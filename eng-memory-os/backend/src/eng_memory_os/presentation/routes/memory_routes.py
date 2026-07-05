"""
Memory REST API routes.

Endpoints for ingesting, querying, listing, and managing memories.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from eng_memory_os.application.memory.ingest_memory import (
    IngestMemoryRequest,
    IngestMemoryUseCase,
)
from eng_memory_os.application.memory.query_memory import (
    QueryMemoryRequest,
    QueryMemoryUseCase,
)
from eng_memory_os.domain.memory.entities import MemoryStatus
from eng_memory_os.domain.memory.value_objects import MemoryId
from eng_memory_os.presentation.dependencies import (
    get_agent_runner,
    get_event_bus,
    get_memory_repo,
)
from eng_memory_os.presentation.schemas import (
    IngestMemoryRequestDTO,
    IngestMemoryResponseDTO,
    MemoryDTO,
    MemoryListResponseDTO,
    MemoryStatsDTO,
    MemoryStatusDTO,
    QueryRequestDTO,
    QueryResponseDTO,
    CitationDTO,
    ErrorResponseDTO,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


# ──────────────────── POST /memories ────────────────────

@router.post(
    "",
    response_model=IngestMemoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new memory",
    description="Accepts raw engineering content and creates a new memory. "
                "Triggers the async processing pipeline (chunking, entity extraction, vectorization).",
    responses={
        409: {"model": ErrorResponseDTO, "description": "Duplicate source URI"},
        422: {"model": ErrorResponseDTO, "description": "Validation error"},
    },
)
async def ingest_memory(
    body: IngestMemoryRequestDTO,
    memory_repo=Depends(get_memory_repo),
    event_bus=Depends(get_event_bus),
):
    use_case = IngestMemoryUseCase(memory_repo=memory_repo, event_bus=event_bus)

    request = IngestMemoryRequest(
        raw_content=body.raw_content,
        source_uri=body.source_uri,
        source_type=body.source_type.value,
        author=body.author,
        title=body.title,
        tags=body.tags,
    )

    result = await use_case.execute(request)

    return IngestMemoryResponseDTO(
        memory_id=result.memory_id,
        status=MemoryStatusDTO(result.status),
        importance_score=result.importance_score,
    )


# ──────────────────── POST /memories/query ────────────────────

@router.post(
    "/query",
    response_model=QueryResponseDTO,
    summary="Query the engineering knowledge base",
    description="Sends a natural language query through the multi-agent pipeline "
                "(Gateway → Planner → Retriever → Reasoner → Critic → Generator).",
    responses={
        503: {"model": ErrorResponseDTO, "description": "Agent system unavailable"},
    },
)
async def query_memories(
    body: QueryRequestDTO,
    agent_runner=Depends(get_agent_runner),
    event_bus=Depends(get_event_bus),
):
    use_case = QueryMemoryUseCase(agent_graph_runner=agent_runner, event_bus=event_bus)

    request = QueryMemoryRequest(
        query_text=body.query,
        user_id="api-user",  # TODO: Extract from JWT when auth is wired
        mode=body.mode,
    )

    result = await use_case.execute(request)

    # Persist the query log in the database
    try:
        from eng_memory_os.presentation.dependencies import get_db_session
        from eng_memory_os.infrastructure.db.postgres_query_log_repository import PostgresQueryLogRepository
        async with get_db_session() as session:
            repo = PostgresQueryLogRepository(session)
            await repo.save(
                user_id_str="api-user",
                raw_query=body.query,
                classified_intent=body.mode,
                response_text=result.response_text,
                confidence=result.confidence,
                is_degraded=result.is_degraded,
                total_time_ms=result.total_time_ms,
                retry_count=result.retry_count,
            )
    except Exception as e:
        logger.warning("query_log_persist_failed", error=str(e))

    citations = [
        CitationDTO(
            evidence_id=c["evidence_id"],
            memory_id=c["memory_id"],
            source_uri=c["source_uri"],
            relevance_score=c["relevance_score"],
            snippet=c["snippet"],
        )
        for c in result.citations
    ]

    return QueryResponseDTO(
        response_id=result.response_id,
        response_text=result.response_text,
        confidence=result.confidence,
        is_degraded=result.is_degraded,
        citations=citations,
        total_time_ms=result.total_time_ms,
        retry_count=result.retry_count,
    )


# ──────────────────── GET /memories/query/history ────────────────────

@router.get(
    "/query/history",
    summary="Get recent query history for the user",
    description="Returns a list of the most recent queries asked by the user.",
)
async def query_history(
    limit: int = Query(100, ge=1, le=500),
):
    try:
        from eng_memory_os.presentation.dependencies import get_db_session
        from eng_memory_os.infrastructure.db.postgres_query_log_repository import PostgresQueryLogRepository
        async with get_db_session() as session:
            repo = PostgresQueryLogRepository(session)
            history = await repo.list_history(user_id_str="api-user", limit=limit)
            return history
    except Exception as e:
        logger.exception("get_query_history_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve query history: {e}",
        )


# ──────────────────── GET /memories ────────────────────

@router.get(
    "",
    response_model=MemoryListResponseDTO,
    summary="List memories",
    description="Returns a paginated list of memories, optionally filtered by status.",
)
async def list_memories(
    status_filter: MemoryStatusDTO | None = Query(None, alias="status", description="Filter by status"),
    author: str | None = Query(None, description="Filter by author"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    memory_repo=Depends(get_memory_repo),
):
    if status_filter:
        memories = await memory_repo.find_by_status(
            MemoryStatus(status_filter.value), limit=limit, offset=offset
        )
    elif author:
        memories = await memory_repo.find_by_author(author, limit=limit, offset=offset)
    else:
        memories = await memory_repo.list_recent(limit=limit, offset=offset)

    items = [
        MemoryDTO(
            id=str(m.id),
            source_uri=str(m.source_uri),
            source_type=m.source_type.value,
            title=m.title,
            author=m.author,
            raw_content=m.raw_content[:500],  # Truncate for list view
            importance_score=float(m.importance_score),
            confidence_score=float(m.confidence_score),
            decay_factor=float(m.decay_factor),
            status=MemoryStatusDTO(m.status.value),
            tags=m.tags,
            access_count=m.access_count,
            created_at=m.created_at,
            updated_at=m.updated_at,
            last_accessed_at=m.last_accessed_at,
        )
        for m in memories
    ]

    return MemoryListResponseDTO(
        items=items,
        total=len(items),
        offset=offset,
        limit=limit,
    )


# ──────────────────── GET /memories/{id} ────────────────────

@router.get(
    "/{memory_id}",
    response_model=MemoryDTO,
    summary="Get a specific memory",
    responses={404: {"model": ErrorResponseDTO}},
)
async def get_memory(
    memory_id: str,
    memory_repo=Depends(get_memory_repo),
):
    memory = await memory_repo.get_by_id(MemoryId.from_str(memory_id))
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

    # Record access
    memory.record_access()
    await memory_repo.save(memory)

    return MemoryDTO(
        id=str(memory.id),
        source_uri=str(memory.source_uri),
        source_type=memory.source_type.value,
        title=memory.title,
        author=memory.author,
        raw_content=memory.raw_content,
        importance_score=float(memory.importance_score),
        confidence_score=float(memory.confidence_score),
        decay_factor=float(memory.decay_factor),
        status=MemoryStatusDTO(memory.status.value),
        tags=memory.tags,
        access_count=memory.access_count,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        last_accessed_at=memory.last_accessed_at,
    )


# ──────────────────── DELETE /memories/{id} ────────────────────

@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory",
    responses={404: {"model": ErrorResponseDTO}},
)
async def delete_memory(
    memory_id: str,
    memory_repo=Depends(get_memory_repo),
):
    deleted = await memory_repo.delete(MemoryId.from_str(memory_id))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")


# ──────────────────── GET /memories/stats ────────────────────

@router.get(
    "/stats/summary",
    response_model=MemoryStatsDTO,
    summary="Get memory statistics",
)
async def get_memory_stats(
    memory_repo=Depends(get_memory_repo),
):
    counts = await memory_repo.count_by_status()
    total = sum(counts.values())

    # Count total queries from database
    total_queries = 0
    try:
        from sqlalchemy import select, func
        from eng_memory_os.infrastructure.db.models import QueryLogModel
        from eng_memory_os.presentation.dependencies import get_db_session
        async with get_db_session() as session:
            result = await session.execute(select(func.count(QueryLogModel.id)))
            total_queries = result.scalar() or 0
    except Exception:
        logger.exception("failed_to_count_query_logs")

    return MemoryStatsDTO(
        pending=counts.get(MemoryStatus.PENDING, 0),
        processing=counts.get(MemoryStatus.PROCESSING, 0),
        active=counts.get(MemoryStatus.ACTIVE, 0),
        stale=counts.get(MemoryStatus.STALE, 0),
        archived=counts.get(MemoryStatus.ARCHIVED, 0),
        failed=counts.get(MemoryStatus.FAILED, 0),
        total=total,
        total_queries=total_queries,
    )
