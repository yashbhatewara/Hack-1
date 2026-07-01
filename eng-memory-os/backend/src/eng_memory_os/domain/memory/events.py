"""
Domain events emitted by the Memory bounded context.

These events are consumed by handlers in the Application layer
to trigger downstream processing (entity extraction, vectorization, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

from eng_memory_os.domain.shared.events import DomainEvent


@dataclass(frozen=True)
class MemoryIngested(DomainEvent):
    """Emitted when a new memory is successfully received for processing.

    Downstream handlers should trigger the full ingestion pipeline:
    normalization → chunking → entity extraction → vectorization → storage.
    """

    memory_id: str = ""
    source_uri: str = ""
    source_type: str = ""
    author: str = ""
    title: str = ""


@dataclass(frozen=True)
class MemoryUpdated(DomainEvent):
    """Emitted when a memory's content is updated and needs reprocessing."""

    memory_id: str = ""
    author: str = ""


@dataclass(frozen=True)
class MemoryDecayed(DomainEvent):
    """Emitted when a memory's decay factor drops below the staleness threshold.

    Downstream handlers may notify users or trigger re-evaluation.
    """

    memory_id: str = ""
    new_decay_factor: float = 0.0


@dataclass(frozen=True)
class MemoryArchived(DomainEvent):
    """Emitted when a memory is archived (manually or automatically)."""

    memory_id: str = ""


@dataclass(frozen=True)
class MemoryProcessingCompleted(DomainEvent):
    """Emitted when the full ingestion pipeline completes successfully."""

    memory_id: str = ""
    chunk_count: int = 0
    entity_count: int = 0


@dataclass(frozen=True)
class MemoryProcessingFailed(DomainEvent):
    """Emitted when the ingestion pipeline fails at any stage."""

    memory_id: str = ""
    stage: str = ""
    error_message: str = ""
