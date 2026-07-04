"""
Memory aggregate root entity.

The Memory entity is the central aggregate in the Memory bounded context.
It represents a single unit of engineering knowledge — a PR diff, an
architecture decision, an incident report, etc. — along with its
metadata, lifecycle state, and quality scores.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self

from eng_memory_os.domain.shared.types import (
    ConfidenceScore,
    DecayFactor,
    ImportanceScore,
    now_utc,
    Timestamp,
)
from eng_memory_os.domain.memory.value_objects import (
    MemoryChunk,
    MemoryId,
    Provenance,
    SourceUri,
)
from eng_memory_os.domain.memory.events import (
    MemoryIngested,
    MemoryUpdated,
    MemoryDecayed,
    MemoryArchived,
)
from eng_memory_os.domain.shared.events import DomainEvent


class MemoryStatus(enum.StrEnum):
    """Lifecycle states of a Memory."""

    PENDING = "pending"          # Received but not yet processed
    PROCESSING = "processing"    # Currently in the ingestion pipeline
    ACTIVE = "active"            # Fully processed and queryable
    STALE = "stale"              # Decay factor below threshold
    ARCHIVED = "archived"        # Manually or automatically archived
    FAILED = "failed"            # Processing failed


class MemorySource(enum.StrEnum):
    """Known source types for incoming memories."""

    PULL_REQUEST = "pull_request"
    GITHUB_PR = "github_pr"
    GITHUB_ISSUE = "github_issue"
    GITHUB_COMMIT = "github_commit"
    ARCHITECTURE_DOC = "architecture_doc"
    ADR = "adr"
    INCIDENT_REPORT = "incident_report"
    SLACK_THREAD = "slack_thread"
    JIRA_TICKET = "jira_ticket"
    NOTION_PAGE = "notion_page"
    NOTION_DOC = "notion_doc"
    CONFLUENCE_PAGE = "confluence_page"
    MANUAL_INPUT = "manual_input"
    CODE_REVIEW = "code_review"
    MEETING_NOTES = "meeting_notes"
    POSTMORTEM = "postmortem"
    RUNBOOK = "runbook"


@dataclass
class Memory:
    """Aggregate root for engineering memory artifacts.

    Enforces all domain invariants and emits domain events
    when state transitions occur.
    """

    id: MemoryId
    source_uri: SourceUri
    source_type: MemorySource
    raw_content: str
    author: str
    title: str

    # Quality & ranking scores
    importance_score: ImportanceScore
    confidence_score: ConfidenceScore
    decay_factor: DecayFactor

    # Integrity
    provenance: Provenance

    # Lifecycle
    status: MemoryStatus
    created_at: Timestamp
    updated_at: Timestamp
    last_accessed_at: Timestamp | None = None
    access_count: int = 0

    # Processed artifacts
    chunks: list[MemoryChunk] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Domain events collected during the lifetime of this aggregate
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def ingest(
        cls,
        raw_content: str,
        source_uri: str,
        source_type: MemorySource,
        author: str,
        title: str,
        importance: float = 5.0,
        tags: list[str] | None = None,
    ) -> Self:
        """Factory method: create a new Memory from raw ingestion data.

        This is the single entry point for creating memories. It initializes
        all scores, computes the provenance hash, and emits a MemoryIngested event.
        """
        if not raw_content.strip():
            raise ValueError("Cannot ingest empty content")

        now = now_utc()
        memory_id = MemoryId.generate()

        memory = cls(
            id=memory_id,
            source_uri=SourceUri(source_uri),
            source_type=source_type,
            raw_content=raw_content,
            author=author,
            title=title,
            importance_score=ImportanceScore(importance),
            confidence_score=ConfidenceScore(1.0),  # Full confidence at ingestion
            decay_factor=DecayFactor(1.0),           # No decay at ingestion
            provenance=Provenance.from_content(raw_content),
            status=MemoryStatus.PENDING,
            created_at=now,
            updated_at=now,
            tags=tags or [],
        )

        memory._pending_events.append(
            MemoryIngested(
                memory_id=str(memory_id),
                source_uri=source_uri,
                source_type=source_type.value,
                author=author,
                title=title,
            )
        )

        return memory

    def mark_processing(self) -> None:
        """Transition to PROCESSING state when the pipeline starts."""
        if self.status != MemoryStatus.PENDING:
            raise ValueError(
                f"Cannot start processing: memory is in '{self.status}' state, expected 'pending'"
            )
        self.status = MemoryStatus.PROCESSING
        self.updated_at = now_utc()

    def mark_active(self, chunks: list[MemoryChunk]) -> None:
        """Transition to ACTIVE state when processing completes successfully."""
        if self.status != MemoryStatus.PROCESSING:
            raise ValueError(
                f"Cannot activate: memory is in '{self.status}' state, expected 'processing'"
            )
        if not chunks:
            raise ValueError("Cannot activate a memory with zero chunks")

        self.chunks = chunks
        self.status = MemoryStatus.ACTIVE
        self.updated_at = now_utc()

    def mark_failed(self, reason: str) -> None:
        """Transition to FAILED state when processing encounters an error."""
        self.status = MemoryStatus.FAILED
        self.updated_at = now_utc()
        self.tags.append(f"failure:{reason}")

    def record_access(self) -> None:
        """Record that this memory was accessed (queried/retrieved).

        Access boosts the decay factor, keeping frequently-used memories fresh.
        """
        self.access_count += 1
        self.last_accessed_at = now_utc()
        # Boost decay factor by 10% on access, capped at 1.0
        new_decay = min(1.0, float(self.decay_factor) * 1.1)
        self.decay_factor = DecayFactor(new_decay)

    def apply_decay(self, decay_rate: float = 0.995) -> None:
        """Apply time-based decay to this memory.

        Called periodically by the background worker. Memories that aren't
        accessed gradually lose relevance. When decay drops below 0.3,
        the memory transitions to STALE.

        Args:
            decay_rate: Multiplicative decay per cycle. Default 0.995 means
                        ~0.5% decay per cycle.
        """
        if self.status not in (MemoryStatus.ACTIVE, MemoryStatus.STALE):
            return

        new_decay = float(self.decay_factor) * decay_rate
        self.decay_factor = DecayFactor(max(0.0, new_decay))
        self.updated_at = now_utc()

        if float(self.decay_factor) < 0.3 and self.status == MemoryStatus.ACTIVE:
            self.status = MemoryStatus.STALE
            self._pending_events.append(
                MemoryDecayed(
                    memory_id=str(self.id),
                    new_decay_factor=float(self.decay_factor),
                )
            )

    def update_content(self, new_content: str, author: str) -> None:
        """Update the raw content and recompute provenance."""
        if not new_content.strip():
            raise ValueError("Cannot update with empty content")

        self.raw_content = new_content
        self.provenance = Provenance.from_content(new_content)
        self.status = MemoryStatus.PENDING  # Needs reprocessing
        self.chunks = []  # Clear old chunks
        self.updated_at = now_utc()

        self._pending_events.append(
            MemoryUpdated(
                memory_id=str(self.id),
                author=author,
            )
        )

    def archive(self) -> None:
        """Manually archive this memory."""
        self.status = MemoryStatus.ARCHIVED
        self.updated_at = now_utc()
        self._pending_events.append(
            MemoryArchived(memory_id=str(self.id))
        )

    def collect_events(self) -> list[DomainEvent]:
        """Drain and return all pending domain events."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    @property
    def effective_score(self) -> float:
        """Composite score used for ranking in retrieval results.

        Combines importance, confidence, and decay into a single ranking signal.
        """
        return (
            float(self.importance_score) * 0.4
            + float(self.confidence_score) * 0.3
            + float(self.decay_factor) * 0.3
        )

    @property
    def is_queryable(self) -> bool:
        """Whether this memory can appear in query results."""
        return self.status == MemoryStatus.ACTIVE and len(self.chunks) > 0
