"""
Shared pytest fixtures for all test suites.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from eng_memory_os.domain.memory.entities import Memory, MemorySource, MemoryStatus
from eng_memory_os.domain.memory.value_objects import MemoryId, MemoryChunk, Provenance, SourceUri
from eng_memory_os.domain.shared.types import (
    ConfidenceScore,
    DecayFactor,
    ImportanceScore,
    new_entity_id,
    now_utc,
)
from eng_memory_os.domain.knowledge.entities import (
    EntityType,
    KnowledgeNode,
    KnowledgeEdge,
    RelationshipType,
)
from eng_memory_os.domain.knowledge.value_objects import EdgeId, NodeId


# ─── Domain Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_memory() -> Memory:
    """Create a fully initialized Memory entity in ACTIVE state."""
    mem = Memory.ingest(
        raw_content="This ADR explains why we chose gRPC for inter-service communication in Q3 2024.",
        source_uri="https://github.com/org/repo/docs/adr/042-grpc.md",
        source_type=MemorySource.ADR,
        author="alice@company.com",
        title="ADR-042: REST to gRPC Migration",
        importance=7.5,
        tags=["architecture", "grpc"],
    )
    # Manually set status to PROCESSING so mark_active is valid
    mem.status = MemoryStatus.PROCESSING
    chunk = MemoryChunk(
        chunk_id=new_entity_id(),
        memory_id=mem.id.value,
        content="gRPC provides lower latency and bidirectional streaming.",
        chunk_index=0,
        token_count=12,
        embedding_vector=[0.1] * 1536,
    )
    mem.mark_active([chunk])
    return mem


@pytest.fixture
def pending_memory() -> Memory:
    """Create a Memory entity in PENDING state."""
    return Memory.ingest(
        raw_content="Auth service upgrade plan for 2025 Q1.",
        source_uri="https://jira.company.com/PROJECT/PLAN-123",
        source_type=MemorySource.JIRA_TICKET,
        author="bob@company.com",
        title="Auth Service Upgrade Plan",
        tags=["auth", "security"],
    )


@pytest.fixture
def sample_node() -> KnowledgeNode:
    """Create a KnowledgeNode entity."""
    return KnowledgeNode(
        id=NodeId.generate(),
        entity_type=EntityType.COMPONENT,
        name="AuthService",
        description="Handles authentication and authorization for all microservices.",
        aliases=["auth", "authentication-service"],
        source_memory_ids=[str(new_entity_id())],
        pagerank_score=0.08,
        degree_centrality=0.45,
        betweenness_centrality=0.12,
        created_at=now_utc(),
        updated_at=now_utc(),
    )


@pytest.fixture
def sample_edge(sample_node: KnowledgeNode) -> KnowledgeEdge:
    """Create a KnowledgeEdge between two nodes."""
    target = KnowledgeNode(
        id=NodeId.generate(),
        entity_type=EntityType.COMPONENT,
        name="PaymentService",
        description="Handles payment processing.",
        aliases=[],
        source_memory_ids=[],
        pagerank_score=0.05,
        degree_centrality=0.3,
        betweenness_centrality=0.08,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    return KnowledgeEdge(
        id=EdgeId.generate(),
        source_node_id=sample_node.id,
        target_node_id=target.id,
        relationship_type=RelationshipType.DEPENDS_ON,
        weight=1.0,
        description="PaymentService depends on AuthService for token validation.",
        source_memory_id=str(new_entity_id()),
        created_at=now_utc(),
    )


# ─── Mock Infrastructure Fixtures ─────────────────────────────────────────────

@pytest.fixture
def mock_memory_repo():
    """Mock MemoryRepository."""
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.find_by_source_uri = AsyncMock(return_value=None)
    repo.find_by_status = AsyncMock(return_value=[])
    repo.count_by_status = AsyncMock(return_value={})
    repo.find_for_decay = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_event_bus():
    """Mock InMemoryEventBus."""
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value=None)
    bus.publish_all = AsyncMock(return_value=None)
    return bus


@pytest.fixture
def mock_graph_repo():
    """Mock KnowledgeGraphRepository."""
    repo = AsyncMock()
    repo.save_node = AsyncMock(return_value=None)
    repo.save_edge = AsyncMock(return_value=None)
    repo.find_nodes_by_name = AsyncMock(return_value=[])
    repo.get_node_by_id = AsyncMock(return_value=None)
    repo.get_neighbors = AsyncMock(return_value=MagicMock(nodes=[], edges=[]))
    repo.get_graph_stats = AsyncMock(return_value={"total_nodes": 0, "total_edges": 0})
    return repo


@pytest.fixture
def mock_llm_gateway():
    """Mock LLMGateway."""
    gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "search"
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    gateway.complete = AsyncMock(return_value=mock_response)
    return gateway


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService."""
    svc = AsyncMock()
    svc.embed_texts = AsyncMock(return_value=[[0.1] * 1536])
    svc.embed_query = AsyncMock(return_value=[0.1] * 1536)
    svc.get_dimension = MagicMock(return_value=1536)
    return svc


@pytest.fixture
def mock_vector_store():
    """Mock VectorStoreRepository."""
    store = AsyncMock()
    store.search_similar = AsyncMock(return_value=[])
    store.upsert_chunks = AsyncMock(return_value=0)
    store.ensure_collection = AsyncMock(return_value=None)
    return store
