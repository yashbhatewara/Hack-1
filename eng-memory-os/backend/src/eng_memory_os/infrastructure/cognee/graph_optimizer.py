"""
Knowledge graph optimizer.

Handles graph-level optimizations:
- Duplicate node detection and merging
- Synonym resolution
- PageRank and centrality recomputation
- Stale node cleanup
"""

from __future__ import annotations

from difflib import SequenceMatcher

import structlog

from eng_memory_os.domain.knowledge.entities import KnowledgeNode
from eng_memory_os.domain.knowledge.events import GraphOptimized, NodesMerged
from eng_memory_os.domain.knowledge.repositories import KnowledgeGraphRepository
from eng_memory_os.domain.shared.events import DomainEvent

logger = structlog.get_logger(__name__)


class GraphOptimizer:
    """Optimizes the knowledge graph by merging duplicates and recomputing metrics."""

    def __init__(
        self,
        graph_repo: KnowledgeGraphRepository,
        similarity_threshold: float = 0.85,
    ) -> None:
        self._graph_repo = graph_repo
        self._similarity_threshold = similarity_threshold

    async def optimize(self) -> tuple[GraphOptimized, list[DomainEvent]]:
        """Run full graph optimization pipeline.

        Steps:
        1. Detect and merge duplicate nodes
        2. Recompute PageRank scores
        3. Recompute degree centrality
        4. Return optimization summary

        Returns:
            A tuple of (GraphOptimized event, list of NodesMerged events).
        """
        events: list[DomainEvent] = []

        # Step 1: Detect and merge duplicates
        merged_count = await self._merge_duplicates(events)

        # Step 2: Recompute PageRank
        await self._graph_repo.compute_pagerank()

        # Step 3: Recompute degree centrality
        await self._graph_repo.compute_degree_centrality()

        # Get final stats
        stats = await self._graph_repo.get_graph_stats()

        optimization_event = GraphOptimized(
            nodes_merged=merged_count,
            nodes_removed=merged_count,
            pagerank_updated=True,
            total_nodes=stats["total_nodes"],
            total_edges=stats["total_edges"],
        )

        logger.info(
            "graph_optimized",
            nodes_merged=merged_count,
            total_nodes=stats["total_nodes"],
            total_edges=stats["total_edges"],
        )

        return optimization_event, events

    async def _merge_duplicates(self, events: list[DomainEvent]) -> int:
        """Detect and merge nodes with similar names.

        Uses SequenceMatcher for fuzzy string matching to find nodes
        that likely refer to the same entity (e.g., "UserService" and "user-service").
        """
        stats = await self._graph_repo.get_graph_stats()
        total_nodes = stats["total_nodes"]

        if total_nodes < 2:
            return 0

        merged_count = 0
        processed_ids: set[str] = set()

        # Get all nodes by type (merge within types only)
        from eng_memory_os.domain.knowledge.entities import EntityType

        for entity_type in EntityType:
            nodes = await self._graph_repo.find_nodes_by_type(entity_type, limit=10000)

            # Compare all pairs within the type
            for i, node_a in enumerate(nodes):
                if str(node_a.id) in processed_ids:
                    continue

                for node_b in nodes[i + 1 :]:
                    if str(node_b.id) in processed_ids:
                        continue

                    similarity = self._compute_name_similarity(node_a, node_b)

                    if similarity >= self._similarity_threshold:
                        # Merge node_b into node_a (keep the one with more sources)
                        if len(node_a.source_memory_ids) >= len(node_b.source_memory_ids):
                            survivor, victim = node_a, node_b
                        else:
                            survivor, victim = node_b, node_a

                        survivor.merge_with(victim)
                        await self._graph_repo.save_node(survivor)
                        await self._graph_repo.delete_node(victim.id)

                        processed_ids.add(str(victim.id))
                        merged_count += 1

                        events.append(
                            NodesMerged(
                                surviving_node_id=str(survivor.id),
                                merged_node_ids=[str(victim.id)],
                                merge_reason=f"Name similarity: {similarity:.2f}",
                            )
                        )

                        logger.debug(
                            "nodes_merged",
                            survivor=survivor.name,
                            victim=victim.name,
                            similarity=similarity,
                        )

        return merged_count

    def _compute_name_similarity(
        self,
        node_a: KnowledgeNode,
        node_b: KnowledgeNode,
    ) -> float:
        """Compute the maximum name similarity between two nodes,
        considering all aliases."""
        names_a = [node_a.name.lower()] + [a.lower() for a in node_a.aliases]
        names_b = [node_b.name.lower()] + [a.lower() for a in node_b.aliases]

        max_similarity = 0.0
        for na in names_a:
            for nb in names_b:
                # Normalize: remove hyphens, underscores, spaces for comparison
                na_norm = na.replace("-", "").replace("_", "").replace(" ", "")
                nb_norm = nb.replace("-", "").replace("_", "").replace(" ", "")

                sim = SequenceMatcher(None, na_norm, nb_norm).ratio()
                max_similarity = max(max_similarity, sim)

        return max_similarity
