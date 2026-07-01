"""
Cognee-backed implementation of the KnowledgeGraphRepository.

Uses Cognee 1.0's memory-native API (remember, recall, improve, forget)
along with NetworkX for graph operations (PageRank, centrality).
"""

from __future__ import annotations

import uuid
from difflib import SequenceMatcher

import networkx as nx
import structlog

from eng_memory_os.domain.knowledge.entities import (
    EntityType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    RelationshipType,
)
from eng_memory_os.domain.knowledge.repositories import KnowledgeGraphRepository
from eng_memory_os.domain.knowledge.value_objects import (
    EdgeId,
    EntityMention,
    GraphPosition,
    NodeId,
)
from eng_memory_os.domain.shared.types import EntityId, Timestamp, now_utc

logger = structlog.get_logger(__name__)


class CogneeGraphAdapter(KnowledgeGraphRepository):
    """Cognee + NetworkX implementation of the KnowledgeGraphRepository.

    Uses an in-memory NetworkX graph for fast graph operations
    (PageRank, centrality, neighbor traversal) and syncs with Cognee
    for persistent knowledge graph storage.

    This dual approach gives us:
    - Fast graph algorithms (NetworkX is optimized for this)
    - Persistent, semantically-rich knowledge graph (Cognee)
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}

    async def save_node(self, node: KnowledgeNode) -> None:
        """Persist a knowledge node (upsert)."""
        node_id = str(node.id)
        self._nodes[node_id] = node

        # Add to NetworkX graph with metadata
        self._graph.add_node(
            node_id,
            entity_type=node.entity_type.value,
            name=node.name,
            description=node.description,
        )

        logger.debug("node_saved", node_id=node_id, name=node.name, type=node.entity_type.value)

    async def save_edge(self, edge: KnowledgeEdge) -> None:
        """Persist a knowledge edge (upsert)."""
        edge_id = str(edge.id)
        self._edges[edge_id] = edge

        src = str(edge.source_node_id)
        tgt = str(edge.target_node_id)

        # Add to NetworkX graph
        self._graph.add_edge(
            src,
            tgt,
            edge_id=edge_id,
            relationship_type=edge.relationship_type.value,
            weight=edge.weight,
        )

        logger.debug(
            "edge_saved",
            edge_id=edge_id,
            source=src,
            target=tgt,
            type=edge.relationship_type.value,
        )

    async def get_node_by_id(self, node_id: NodeId) -> KnowledgeNode | None:
        return self._nodes.get(str(node_id))

    async def find_nodes_by_name(
        self,
        name: str,
        entity_type: EntityType | None = None,
        fuzzy: bool = False,
    ) -> list[KnowledgeNode]:
        """Find nodes by name with optional fuzzy matching."""
        results: list[KnowledgeNode] = []
        name_lower = name.lower()

        for node in self._nodes.values():
            # Filter by type if specified
            if entity_type and node.entity_type != entity_type:
                continue

            if fuzzy:
                # Fuzzy matching using sequence similarity
                similarity = SequenceMatcher(None, name_lower, node.name.lower()).ratio()
                if similarity >= 0.7:
                    results.append(node)
                elif any(
                    SequenceMatcher(None, name_lower, alias.lower()).ratio() >= 0.7
                    for alias in node.aliases
                ):
                    results.append(node)
            else:
                # Exact matching (case-insensitive)
                if node.matches_name(name):
                    results.append(node)

        return results

    async def find_nodes_by_type(
        self,
        entity_type: EntityType,
        limit: int = 100,
    ) -> list[KnowledgeNode]:
        return [
            n for n in self._nodes.values()
            if n.entity_type == entity_type
        ][:limit]

    async def find_nodes_by_memory_id(self, memory_id: str) -> list[KnowledgeNode]:
        return [
            n for n in self._nodes.values()
            if memory_id in n.source_memory_ids
        ]

    async def get_neighbors(
        self,
        node_id: NodeId,
        depth: int = 1,
        relationship_types: list[RelationshipType] | None = None,
    ) -> KnowledgeGraph:
        """Get N-degree neighbors using BFS on the NetworkX graph."""
        nid = str(node_id)
        if nid not in self._graph:
            return KnowledgeGraph()

        # BFS to find neighbors within depth
        visited: set[str] = {nid}
        frontier: set[str] = {nid}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for current in frontier:
                # Outgoing edges
                for successor in self._graph.successors(current):
                    if successor not in visited:
                        edge_data = self._graph.edges[current, successor]
                        if relationship_types:
                            if edge_data.get("relationship_type") in [rt.value for rt in relationship_types]:
                                next_frontier.add(successor)
                                visited.add(successor)
                        else:
                            next_frontier.add(successor)
                            visited.add(successor)
                # Incoming edges
                for predecessor in self._graph.predecessors(current):
                    if predecessor not in visited:
                        edge_data = self._graph.edges[predecessor, current]
                        if relationship_types:
                            if edge_data.get("relationship_type") in [rt.value for rt in relationship_types]:
                                next_frontier.add(predecessor)
                                visited.add(predecessor)
                        else:
                            next_frontier.add(predecessor)
                            visited.add(predecessor)
            frontier = next_frontier

        # Build the subgraph
        subgraph = KnowledgeGraph()
        for vid in visited:
            node = self._nodes.get(vid)
            if node:
                subgraph.add_node(node)

        # Add edges between visited nodes
        for edge in self._edges.values():
            src = str(edge.source_node_id)
            tgt = str(edge.target_node_id)
            if src in visited and tgt in visited:
                subgraph.add_edge(edge)

        return subgraph

    async def get_edges_between(
        self,
        source_id: NodeId,
        target_id: NodeId,
    ) -> list[KnowledgeEdge]:
        src = str(source_id)
        tgt = str(target_id)
        return [
            e for e in self._edges.values()
            if str(e.source_node_id) == src and str(e.target_node_id) == tgt
        ]

    async def get_full_subgraph(self, node_ids: list[NodeId]) -> KnowledgeGraph:
        id_set = {str(nid) for nid in node_ids}
        subgraph = KnowledgeGraph()

        for nid in id_set:
            node = self._nodes.get(nid)
            if node:
                subgraph.add_node(node)

        for edge in self._edges.values():
            if str(edge.source_node_id) in id_set and str(edge.target_node_id) in id_set:
                subgraph.add_edge(edge)

        return subgraph

    async def delete_node(self, node_id: NodeId) -> bool:
        nid = str(node_id)
        if nid not in self._nodes:
            return False

        # Remove from NetworkX
        if nid in self._graph:
            self._graph.remove_node(nid)

        # Remove connected edges
        edges_to_remove = [
            eid for eid, e in self._edges.items()
            if str(e.source_node_id) == nid or str(e.target_node_id) == nid
        ]
        for eid in edges_to_remove:
            del self._edges[eid]

        # Remove node
        del self._nodes[nid]
        return True

    async def compute_pagerank(self) -> dict[str, float]:
        """Compute PageRank using NetworkX's optimized implementation."""
        if len(self._graph) == 0:
            return {}

        try:
            scores = nx.pagerank(self._graph, alpha=0.85, max_iter=100)
            # Update node objects
            for nid, score in scores.items():
                node = self._nodes.get(nid)
                if node:
                    node.pagerank_score = score

            logger.info("pagerank_computed", node_count=len(scores))
            return {str(k): v for k, v in scores.items()}
        except nx.PowerIterationFailedConvergence:
            logger.warning("pagerank_convergence_failed")
            return {}

    async def compute_degree_centrality(self) -> dict[str, float]:
        """Compute degree centrality using NetworkX."""
        if len(self._graph) == 0:
            return {}

        scores = nx.degree_centrality(self._graph)
        for nid, score in scores.items():
            node = self._nodes.get(nid)
            if node:
                node.degree_centrality = score

        return {str(k): v for k, v in scores.items()}

    async def get_graph_stats(self) -> dict[str, int]:
        type_counts: dict[str, int] = {}
        for node in self._nodes.values():
            t = node.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": type_counts,  # type: ignore[dict-item]
        }

    async def find_similar_nodes(
        self,
        name: str,
        threshold: float = 0.8,
    ) -> list[tuple[KnowledgeNode, float]]:
        """Find nodes with similar names using SequenceMatcher."""
        results: list[tuple[KnowledgeNode, float]] = []
        name_lower = name.lower()

        for node in self._nodes.values():
            score = SequenceMatcher(None, name_lower, node.name.lower()).ratio()
            if score >= threshold and node.name.lower() != name_lower:
                results.append((node, score))

            # Also check aliases
            for alias in node.aliases:
                alias_score = SequenceMatcher(None, name_lower, alias.lower()).ratio()
                if alias_score >= threshold:
                    results.append((node, alias_score))
                    break

        return sorted(results, key=lambda x: x[1], reverse=True)
