"""
Memory value objects.

Immutable, validated domain primitives that carry no identity.
Value objects are equal when all their attributes are equal.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Self

from eng_memory_os.domain.shared.types import EntityId, new_entity_id


@dataclass(frozen=True)
class MemoryId:
    """Strongly-typed identifier for a Memory aggregate."""

    value: EntityId

    @classmethod
    def generate(cls) -> Self:
        """Generate a new unique MemoryId."""
        return cls(value=new_entity_id())

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Parse a MemoryId from its string representation."""
        return cls(value=EntityId(uuid.UUID(value)))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class SourceUri:
    """URI identifying the original source of a memory.

    Examples:
        - github://org/repo/pull/123
        - slack://channel/C123/message/ts123
        - jira://PROJECT/ISSUE-456
        - notion://page/abc123
        - file:///path/to/doc.md
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("SourceUri cannot be empty")

    @property
    def scheme(self) -> str:
        """Extract the URI scheme (e.g., 'github', 'slack')."""
        parts = self.value.split("://", maxsplit=1)
        return parts[0] if len(parts) == 2 else "unknown"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Provenance:
    """Cryptographic proof of the source data's integrity.

    The hash is computed over the raw source content to enable
    verification that the memory was derived from authentic source data.
    """

    hash_algorithm: str
    hash_value: str

    @classmethod
    def from_content(cls, content: str, algorithm: str = "sha256") -> Self:
        """Compute provenance hash from raw content."""
        hasher = hashlib.new(algorithm)
        hasher.update(content.encode("utf-8"))
        return cls(hash_algorithm=algorithm, hash_value=hasher.hexdigest())

    @classmethod
    def from_bytes(cls, data: bytes, algorithm: str = "sha256") -> Self:
        """Compute provenance hash from raw bytes."""
        hasher = hashlib.new(algorithm)
        hasher.update(data)
        return cls(hash_algorithm=algorithm, hash_value=hasher.hexdigest())

    def verify(self, content: str) -> bool:
        """Verify that content matches this provenance hash."""
        expected = Provenance.from_content(content, self.hash_algorithm)
        return self.hash_value == expected.hash_value

    def __str__(self) -> str:
        return f"{self.hash_algorithm}:{self.hash_value}"


@dataclass(frozen=True)
class MemoryChunk:
    """A semantically coherent chunk of a memory after splitting.

    Chunks are the unit of vectorization — each chunk gets its own
    embedding vector and is stored independently in the vector database.
    """

    chunk_id: EntityId
    memory_id: EntityId
    content: str
    chunk_index: int
    token_count: int
    embedding_vector: list[float] | None = None

    @classmethod
    def create(
        cls,
        memory_id: EntityId,
        content: str,
        chunk_index: int,
        token_count: int,
    ) -> Self:
        """Create a new chunk without an embedding (pre-vectorization)."""
        return cls(
            chunk_id=new_entity_id(),
            memory_id=memory_id,
            content=content,
            chunk_index=chunk_index,
            token_count=token_count,
            embedding_vector=None,
        )

    def with_embedding(self, vector: list[float]) -> MemoryChunk:
        """Return a new chunk with the embedding vector attached."""
        return MemoryChunk(
            chunk_id=self.chunk_id,
            memory_id=self.memory_id,
            content=self.content,
            chunk_index=self.chunk_index,
            token_count=self.token_count,
            embedding_vector=vector,
        )

    @property
    def is_embedded(self) -> bool:
        return self.embedding_vector is not None
