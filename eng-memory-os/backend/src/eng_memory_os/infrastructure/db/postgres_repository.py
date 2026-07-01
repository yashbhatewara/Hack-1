"""
PostgreSQL implementation of the MemoryRepository.

Translates between domain entities and SQLAlchemy ORM models,
handling all persistence operations for the Memory bounded context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from eng_memory_os.domain.memory.entities import Memory, MemorySource, MemoryStatus
from eng_memory_os.domain.memory.repositories import MemoryRepository
from eng_memory_os.domain.memory.value_objects import (
    MemoryChunk,
    MemoryId,
    Provenance,
    SourceUri,
)
from eng_memory_os.domain.shared.types import (
    ConfidenceScore,
    DecayFactor,
    EntityId,
    ImportanceScore,
    Timestamp,
)
from eng_memory_os.infrastructure.db.models import MemoryChunkModel, MemoryModel


class PostgresMemoryRepository(MemoryRepository):
    """PostgreSQL-backed implementation of the MemoryRepository interface."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, memory: Memory) -> None:
        """Upsert a Memory aggregate (insert or update)."""
        existing = await self._session.get(MemoryModel, memory.id.value)

        if existing:
            # Update existing record
            existing.source_uri = str(memory.source_uri)
            existing.source_type = memory.source_type.value
            existing.raw_content = memory.raw_content
            existing.author = memory.author
            existing.title = memory.title
            existing.importance_score = float(memory.importance_score)
            existing.confidence_score = float(memory.confidence_score)
            existing.decay_factor = float(memory.decay_factor)
            existing.provenance_algorithm = memory.provenance.hash_algorithm
            existing.provenance_hash = memory.provenance.hash_value
            existing.status = memory.status.value
            existing.updated_at = memory.updated_at
            existing.last_accessed_at = memory.last_accessed_at
            existing.access_count = memory.access_count
            existing.tags = memory.tags
        else:
            # Insert new record
            model = MemoryModel(
                id=memory.id.value,
                source_uri=str(memory.source_uri),
                source_type=memory.source_type.value,
                raw_content=memory.raw_content,
                author=memory.author,
                title=memory.title,
                importance_score=float(memory.importance_score),
                confidence_score=float(memory.confidence_score),
                decay_factor=float(memory.decay_factor),
                provenance_algorithm=memory.provenance.hash_algorithm,
                provenance_hash=memory.provenance.hash_value,
                status=memory.status.value,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                last_accessed_at=memory.last_accessed_at,
                access_count=memory.access_count,
                tags=memory.tags,
            )
            self._session.add(model)

        # Upsert chunks
        await self._save_chunks(memory)

    async def _save_chunks(self, memory: Memory) -> None:
        """Persist memory chunks (delete old, insert new)."""
        # Delete existing chunks for this memory
        await self._session.execute(
            delete(MemoryChunkModel).where(
                MemoryChunkModel.memory_id == memory.id.value
            )
        )

        # Insert new chunks
        for chunk in memory.chunks:
            chunk_model = MemoryChunkModel(
                id=chunk.chunk_id,
                memory_id=chunk.memory_id,
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
            )
            self._session.add(chunk_model)

    async def get_by_id(self, memory_id: MemoryId) -> Memory | None:
        """Retrieve a Memory by its ID, including chunks."""
        model = await self._session.get(MemoryModel, memory_id.value)
        if model is None:
            return None

        chunks = await self._load_chunks(memory_id.value)
        return self._to_domain(model, chunks)

    async def find_by_status(
        self,
        status: MemoryStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        result = await self._session.execute(
            select(MemoryModel)
            .where(MemoryModel.status == status.value)
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def find_by_source_uri(self, source_uri: str) -> Memory | None:
        result = await self._session.execute(
            select(MemoryModel).where(MemoryModel.source_uri == source_uri)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_author(
        self,
        author: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        result = await self._session.execute(
            select(MemoryModel)
            .where(MemoryModel.author == author)
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def find_stale(
        self,
        decay_threshold: float = 0.3,
        limit: int = 100,
    ) -> list[Memory]:
        result = await self._session.execute(
            select(MemoryModel)
            .where(
                MemoryModel.status.in_(["active", "stale"]),
                MemoryModel.decay_factor < decay_threshold,
            )
            .order_by(MemoryModel.decay_factor.asc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def find_for_decay(self, batch_size: int = 500) -> list[Memory]:
        result = await self._session.execute(
            select(MemoryModel)
            .where(MemoryModel.status == "active")
            .order_by(MemoryModel.updated_at.asc())
            .limit(batch_size)
        )
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def search_by_tags(self, tags: list[str], limit: int = 50) -> list[Memory]:
        result = await self._session.execute(
            select(MemoryModel)
            .where(MemoryModel.tags.overlap(tags))  # type: ignore[attr-defined]
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def count_by_status(self) -> dict[MemoryStatus, int]:
        result = await self._session.execute(
            select(MemoryModel.status, func.count(MemoryModel.id))
            .group_by(MemoryModel.status)
        )
        counts: dict[MemoryStatus, int] = {}
        for status_str, count in result.all():
            try:
                counts[MemoryStatus(status_str)] = count
            except ValueError:
                pass
        return counts

    async def delete(self, memory_id: MemoryId) -> bool:
        # Delete chunks first
        await self._session.execute(
            delete(MemoryChunkModel).where(
                MemoryChunkModel.memory_id == memory_id.value
            )
        )
        result = await self._session.execute(
            delete(MemoryModel).where(MemoryModel.id == memory_id.value)
        )
        return result.rowcount > 0  # type: ignore[union-attr]

    async def list_recent(
        self,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        query = select(MemoryModel).order_by(MemoryModel.updated_at.desc())
        if since:
            query = query.where(MemoryModel.updated_at >= since)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    # --- Private helpers ---

    async def _load_chunks(self, memory_id: uuid.UUID) -> list[MemoryChunk]:
        """Load all chunks for a memory, ordered by index."""
        result = await self._session.execute(
            select(MemoryChunkModel)
            .where(MemoryChunkModel.memory_id == memory_id)
            .order_by(MemoryChunkModel.chunk_index)
        )
        chunk_models = result.scalars().all()
        return [
            MemoryChunk(
                chunk_id=EntityId(cm.id),
                memory_id=EntityId(cm.memory_id),
                content=cm.content,
                chunk_index=cm.chunk_index,
                token_count=cm.token_count,
                embedding_vector=None,  # Vectors are stored in Qdrant, not Postgres
            )
            for cm in chunk_models
        ]

    def _to_domain(
        self,
        model: MemoryModel,
        chunks: list[MemoryChunk] | None = None,
    ) -> Memory:
        """Convert an ORM model to a domain entity."""
        return Memory(
            id=MemoryId(value=EntityId(model.id)),
            source_uri=SourceUri(model.source_uri),
            source_type=MemorySource(model.source_type),
            raw_content=model.raw_content,
            author=model.author,
            title=model.title,
            importance_score=ImportanceScore(model.importance_score),
            confidence_score=ConfidenceScore(model.confidence_score),
            decay_factor=DecayFactor(model.decay_factor),
            provenance=Provenance(
                hash_algorithm=model.provenance_algorithm,
                hash_value=model.provenance_hash,
            ),
            status=MemoryStatus(model.status),
            created_at=Timestamp(model.created_at),
            updated_at=Timestamp(model.updated_at),
            last_accessed_at=Timestamp(model.last_accessed_at) if model.last_accessed_at else None,
            access_count=model.access_count,
            chunks=chunks or [],
            tags=list(model.tags) if model.tags else [],
        )
