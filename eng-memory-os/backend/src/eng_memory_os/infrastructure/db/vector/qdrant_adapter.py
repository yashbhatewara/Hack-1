"""
Qdrant vector store implementation.

Implements the VectorStoreRepository interface using the Qdrant client.
Handles collection management, chunk upsert, and similarity search.
"""

from __future__ import annotations

import uuid

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from eng_memory_os.domain.knowledge.repositories import VectorStoreRepository
from eng_memory_os.domain.memory.value_objects import MemoryChunk
from eng_memory_os.domain.shared.types import EntityId

logger = structlog.get_logger(__name__)


class QdrantVectorStoreAdapter(VectorStoreRepository):
    """Qdrant-backed implementation of the VectorStoreRepository."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "eng_memory_chunks",
    ) -> None:
        self._client = AsyncQdrantClient(host=host, port=port)
        self._collection_name = collection_name

    async def ensure_collection(self, vector_dimension: int) -> None:
        """Create the Qdrant collection if it doesn't exist."""
        collections = await self._client.get_collections()
        existing_names = [c.name for c in collections.collections]

        if self._collection_name not in existing_names:
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=vector_dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "qdrant_collection_created",
                collection=self._collection_name,
                dimension=vector_dimension,
            )
        else:
            logger.info(
                "qdrant_collection_exists",
                collection=self._collection_name,
            )

    async def upsert_chunks(self, chunks: list[MemoryChunk]) -> int:
        """Store chunk embeddings in Qdrant.

        Only chunks with non-None embedding vectors are stored.
        Returns the count of successfully upserted chunks.
        """
        points: list[PointStruct] = []

        for chunk in chunks:
            if chunk.embedding_vector is None:
                logger.warning(
                    "chunk_missing_embedding",
                    chunk_id=str(chunk.chunk_id),
                    memory_id=str(chunk.memory_id),
                )
                continue

            point = PointStruct(
                id=str(chunk.chunk_id),
                vector=chunk.embedding_vector,
                payload={
                    "memory_id": str(chunk.memory_id),
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                },
            )
            points.append(point)

        if not points:
            return 0

        # Qdrant supports batch upserts efficiently
        batch_size = 100
        upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )
            upserted += len(batch)

        logger.info(
            "chunks_upserted",
            count=upserted,
            collection=self._collection_name,
        )
        return upserted

    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.5,
        filter_memory_ids: list[str] | None = None,
    ) -> list[tuple[MemoryChunk, float]]:
        """Find chunks with similar embedding vectors."""
        query_filter = None
        if filter_memory_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="memory_id",
                        match=MatchValue(value=mid),
                    )
                    for mid in filter_memory_ids
                ]
            )

        response = await self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        results = response.points

        chunks_with_scores: list[tuple[MemoryChunk, float]] = []
        for hit in results:
            payload = hit.payload or {}
            chunk = MemoryChunk(
                chunk_id=EntityId(uuid.UUID(str(hit.id))),
                memory_id=EntityId(uuid.UUID(payload.get("memory_id", ""))),
                content=payload.get("content", ""),
                chunk_index=payload.get("chunk_index", 0),
                token_count=payload.get("token_count", 0),
                embedding_vector=None,  # Don't return vectors in search results
            )
            chunks_with_scores.append((chunk, hit.score))

        return chunks_with_scores

    async def delete_by_memory_id(self, memory_id: str) -> int:
        """Delete all chunks belonging to a specific memory."""
        # Get count before deletion
        count_before = await self._count_by_memory_id(memory_id)

        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="memory_id",
                        match=MatchValue(value=memory_id),
                    )
                ]
            ),
        )

        logger.info(
            "chunks_deleted",
            memory_id=memory_id,
            count=count_before,
        )
        return count_before

    async def get_collection_stats(self) -> dict[str, int]:
        """Return statistics about the vector collection."""
        try:
            info = await self._client.get_collection(self._collection_name)
            return {
                "total_vectors": info.points_count or 0,
                "indexed_vectors": info.indexed_vectors_count or 0,
                "segments": info.segments_count or 0,
            }
        except Exception:
            return {"total_vectors": 0, "indexed_vectors": 0, "segments": 0}

    async def _count_by_memory_id(self, memory_id: str) -> int:
        """Count chunks for a specific memory (for deletion tracking)."""
        try:
            result = await self._client.count(
                collection_name=self._collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="memory_id",
                            match=MatchValue(value=memory_id),
                        )
                    ]
                ),
            )
            return result.count
        except Exception:
            return 0

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        await self._client.close()
