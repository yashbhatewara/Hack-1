"""
Abstract repository interface for the Memory bounded context.

This defines the contract that infrastructure implementations (PostgreSQL, etc.)
must fulfill. The domain layer depends only on this interface — never on
concrete database implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from eng_memory_os.domain.memory.entities import Memory, MemoryStatus
from eng_memory_os.domain.memory.value_objects import MemoryId


class MemoryRepository(ABC):
    """Abstract repository for Memory aggregate persistence.

    All methods are async to support non-blocking I/O at the infrastructure layer.
    """

    @abstractmethod
    async def save(self, memory: Memory) -> None:
        """Persist a new or updated Memory aggregate.

        If the memory already exists (by ID), it must be updated.
        If it does not exist, it must be inserted.
        """
        ...

    @abstractmethod
    async def get_by_id(self, memory_id: MemoryId) -> Memory | None:
        """Retrieve a Memory by its unique identifier.

        Returns None if no memory with the given ID exists.
        """
        ...

    @abstractmethod
    async def find_by_status(
        self,
        status: MemoryStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        """Find all memories with a given lifecycle status.

        Results are ordered by updated_at descending (most recent first).
        """
        ...

    @abstractmethod
    async def find_by_source_uri(self, source_uri: str) -> Memory | None:
        """Find a memory by its original source URI.

        Used to detect duplicates during ingestion.
        """
        ...

    @abstractmethod
    async def find_by_author(
        self,
        author: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        """Find all memories authored by a specific person."""
        ...

    @abstractmethod
    async def find_stale(
        self,
        decay_threshold: float = 0.3,
        limit: int = 100,
    ) -> list[Memory]:
        """Find memories whose decay factor is below the given threshold.

        Used by the background worker for staleness management.
        """
        ...

    @abstractmethod
    async def find_for_decay(
        self,
        batch_size: int = 500,
    ) -> list[Memory]:
        """Find active memories that need decay recalculation.

        Returns a batch of ACTIVE memories ordered by last decay application time.
        """
        ...

    @abstractmethod
    async def search_by_tags(
        self,
        tags: list[str],
        limit: int = 50,
    ) -> list[Memory]:
        """Find memories that match any of the given tags."""
        ...

    @abstractmethod
    async def count_by_status(self) -> dict[MemoryStatus, int]:
        """Return counts of memories grouped by status.

        Used for dashboard metrics and health monitoring.
        """
        ...

    @abstractmethod
    async def delete(self, memory_id: MemoryId) -> bool:
        """Permanently delete a memory. Returns True if found and deleted."""
        ...

    @abstractmethod
    async def list_recent(
        self,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        """List recently updated memories, optionally filtered by timestamp."""
        ...
