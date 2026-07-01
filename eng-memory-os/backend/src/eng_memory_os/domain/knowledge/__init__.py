"""Knowledge bounded context: entity extraction, relationship mapping, and graph persistence."""

from eng_memory_os.domain.knowledge.entities import (
    KnowledgeNode,
    KnowledgeEdge,
    KnowledgeGraph,
    EntityType,
    RelationshipType,
)
from eng_memory_os.domain.knowledge.value_objects import (
    NodeId,
    EdgeId,
    GraphPosition,
    EntityMention,
)
from eng_memory_os.domain.knowledge.events import (
    EntitiesExtracted,
    RelationshipsMapped,
    GraphOptimized,
    NodesMerged,
)
from eng_memory_os.domain.knowledge.repositories import (
    KnowledgeGraphRepository,
    VectorStoreRepository,
)

__all__ = [
    "KnowledgeNode",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "EntityType",
    "RelationshipType",
    "NodeId",
    "EdgeId",
    "GraphPosition",
    "EntityMention",
    "EntitiesExtracted",
    "RelationshipsMapped",
    "GraphOptimized",
    "NodesMerged",
    "KnowledgeGraphRepository",
    "VectorStoreRepository",
]
