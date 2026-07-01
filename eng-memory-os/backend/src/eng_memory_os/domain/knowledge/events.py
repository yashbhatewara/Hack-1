"""
Domain events emitted by the Knowledge bounded context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eng_memory_os.domain.shared.events import DomainEvent


@dataclass(frozen=True)
class EntitiesExtracted(DomainEvent):
    """Emitted when entities are extracted from a memory."""

    memory_id: str = ""
    node_ids: list[str] = field(default_factory=list)
    entity_count: int = 0
    entity_types: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipsMapped(DomainEvent):
    """Emitted when relationships between entities are identified."""

    memory_id: str = ""
    edge_ids: list[str] = field(default_factory=list)
    relationship_count: int = 0


@dataclass(frozen=True)
class GraphOptimized(DomainEvent):
    """Emitted when the knowledge graph is optimized (dedup, PageRank update)."""

    nodes_merged: int = 0
    nodes_removed: int = 0
    pagerank_updated: bool = False
    total_nodes: int = 0
    total_edges: int = 0


@dataclass(frozen=True)
class NodesMerged(DomainEvent):
    """Emitted when duplicate nodes are merged during graph optimization."""

    surviving_node_id: str = ""
    merged_node_ids: list[str] = field(default_factory=list)
    merge_reason: str = ""
