"""
Ingest Memory use case.

Accepts raw engineering data (PR diffs, docs, slack threads, etc.),
creates a Memory aggregate, and publishes a MemoryIngested event
to trigger the full processing pipeline.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.memory.entities import Memory, MemorySource
from eng_memory_os.domain.memory.repositories import MemoryRepository
from eng_memory_os.domain.memory.services import MemoryDomainService
from eng_memory_os.domain.shared.types import ImportanceScore
from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class IngestMemoryRequest:
    """Input data for the IngestMemory use case."""

    __slots__ = ("raw_content", "source_uri", "source_type", "author", "title", "tags")

    def __init__(
        self,
        raw_content: str,
        source_uri: str,
        source_type: str,
        author: str,
        title: str,
        tags: list[str] | None = None,
    ) -> None:
        self.raw_content = raw_content
        self.source_uri = source_uri
        self.source_type = source_type
        self.author = author
        self.title = title
        self.tags = tags or []


class IngestMemoryResponse:
    """Output data from the IngestMemory use case."""

    __slots__ = ("memory_id", "status", "importance_score")

    def __init__(self, memory_id: str, status: str, importance_score: float) -> None:
        self.memory_id = memory_id
        self.status = status
        self.importance_score = importance_score


class IngestMemoryUseCase:
    """Orchestrates the ingestion of a new memory artifact.

    Steps:
    1. Check for duplicate source URI
    2. Calculate importance score using heuristics
    3. Create Memory aggregate
    4. Persist to repository
    5. Publish MemoryIngested event (triggers async pipeline)
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._memory_repo = memory_repo
        self._event_bus = event_bus
        self._domain_service = MemoryDomainService()

    async def execute(self, request: IngestMemoryRequest) -> IngestMemoryResponse:
        """Execute the memory ingestion use case."""
        # 1. Check for duplicate
        existing = await self._memory_repo.find_by_source_uri(request.source_uri)
        if existing:
            logger.info(
                "duplicate_source_detected",
                source_uri=request.source_uri,
                existing_id=str(existing.id),
            )
            # Update existing memory instead of creating a duplicate
            existing.update_content(request.raw_content, request.author)
            await self._memory_repo.save(existing)
            events = existing.collect_events()
            await self._event_bus.publish_all(events)

            return IngestMemoryResponse(
                memory_id=str(existing.id),
                status=existing.status.value,
                importance_score=float(existing.importance_score),
            )

        # 2. Calculate importance score
        has_code = self._domain_service.detect_code_blocks(request.raw_content)
        has_arch = self._domain_service.detect_architecture_keywords(request.raw_content)
        importance = self._domain_service.calculate_importance(
            source_type=request.source_type,
            content_length=len(request.raw_content),
            has_code_blocks=has_code,
            has_architecture_keywords=has_arch,
        )

        # 3. Create Memory aggregate
        try:
            source_type = MemorySource(request.source_type)
        except ValueError:
            source_type = MemorySource.MANUAL_INPUT

        memory = Memory.ingest(
            raw_content=request.raw_content,
            source_uri=request.source_uri,
            source_type=source_type,
            author=request.author,
            title=request.title,
            importance=float(importance),
            tags=request.tags,
        )

        # 4. Persist
        await self._memory_repo.save(memory)

        # 5. Publish domain events (triggers the processing pipeline)
        events = memory.collect_events()
        await self._event_bus.publish_all(events)

        logger.info(
            "memory_ingested",
            memory_id=str(memory.id),
            source_type=request.source_type,
            importance=float(importance),
            content_length=len(request.raw_content),
        )

        return IngestMemoryResponse(
            memory_id=str(memory.id),
            status=memory.status.value,
            importance_score=float(importance),
        )
