"""
Query Memory use case.

Receives a user query, routes it through the LangGraph agent system,
and returns the final response with citations and confidence scores.
"""

from __future__ import annotations

import time
from typing import TypedDict

import structlog

from eng_memory_os.domain.agent.entities import AgentResponse, Query
from eng_memory_os.domain.agent.events import QueryReceived, ResponseGenerated
from eng_memory_os.domain.shared.types import new_entity_id
from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class CitationDict(TypedDict):
    """Dictionary representation of a citation."""
    evidence_id: str
    memory_id: str
    source_uri: str
    relevance_score: float
    snippet: str


class QueryMemoryRequest:
    """Input for the QueryMemory use case."""

    __slots__ = ("query_text", "user_id", "mode")

    def __init__(self, query_text: str, user_id: str, mode: str = "agent") -> None:
        self.query_text = query_text
        self.user_id = user_id
        self.mode = mode


class QueryMemoryResponse:
    """Output from the QueryMemory use case."""

    __slots__ = (
        "response_id", "response_text", "confidence", "is_degraded",
        "citations", "total_time_ms", "retry_count",
    )

    def __init__(
        self,
        response_id: str,
        response_text: str,
        confidence: float,
        is_degraded: bool,
        citations: list[CitationDict],
        total_time_ms: float,
        retry_count: int,
    ) -> None:
        self.response_id = response_id
        self.response_text = response_text
        self.confidence = confidence
        self.is_degraded = is_degraded
        self.citations = citations
        self.total_time_ms = total_time_ms
        self.retry_count = retry_count


class QueryMemoryUseCase:
    """Orchestrates query execution through the agent system.

    Steps:
    1. Create Query domain object
    2. Publish QueryReceived event
    3. Execute the LangGraph agent graph
    4. Convert AgentResponse to use case response
    5. Publish ResponseGenerated event
    """

    def __init__(
        self,
        agent_graph_runner: object,  # Will be the LangGraph runner from Phase 5
        event_bus: InMemoryEventBus,
    ) -> None:
        self._agent_runner = agent_graph_runner
        self._event_bus = event_bus

    async def execute(self, request: QueryMemoryRequest) -> QueryMemoryResponse:
        """Execute a query through the full agent pipeline."""
        start_time = time.perf_counter()

        # 1. Create query
        query = Query.create(raw_text=request.query_text, user_id=request.user_id)

        # 2. Publish QueryReceived
        await self._event_bus.publish(
            QueryReceived(
                query_id=str(query.id),
                raw_text=request.query_text,
                user_id=request.user_id,
                classified_intent="pending" if request.mode == "agent" else "rag",
            )
        )

        # 3. Execute the agent graph
        agent_response: AgentResponse = await self._run_agent_graph(query, request.mode)

        total_time = (time.perf_counter() - start_time) * 1000

        # 4. Publish ResponseGenerated
        await self._event_bus.publish(
            ResponseGenerated(
                query_id=str(query.id),
                response_id=str(agent_response.id),
                is_degraded=agent_response.is_degraded,
                confidence=float(agent_response.confidence),
                total_time_ms=total_time,
                retry_count=agent_response.retry_count,
            )
        )

        logger.info(
            "query_completed",
            query_id=str(query.id),
            confidence=float(agent_response.confidence),
            is_degraded=agent_response.is_degraded,
            total_time_ms=round(total_time, 1),
            retry_count=agent_response.retry_count,
        )

        # 5. Build response
        citations: list[CitationDict] = [
            {
                "evidence_id": c.evidence_id,
                "memory_id": c.memory_id,
                "source_uri": c.source_uri,
                "relevance_score": c.relevance_score,
                "snippet": c.chunk_content[:300],
            }
            for c in agent_response.citations
        ]

        return QueryMemoryResponse(
            response_id=str(agent_response.id),
            response_text=agent_response.response_text,
            confidence=float(agent_response.confidence),
            is_degraded=agent_response.is_degraded,
            citations=citations,
            total_time_ms=total_time,
            retry_count=agent_response.retry_count,
        )

    async def _run_agent_graph(self, query: Query, mode: str = "agent") -> AgentResponse:
        """Execute the LangGraph agent graph or direct RAG runner.

        This method delegates to the agent graph runner which is injected
        from the infrastructure layer (Phase 5).
        """
        if hasattr(self._agent_runner, "run"):
            if mode == "rag" and hasattr(self._agent_runner, "run_rag"):
                return await self._agent_runner.run_rag(query)  # type: ignore[attr-defined]
            return await self._agent_runner.run(query)  # type: ignore[union-attr]

        # Fallback: if agent runner not yet wired, return insufficient evidence
        from eng_memory_os.domain.shared.types import ConfidenceScore
        return AgentResponse.create_degraded(
            query_id=query.id,
            partial_text="The agent system is not yet initialized. Please try again later.",
            citations=[],
            total_time_ms=0.0,
            retry_count=0,
            nodes_visited=[],
        )
