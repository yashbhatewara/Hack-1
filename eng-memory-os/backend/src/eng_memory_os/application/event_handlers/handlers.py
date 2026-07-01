"""
Event handlers that wire bounded contexts together.

These handlers subscribe to domain events via the event bus,
enabling loose coupling between the Memory, Knowledge, and Agent contexts.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.memory.events import MemoryIngested, MemoryUpdated
from eng_memory_os.domain.knowledge.events import EntitiesExtracted
from eng_memory_os.domain.shared.events import DomainEvent

logger = structlog.get_logger(__name__)


class OnMemoryIngestedHandler:
    """Triggered when a new memory is ingested.

    Kicks off the full processing pipeline:
    1. Transition memory to PROCESSING state
    2. Run normalization and semantic chunking
    3. Trigger entity extraction
    4. Trigger vectorization
    """

    def __init__(
        self,
        memory_repo: object,
        pipeline: object,
    ) -> None:
        self._memory_repo = memory_repo
        self._pipeline = pipeline

    async def __call__(self, event: DomainEvent) -> None:
        if not isinstance(event, MemoryIngested):
            return

        logger.info(
            "handling_memory_ingested",
            memory_id=event.memory_id,
            source_type=event.source_type,
        )

        try:
            # Delegate to the memory pipeline
            if hasattr(self._pipeline, "process"):
                await self._pipeline.process(event.memory_id)
        except Exception:
            logger.exception(
                "memory_processing_failed",
                memory_id=event.memory_id,
            )


class OnMemoryUpdatedHandler:
    """Triggered when a memory's content is updated.

    Reprocesses the memory through the pipeline (re-chunk, re-extract, re-vectorize).
    """

    def __init__(self, pipeline: object) -> None:
        self._pipeline = pipeline

    async def __call__(self, event: DomainEvent) -> None:
        if not isinstance(event, MemoryUpdated):
            return

        logger.info("handling_memory_updated", memory_id=event.memory_id)

        try:
            if hasattr(self._pipeline, "process"):
                await self._pipeline.process(event.memory_id)
        except Exception:
            logger.exception("memory_reprocessing_failed", memory_id=event.memory_id)


class OnEntitiesExtractedHandler:
    """Triggered when entities are extracted from a memory.

    Kicks off vectorization of the chunks and graph optimization
    if a significant number of new entities were added.
    """

    OPTIMIZATION_THRESHOLD = 50  # Optimize graph every N new entities

    def __init__(
        self,
        vector_store: object,
        graph_optimizer: object,
    ) -> None:
        self._vector_store = vector_store
        self._graph_optimizer = graph_optimizer
        self._entities_since_optimization = 0

    async def __call__(self, event: DomainEvent) -> None:
        if not isinstance(event, EntitiesExtracted):
            return

        logger.info(
            "handling_entities_extracted",
            memory_id=event.memory_id,
            entity_count=event.entity_count,
        )

        self._entities_since_optimization += event.entity_count

        # Trigger graph optimization if threshold reached
        if self._entities_since_optimization >= self.OPTIMIZATION_THRESHOLD:
            logger.info(
                "triggering_graph_optimization",
                entities_since_last=self._entities_since_optimization,
            )
            try:
                if hasattr(self._graph_optimizer, "execute"):
                    await self._graph_optimizer.execute()
                self._entities_since_optimization = 0
            except Exception:
                logger.exception("graph_optimization_failed")


class EventAuditLogger:
    """Global handler that logs every domain event for auditing.

    Subscribed via event_bus.subscribe_all() to receive all events.
    """

    async def __call__(self, event: DomainEvent) -> None:
        logger.info(
            "domain_event",
            event_type=event.event_type,
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
        )
