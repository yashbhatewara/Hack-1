"""
Agent state definition for the LangGraph state graph.

This TypedDict defines the shared data structure that flows through
every node in the multi-agent system. All nodes read from and write
to this state.
"""

from __future__ import annotations

from typing import Annotated, TypedDict
import operator


class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph agent graph.

    All fields are optional (total=False) because they are populated
    progressively as the graph executes.
    """

    # --- Input ---
    query_text: str
    query_id: str
    user_id: str

    # --- Gateway Node Output ---
    classified_intent: str

    # --- Planner Node Output ---
    sub_queries: list[str]

    # --- Retriever Node Output ---
    retrieved_chunks: list[dict]       # [{content, memory_id, score, source_uri}]
    graph_neighbors: list[dict]        # [{node_id, name, type, pagerank}]
    lexical_matches: list[dict]        # [{content, memory_id, score}]
    evidence: list[dict]               # Merged & ranked evidence
    evidence_count: int

    # --- Reasoner Node Output ---
    reasoning_text: str
    citations_used: list[dict]         # [{evidence_id, memory_id, source_uri, score}]

    # --- Critic Node Output ---
    confidence_score: float
    hallucination_detected: bool
    critic_feedback: str
    refined_query: str

    # --- Control Flow ---
    loop_count: int
    max_loops: int
    should_retry: bool

    # --- Generator Node Output ---
    final_response: str
    is_degraded: bool

    # --- Execution Trace ---
    nodes_visited: Annotated[list[str], operator.add]
    total_time_ms: float
