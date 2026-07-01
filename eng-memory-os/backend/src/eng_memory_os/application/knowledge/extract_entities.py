"""
Extract Entities use case.

Drives the Cognee entity extraction pipeline: takes a memory's content,
extracts entities and relationships, persists them to the knowledge graph.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.knowledge.events import EntitiesExtracted, RelationshipsMapped
from eng_memory_os.domain.knowledge.repositories import KnowledgeGraphRepository
from eng_memory_os.domain.memory.repositories import MemoryRepository
from eng_memory_os.domain.memory.value_objects import MemoryId
from eng_memory_os.infrastructure.cognee.entity_extractor import EntityExtractor
from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class ExtractEntitiesUseCase:
    """Extracts engineering entities from a memory and persists them to the graph.

    Steps:
    1. Load the memory by ID
    2. Run entity extraction on each chunk (or raw content)
    3. Save extracted nodes to the knowledge graph
    4. Save extracted edges to the knowledge graph
    5. Publish EntitiesExtracted and RelationshipsMapped events
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        graph_repo: KnowledgeGraphRepository,
        entity_extractor: EntityExtractor,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._memory_repo = memory_repo
        self._graph_repo = graph_repo
        self._extractor = entity_extractor
        self._event_bus = event_bus

    async def execute(self, memory_id: str) -> dict[str, int]:
        """Execute entity extraction for a specific memory.

        Returns a summary of extracted entities and relationships.
        """
        memory = await self._memory_repo.get_by_id(MemoryId.from_str(memory_id))
        if memory is None:
            logger.warning("memory_not_found_for_extraction", memory_id=memory_id)
            return {"entities": 0, "relationships": 0}

        total_nodes = 0
        total_edges = 0
        all_node_ids: list[str] = []
        all_edge_ids: list[str] = []
        entity_type_counts: dict[str, int] = {}

        # Extract from each chunk if available, otherwise from raw content
        contents = (
            [(c.content, c.chunk_index) for c in memory.chunks]
            if memory.chunks
            else [(memory.raw_content, 0)]
        )

        for content, chunk_index in contents:
            nodes, edges = await self._extractor.extract(
                content=content,
                source_memory_id=memory_id,
                chunk_index=chunk_index,
            )

            # Check for existing nodes with similar names and merge if needed
            for node in nodes:
                existing = await self._graph_repo.find_nodes_by_name(
                    node.name, entity_type=node.entity_type, fuzzy=True
                )
                if existing:
                    # Merge into existing node
                    existing[0].merge_with(node)
                    await self._graph_repo.save_node(existing[0])
                    all_node_ids.append(str(existing[0].id))
                else:
                    await self._graph_repo.save_node(node)
                    all_node_ids.append(str(node.id))

                # Count by type
                t = node.entity_type.value
                entity_type_counts[t] = entity_type_counts.get(t, 0) + 1
                total_nodes += 1

            for _src_name, _tgt_name, edge in edges:
                await self._graph_repo.save_edge(edge)
                all_edge_ids.append(str(edge.id))
                total_edges += 1

        # Publish events
        await self._event_bus.publish(
            EntitiesExtracted(
                memory_id=memory_id,
                node_ids=all_node_ids,
                entity_count=total_nodes,
                entity_types=entity_type_counts,
            )
        )

        if total_edges > 0:
            await self._event_bus.publish(
                RelationshipsMapped(
                    memory_id=memory_id,
                    edge_ids=all_edge_ids,
                    relationship_count=total_edges,
                )
            )

        logger.info(
            "entities_extracted",
            memory_id=memory_id,
            entities=total_nodes,
            relationships=total_edges,
        )

        return {"entities": total_nodes, "relationships": total_edges}
