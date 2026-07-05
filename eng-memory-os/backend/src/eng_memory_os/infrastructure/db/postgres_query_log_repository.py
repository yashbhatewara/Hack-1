from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eng_memory_os.infrastructure.db.models import QueryLogModel


class PostgresQueryLogRepository:
    """Handles persistence and retrieval of query logs in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        user_id_str: str,
        raw_query: str,
        classified_intent: str,
        response_text: str,
        confidence: float,
        is_degraded: bool,
        total_time_ms: float,
        retry_count: int,
    ) -> QueryLogModel:
        # Generate a deterministic UUID if the string is not a valid UUID format
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            user_id = uuid.uuid5(uuid.NAMESPACE_DNS, user_id_str)

        log = QueryLogModel(
            user_id=user_id,
            raw_query=raw_query,
            classified_intent=classified_intent,
            response_text=response_text,
            confidence=confidence,
            is_degraded=is_degraded,
            total_time_ms=total_time_ms,
            retry_count=retry_count,
        )
        self._session.add(log)
        # Flush to generate ID, commit is handled by context manager or session transaction
        await self._session.flush()
        return log

    async def list_history(
        self,
        user_id_str: str,
        limit: int = 20,
    ) -> list[dict]:
        # Note: no user_id filter — all queries belong to the same anonymous user
        # until authentication is wired up.
        stmt = (
            select(QueryLogModel)
            .order_by(QueryLogModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "raw_query": m.raw_query,
                "classified_intent": m.classified_intent,
                "response_text": m.response_text,
                "confidence": m.confidence,
                "is_degraded": m.is_degraded,
                "total_time_ms": m.total_time_ms,
                "retry_count": m.retry_count,
                "created_at": m.created_at.isoformat(),
            }
            for m in models
        ]
