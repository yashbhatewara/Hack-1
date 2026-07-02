"""
Abstract repository interfaces for the Knowledge bounded context.

Defines contracts for both graph storage (KnowledgeGraphRepository)
and vector storage (VectorStoreRepository).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict

from eng_memory_os.domain.knowledge.entities import (
    EntityType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    RelationshipType,
)
from eng_memory_os.domain.knowledge.value_objects import NodeId
from eng_memory_os.domain.memory.value_objects import MemoryChunk


class GraphStats(TypedDict):
    total_nodes: int
    total_edges: int
    nodes_by_type: dict[str, int]


class KnowledgeGraphRepository(ABC):
    """Abstract repository for knowledge graph persistence.

    Implementations may use NetworkX (in-memory), Neo4j, or Cognee's
    built-in graph backend.
    """

    @abstractmethod
    async def save_node(self, node: KnowledgeNode) -> None:
        """Persist a knowledge node. Upsert semantics."""
        ...

    @abstractmethod
    async def save_edge(self, edge: KnowledgeEdge) -> None:
        """Persist a knowledge edge. Upsert semantics."""
        ...

    @abstractmethod
    async def get_node_by_id(self, node_id: NodeId) -> KnowledgeNode | None:
        """Retrieve a node by its unique identifier."""
        ...

    @abstractmethod
    async def find_nodes_by_name(
        self,
        name: str,
        entity_type: EntityType | None = None,
        fuzzy: bool = False,
    ) -> list[KnowledgeNode]:
        """Find nodes matching a name query, optionally filtered by type.

        If fuzzy=True, perform approximate string matching for typo tolerance.
        """
        ...

    @abstractmethod
    async def find_nodes_by_type(
        self,
        entity_type: EntityType,
        limit: int = 100,
    ) -> list[KnowledgeNode]:
        """Find all nodes of a given entity type."""
        ...

    @abstractmethod
    async def find_nodes_by_memory_id(self, memory_id: str) -> list[KnowledgeNode]:
        """Find all nodes that were extracted from a specific memory."""
        ...

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: NodeId,
        depth: int = 1,
        relationship_types: list[RelationshipType] | None = None,
    ) -> KnowledgeGraph:
        """Get a subgraph of N-degree neighbors around a node.

        Optionally filter by relationship types.
        Returns a KnowledgeGraph containing the nodes and edges.
        """
        ...

    @abstractmethod
    async def get_edges_between(
        self,
        source_id: NodeId,
        target_id: NodeId,
    ) -> list[KnowledgeEdge]:
        """Find all edges between two specific nodes."""
        ...

    @abstractmethod
    async def get_full_subgraph(
        self,
        node_ids: list[NodeId],
    ) -> KnowledgeGraph:
        """Load a subgraph containing all specified nodes and edges between them."""
        ...

    @abstractmethod
    async def delete_node(self, node_id: NodeId) -> bool:
        """Delete a node and all its connected edges."""
        ...

    @abstractmethod
    async def compute_pagerank(self) -> dict[str, float]:
        """Compute PageRank scores for all nodes in the graph.

        Returns a mapping of node_id -> pagerank_score.
        """
        ...

    @abstractmethod
    async def compute_degree_centrality(self) -> dict[str, float]:
        """Compute degree centrality for all nodes.

        Returns a mapping of node_id -> centrality_score.
        """
        ...

    @abstractmethod
    async def get_graph_stats(self) -> GraphStats:
        """Return aggregate statistics about the knowledge graph.

        Keys: total_nodes, total_edges, nodes_by_type (nested dict).
        """
        ...

    @abstractmethod
    async def find_similar_nodes(
        self,
        name: str,
        threshold: float = 0.8,
    ) -> list[tuple[KnowledgeNode, float]]:
        """Find nodes with similar names for deduplication.

        Returns list of (node, similarity_score) tuples.
        """
        ...


class VectorStoreRepository(ABC):
    """Abstract repository for vector embeddings storage.

    Implementations use Qdrant, Milvus, or other vector databases.
    """

    @abstractmethod
    async def upsert_chunks(self, chunks: list[MemoryChunk]) -> int:
        """Store chunk embeddings in the vector database.

        Returns the number of chunks successfully stored.
        Chunks must have embedding_vector set (non-None).
        """
        ...

    @abstractmethod
    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.5,
        filter_memory_ids: list[str] | None = None,
    ) -> list[tuple[MemoryChunk, float]]:
        """Find chunks with similar embedding vectors.

        Returns list of (chunk, similarity_score) tuples, ordered by
        descending similarity.

        Args:
            query_vector: The query embedding vector.
            limit: Maximum number of results.
            score_threshold: Minimum similarity score to include.
            filter_memory_ids: Optional filter to restrict to specific memories.
        """
        ...

    @abstractmethod
    async def delete_by_memory_id(self, memory_id: str) -> int:
        """Delete all chunks belonging to a specific memory.

        Returns the number of chunks deleted.
        """
        ...

    @abstractmethod
    async def get_collection_stats(self) -> dict[str, int]:
        """Return statistics about the vector collection.

        Keys: total_vectors, indexed_vectors, etc.
        """
        ...

    @abstractmethod
    async def ensure_collection(self, vector_dimension: int) -> None:
        """Ensure the vector collection exists with the correct schema.

        Creates the collection if it doesn't exist, or validates the
        existing collection's configuration.
        """
        ...
