"""
Dependency Injection container.

Wires together all layers (infrastructure → application → presentation)
using FastAPI's dependency injection system. This is the single
composition root for the entire application.
"""

from __future__ import annotations

import time
from functools import lru_cache

import structlog
from fastapi import Depends, Request

from eng_memory_os.cmd.config import Settings
from eng_memory_os.infrastructure.db.connection import DatabaseSessionManager

logger = structlog.get_logger(__name__)

# Global singletons (initialized during app lifespan)
_db_manager: DatabaseSessionManager | None = None
_event_bus = None
_llm_gateway = None
_vector_store = None
_graph_repo = None
_embedding_service = None
_agent_runner = None
_start_time: float = 0.0


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


async def initialize_services(settings: Settings) -> None:
    """Initialize all infrastructure services. Called during app lifespan startup."""
    global _db_manager, _event_bus, _llm_gateway, _vector_store
    global _graph_repo, _embedding_service, _agent_runner, _start_time

    _start_time = time.monotonic()

    # 1. Database
    from eng_memory_os.infrastructure.db.connection import DatabaseSessionManager
    _db_manager = DatabaseSessionManager(settings.database_url)
    await _db_manager.initialize()

    # 2. Event Bus
    from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus
    _event_bus = InMemoryEventBus()

    # 3. LLM Gateway
    from eng_memory_os.infrastructure.llm.gateway import LLMGatewayImpl
    from eng_memory_os.domain.gateway.entities import LLMProvider
    _llm_gateway = LLMGatewayImpl(
        primary_provider=LLMProvider.OPENAI,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
    )

    # 4. Vector Store
    from eng_memory_os.infrastructure.db.vector.qdrant_adapter import QdrantVectorStoreAdapter
    _vector_store = QdrantVectorStoreAdapter(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

    # 5. Embedding Service
    if settings.openai_api_key:
        from eng_memory_os.infrastructure.db.vector.embedding_service import OpenAIEmbeddingService
        _embedding_service = OpenAIEmbeddingService(api_key=settings.openai_api_key)
    else:
        from eng_memory_os.infrastructure.db.vector.embedding_service import OllamaEmbeddingService
        _embedding_service = OllamaEmbeddingService(base_url=settings.ollama_base_url)

    # 6. Knowledge Graph
    from eng_memory_os.infrastructure.cognee.cognee_adapter import CogneeGraphAdapter
    _graph_repo = CogneeGraphAdapter()

    # 7. Agent Graph Runner
    from eng_memory_os.infrastructure.langgraph.graph_builder import AgentGraphRunner
    _agent_runner = AgentGraphRunner(
        llm_gateway=_llm_gateway,
        vector_store=_vector_store,
        graph_repo=_graph_repo,
        embedding_service=_embedding_service,
    )

    # 8. Register event handlers
    from eng_memory_os.application.event_handlers.handlers import (
        EventAuditLogger,
        OnEntitiesExtractedHandler,
        OnMemoryIngestedHandler,
    )
    from eng_memory_os.application.pipelines.memory_pipeline import MemoryPipeline
    from eng_memory_os.application.knowledge.extract_entities import ExtractEntitiesUseCase
    from eng_memory_os.infrastructure.cognee.entity_extractor import EntityExtractor
    from eng_memory_os.application.knowledge.optimize_graph import OptimizeGraphUseCase

    entity_extractor = EntityExtractor(_llm_gateway)
    extract_uc = ExtractEntitiesUseCase(
        memory_repo=await _get_memory_repo_internal(),
        graph_repo=_graph_repo,
        entity_extractor=entity_extractor,
        event_bus=_event_bus,
    )
    pipeline = MemoryPipeline(
        memory_repo=await _get_memory_repo_internal(),
        extract_entities_uc=extract_uc,
        embedding_service=_embedding_service,
        vector_store=_vector_store,
        event_bus=_event_bus,
    )
    optimize_uc = OptimizeGraphUseCase(graph_repo=_graph_repo, event_bus=_event_bus)

    from eng_memory_os.domain.memory.events import MemoryIngested, MemoryUpdated
    from eng_memory_os.domain.knowledge.events import EntitiesExtracted

    _event_bus.subscribe(MemoryIngested, OnMemoryIngestedHandler(
        memory_repo=await _get_memory_repo_internal(),
        pipeline=pipeline,
    ))
    _event_bus.subscribe(MemoryUpdated, OnMemoryIngestedHandler(
        memory_repo=await _get_memory_repo_internal(),
        pipeline=pipeline,
    ))
    _event_bus.subscribe(EntitiesExtracted, OnEntitiesExtractedHandler(
        vector_store=_vector_store,
        graph_optimizer=optimize_uc,
    ))
    _event_bus.subscribe_all(EventAuditLogger())

    logger.info("all_services_initialized")


async def shutdown_services() -> None:
    """Shutdown all services. Called during app lifespan shutdown."""
    global _db_manager, _vector_store
    if _db_manager:
        await _db_manager.close()
    if _vector_store and hasattr(_vector_store, "close"):
        await _vector_store.close()
    logger.info("all_services_shutdown")


async def _get_memory_repo_internal():
    """Internal helper to create a memory repo with a fresh session."""
    from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
    if _db_manager is None:
        raise RuntimeError("Database not initialized")
    # Return a factory — actual session is created per-request
    return _MemoryRepoFactory(_db_manager)


class _MemoryRepoFactory:
    """Lazy factory for memory repositories — creates a session per call."""

    def __init__(self, db_manager: DatabaseSessionManager) -> None:
        self._db_manager = db_manager

    async def save(self, memory):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            await repo.save(memory)

    async def get_by_id(self, memory_id):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.get_by_id(memory_id)

    async def find_by_source_uri(self, uri):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.find_by_source_uri(uri)

    async def find_by_status(self, status, limit=100, offset=0):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.find_by_status(status, limit, offset)

    async def find_by_author(self, author, limit=50, offset=0):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.find_by_author(author, limit, offset)

    async def search_by_tags(self, tags, limit=50):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.search_by_tags(tags, limit)

    async def count_by_status(self):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.count_by_status()

    async def list_recent(self, since=None, limit=50, offset=0):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.list_recent(since, limit, offset)

    async def delete(self, memory_id):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.delete(memory_id)

    async def find_for_decay(self, batch_size=500):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.find_for_decay(batch_size)

    async def find_stale(self, decay_threshold=0.3, limit=100):
        async with self._db_manager.session() as session:
            from eng_memory_os.infrastructure.db.postgres_repository import PostgresMemoryRepository
            repo = PostgresMemoryRepository(session)
            return await repo.find_stale(decay_threshold, limit)


# ───────────────── FastAPI Dependency Getters ─────────────────

def get_event_bus():
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized")
    return _event_bus


def get_llm_gateway():
    if _llm_gateway is None:
        raise RuntimeError("LLM Gateway not initialized")
    return _llm_gateway


def get_vector_store():
    if _vector_store is None:
        raise RuntimeError("Vector store not initialized")
    return _vector_store


def get_graph_repo():
    if _graph_repo is None:
        raise RuntimeError("Graph repo not initialized")
    return _graph_repo


def get_embedding_service():
    if _embedding_service is None:
        raise RuntimeError("Embedding service not initialized")
    return _embedding_service


def get_agent_runner():
    if _agent_runner is None:
        raise RuntimeError("Agent runner not initialized")
    return _agent_runner


async def get_memory_repo():
    return await _get_memory_repo_internal()


def get_uptime() -> float:
    return time.monotonic() - _start_time
