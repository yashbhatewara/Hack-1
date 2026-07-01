"""
Optimize Graph use case.

Triggers knowledge graph optimization: duplicate merging,
PageRank recomputation, and centrality updates.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.knowledge.repositories import KnowledgeGraphRepository
from eng_memory_os.infrastructure.cognee.graph_optimizer import GraphOptimizer
from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class OptimizeGraphUseCase:
    """Orchestrates a full knowledge graph optimization cycle."""

    def __init__(
        self,
        graph_repo: KnowledgeGraphRepository,
        event_bus: InMemoryEventBus,
        similarity_threshold: float = 0.85,
    ) -> None:
        self._optimizer = GraphOptimizer(graph_repo, similarity_threshold)
        self._event_bus = event_bus

    async def execute(self) -> dict[str, int | bool]:
        """Run graph optimization and publish results."""
        optimization_event, merge_events = await self._optimizer.optimize()

        # Publish all events
        await self._event_bus.publish(optimization_event)
        await self._event_bus.publish_all(merge_events)

        return {
            "nodes_merged": optimization_event.nodes_merged,
            "total_nodes": optimization_event.total_nodes,
            "total_edges": optimization_event.total_edges,
            "pagerank_updated": optimization_event.pagerank_updated,
        }
