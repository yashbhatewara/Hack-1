"""
Knowledge value objects.

Immutable types for graph node/edge identifiers, positions, and entity mentions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Self

from eng_memory_os.domain.shared.types import EntityId, new_entity_id


@dataclass(frozen=True)
class NodeId:
    """Strongly-typed identifier for a knowledge graph node."""

    value: EntityId

    @classmethod
    def generate(cls) -> Self:
        return cls(value=new_entity_id())

    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls(value=EntityId(uuid.UUID(value)))

    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True)
class EdgeId:
    """Strongly-typed identifier for a knowledge graph edge."""

    value: EntityId

    @classmethod
    def generate(cls) -> Self:
        return cls(value=new_entity_id())

    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls(value=EntityId(uuid.UUID(value)))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class GraphPosition:
    """2D position for graph visualization layout.

    Used by the frontend React Flow graph explorer to position nodes.
    """

    x: float
    y: float

    @classmethod
    def origin(cls) -> Self:
        return cls(x=0.0, y=0.0)

    def translate(self, dx: float, dy: float) -> GraphPosition:
        return GraphPosition(x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True)
class EntityMention:
    """A mention of an entity within a specific memory chunk.

    Tracks where in the source text an entity was identified,
    enabling evidence tracing back to exact source locations.
    """

    entity_name: str
    entity_type: str
    memory_id: str
    chunk_index: int
    start_offset: int
    end_offset: int
    context_snippet: str

    @property
    def span_length(self) -> int:
        return self.end_offset - self.start_offset
