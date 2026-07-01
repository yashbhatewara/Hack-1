"""
Knowledge graph entities.

Defines the nodes, edges, and aggregate graph structures that form
the engineering knowledge graph. Nodes represent entities (actors,
components, decisions, incidents) and edges represent relationships
between them.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime

from eng_memory_os.domain.shared.types import now_utc, Timestamp
from eng_memory_os.domain.knowledge.value_objects import (
    EdgeId,
    EntityMention,
    GraphPosition,
    NodeId,
)


class EntityType(enum.StrEnum):
    """Types of entities that can be extracted from engineering knowledge."""

    ACTOR = "actor"                 # A person, team, or org
    COMPONENT = "component"         # A service, library, module, or system
    DECISION = "decision"           # An architectural or design decision
    INCIDENT = "incident"           # A production incident or outage
    TECHNOLOGY = "technology"       # A framework, language, or tool
    CONCEPT = "concept"             # A design pattern, principle, or methodology
    METRIC = "metric"               # A KPI, SLO, or measurement
    DOCUMENT = "document"           # A doc, RFC, or ADR
    ENVIRONMENT = "environment"     # A deployment environment (prod, staging, etc.)
    API_ENDPOINT = "api_endpoint"   # A specific API route or endpoint


class RelationshipType(enum.StrEnum):
    """Types of relationships between knowledge nodes."""

    IMPLEMENTED = "implemented"         # Actor -> Component
    DECIDED = "decided"                 # Actor -> Decision
    CAUSED = "caused"                   # Component/Decision -> Incident
    RESOLVED = "resolved"              # Actor -> Incident
    DEPENDS_ON = "depends_on"          # Component -> Component
    REPLACED = "replaced"              # Component -> Component
    USES = "uses"                      # Component -> Technology
    AUTHORED = "authored"              # Actor -> Document
    REFERENCES = "references"          # Document -> Decision/Component
    AFFECTED = "affected"              # Incident -> Component
    MONITORS = "monitors"              # Metric -> Component
    MEMBER_OF = "member_of"            # Actor -> Actor (team membership)
    DEPLOYED_TO = "deployed_to"        # Component -> Environment
    EXPOSES = "exposes"                # Component -> API_ENDPOINT
    RELATED_TO = "related_to"          # Generic relationship


@dataclass
class KnowledgeNode:
    """A node in the engineering knowledge graph.

    Represents an extracted entity with its metadata, source provenance,
    and graph metrics (PageRank, degree centrality).
    """

    id: NodeId
    entity_type: EntityType
    name: str
    description: str
    properties: dict[str, str | int | float | bool]

    # Source provenance
    source_memory_ids: list[str]
    mentions: list[EntityMention]

    # Graph metrics (updated during optimization)
    pagerank_score: float
    degree_centrality: float

    # Layout
    position: GraphPosition

    # Lifecycle
    created_at: Timestamp
    updated_at: Timestamp

    # Aliases for synonym resolution
    aliases: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        entity_type: EntityType,
        name: str,
        description: str,
        source_memory_id: str,
        mention: EntityMention | None = None,
        properties: dict[str, str | int | float | bool] | None = None,
    ) -> KnowledgeNode:
        """Factory method to create a new knowledge node."""
        now = now_utc()
        return cls(
            id=NodeId.generate(),
            entity_type=entity_type,
            name=name,
            description=description,
            properties=properties or {},
            source_memory_ids=[source_memory_id],
            mentions=[mention] if mention else [],
            pagerank_score=0.0,
            degree_centrality=0.0,
            position=GraphPosition.origin(),
            created_at=now,
            updated_at=now,
        )

    def merge_with(self, other: KnowledgeNode) -> None:
        """Merge another node into this one (deduplication).

        Combines source references, mentions, and properties.
        The other node should be deleted after merging.
        """
        # Merge source memory IDs (deduplicate)
        existing_ids = set(self.source_memory_ids)
        for mid in other.source_memory_ids:
            if mid not in existing_ids:
                self.source_memory_ids.append(mid)

        # Merge mentions
        self.mentions.extend(other.mentions)

        # Merge properties (other's properties take precedence for conflicts)
        self.properties.update(other.properties)

        # Add other's name as an alias if different
        if other.name.lower() != self.name.lower() and other.name not in self.aliases:
            self.aliases.append(other.name)

        # Merge aliases
        existing_aliases = set(a.lower() for a in self.aliases)
        for alias in other.aliases:
            if alias.lower() not in existing_aliases:
                self.aliases.append(alias)

        self.updated_at = now_utc()

    def matches_name(self, query: str) -> bool:
        """Check if this node matches a name query (case-insensitive, alias-aware)."""
        query_lower = query.lower()
        if self.name.lower() == query_lower:
            return True
        return any(alias.lower() == query_lower for alias in self.aliases)

    def update_metrics(self, pagerank: float, degree_centrality: float) -> None:
        """Update graph metrics after optimization."""
        self.pagerank_score = pagerank
        self.degree_centrality = degree_centrality
        self.updated_at = now_utc()


@dataclass
class KnowledgeEdge:
    """A directed edge in the engineering knowledge graph.

    Represents a relationship between two entities, with metadata
    about the strength and source of the relationship.
    """

    id: EdgeId
    source_node_id: NodeId
    target_node_id: NodeId
    relationship_type: RelationshipType
    weight: float  # Relationship strength [0.0, 1.0]
    description: str
    source_memory_ids: list[str]
    created_at: Timestamp
    updated_at: Timestamp

    @classmethod
    def create(
        cls,
        source_node_id: NodeId,
        target_node_id: NodeId,
        relationship_type: RelationshipType,
        description: str,
        source_memory_id: str,
        weight: float = 1.0,
    ) -> KnowledgeEdge:
        """Factory method to create a new knowledge edge."""
        now = now_utc()
        return cls(
            id=EdgeId.generate(),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            weight=min(1.0, max(0.0, weight)),
            description=description,
            source_memory_ids=[source_memory_id],
            created_at=now,
            updated_at=now,
        )

    def strengthen(self, additional_memory_id: str, boost: float = 0.1) -> None:
        """Strengthen the edge when additional evidence is found."""
        if additional_memory_id not in self.source_memory_ids:
            self.source_memory_ids.append(additional_memory_id)
        self.weight = min(1.0, self.weight + boost)
        self.updated_at = now_utc()


@dataclass
class KnowledgeGraph:
    """In-memory representation of a subgraph for query-time operations.

    This is NOT the full persistent graph — it's a working set loaded
    from the repository for traversal, ranking, and visualization.
    """

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    def add_node(self, node: KnowledgeNode) -> None:
        self.nodes[str(node.id)] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[KnowledgeNode]:
        """Get N-degree neighbors of a node via BFS traversal."""
        if node_id not in self.nodes:
            return []

        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}
        result: list[KnowledgeNode] = []

        for _ in range(depth):
            next_frontier: set[str] = set()
            for current_id in frontier:
                for edge in self.edges:
                    src = str(edge.source_node_id)
                    tgt = str(edge.target_node_id)
                    if src == current_id and tgt not in visited:
                        next_frontier.add(tgt)
                        visited.add(tgt)
                    elif tgt == current_id and src not in visited:
                        next_frontier.add(src)
                        visited.add(src)
            for nid in next_frontier:
                node = self.nodes.get(nid)
                if node:
                    result.append(node)
            frontier = next_frontier

        return result

    def get_edges_for_node(self, node_id: str) -> list[KnowledgeEdge]:
        """Get all edges connected to a node (inbound + outbound)."""
        return [
            e for e in self.edges
            if str(e.source_node_id) == node_id or str(e.target_node_id) == node_id
        ]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
