"""
LangGraph Agent Graph Builder and Runner.

Compiles the 6-node multi-agent state graph with conditional edges:
  Gateway → Planner → Retriever → Reasoner → Critic
                                              ↓ (retry?)
                                        ↻ Planner (if should_retry and loop < 3)
                                        → Generator (if done or max retries)

The Critic→Planner loop implements the "criticize, refine, retry"
anti-hallucination cycle from the master prompt.
"""

from __future__ import annotations

import time

import structlog
from langgraph.graph import END, StateGraph

from eng_memory_os.domain.agent.entities import AgentResponse, Citation, Query
from eng_memory_os.domain.knowledge.repositories import (
    KnowledgeGraphRepository,
    VectorStoreRepository,
)
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.domain.shared.types import ConfidenceScore, new_entity_id, now_utc
from eng_memory_os.infrastructure.db.vector.embedding_service import EmbeddingService
from eng_memory_os.infrastructure.langgraph.nodes.critic_node import CriticNode
from eng_memory_os.infrastructure.langgraph.nodes.gateway_node import GatewayNode
from eng_memory_os.infrastructure.langgraph.nodes.generator_node import GeneratorNode
from eng_memory_os.infrastructure.langgraph.nodes.planner_node import PlannerNode
from eng_memory_os.infrastructure.langgraph.nodes.reasoner_node import ReasonerNode
from eng_memory_os.infrastructure.langgraph.nodes.retriever_node import RetrieverNode
from eng_memory_os.infrastructure.langgraph.state import AgentState

logger = structlog.get_logger(__name__)


def _critic_router(state: AgentState) -> str:
    """Route from Critic: retry or generate final response."""
    if state.get("should_retry", False):
        return "planner"
    return "generator"


class AgentGraphBuilder:
    """Builds and compiles the LangGraph state graph."""

    def __init__(
        self,
        llm_gateway: LLMGateway,
        vector_store: VectorStoreRepository,
        graph_repo: KnowledgeGraphRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self._llm = llm_gateway
        self._vector_store = vector_store
        self._graph_repo = graph_repo
        self._embedding_service = embedding_service

    def build(self) -> StateGraph:
        """Build and compile the agent graph.

        Graph structure:
          gateway → planner → retriever → reasoner → critic
          critic → planner (if should_retry=True and loop_count < max_loops)
          critic → generator (if should_retry=False or loop_count >= max_loops)
          generator → END
        """
        # Instantiate nodes
        gateway = GatewayNode(self._llm)
        planner = PlannerNode(self._llm)
        retriever = RetrieverNode(self._vector_store, self._graph_repo, self._embedding_service)
        reasoner = ReasonerNode(self._llm)
        critic = CriticNode(self._llm)
        generator = GeneratorNode()

        # Build the state graph
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("gateway", gateway)
        graph.add_node("planner", planner)
        graph.add_node("retriever", retriever)
        graph.add_node("reasoner", reasoner)
        graph.add_node("critic", critic)
        graph.add_node("generator", generator)

        # Set entry point
        graph.set_entry_point("gateway")

        # Add edges
        graph.add_edge("gateway", "planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "reasoner")
        graph.add_edge("reasoner", "critic")

        # Conditional edge from critic
        graph.add_conditional_edges(
            "critic",
            _critic_router,
            {
                "planner": "planner",
                "generator": "generator",
            },
        )

        graph.add_edge("generator", END)

        return graph


class AgentGraphRunner:
    """Runs the compiled agent graph for a given query.

    Used by the QueryMemoryUseCase to execute queries through
    the full multi-agent pipeline.
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        vector_store: VectorStoreRepository,
        graph_repo: KnowledgeGraphRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        builder = AgentGraphBuilder(
            llm_gateway=llm_gateway,
            vector_store=vector_store,
            graph_repo=graph_repo,
            embedding_service=embedding_service,
        )
        graph = builder.build()
        self._compiled_graph = graph.compile()

    async def run(self, query: Query) -> AgentResponse:
        """Execute the agent graph for a given query and return an AgentResponse."""
        start_time = time.perf_counter()

        # Prepare initial state
        initial_state: AgentState = {
            "query_text": query.raw_text,
            "query_id": str(query.id),
            "user_id": query.user_id,
        }

        # Execute the graph
        final_state = await self._compiled_graph.ainvoke(initial_state)

        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Build citations from the state
        citations = self._build_citations(final_state)

        # Build the AgentResponse
        is_degraded = final_state.get("is_degraded", False)
        confidence = ConfidenceScore(final_state.get("confidence_score", 0.0))
        response_text = final_state.get("final_response", "")
        nodes_visited = final_state.get("nodes_visited", [])
        retry_count = final_state.get("loop_count", 0)

        if is_degraded:
            return AgentResponse.create_degraded(
                query_id=query.id,
                partial_text=response_text,
                citations=citations,
                total_time_ms=total_time_ms,
                retry_count=retry_count,
                nodes_visited=nodes_visited,
            )

        return AgentResponse.create_success(
            query_id=query.id,
            response_text=response_text,
            confidence=confidence,
            citations=citations,
            total_time_ms=total_time_ms,
            retry_count=retry_count,
            nodes_visited=nodes_visited,
        )

    @staticmethod
    def _build_citations(state: dict) -> list[Citation]:
        """Convert state citations to domain Citation objects."""
        citations: list[Citation] = []
        for c in state.get("citations_used", []):
            citations.append(
                Citation(
                    evidence_id=c.get("evidence_id", ""),
                    memory_id=c.get("memory_id", ""),
                    source_uri=c.get("source_uri", ""),
                    chunk_content=c.get("content", ""),
                    relevance_score=c.get("relevance_score", 0.0),
                )
            )
        return citations
