"""
Agent domain entities.

Defines the data structures that flow through the LangGraph multi-agent
system: queries, retrieval results, reasoning results, citations,
and the final agent response.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from eng_memory_os.domain.shared.types import (
    ConfidenceScore,
    EntityId,
    Timestamp,
    new_entity_id,
    now_utc,
)


class QueryIntent(enum.StrEnum):
    """Classified intent of an incoming query."""

    SEARCH = "search"                   # Find specific information
    EXPLAIN = "explain"                 # Explain a concept or decision
    COMPARE = "compare"                 # Compare approaches or components
    TIMELINE = "timeline"               # Get chronological history
    IMPACT_ANALYSIS = "impact_analysis" # Assess impact of a change
    ROOT_CAUSE = "root_cause"           # Root cause analysis for incidents
    SUMMARIZE = "summarize"             # Summarize a topic or period
    INGEST = "ingest"                   # Add new information
    UNKNOWN = "unknown"                 # Could not classify


@dataclass
class Query:
    """Represents a user's question to the engineering memory system."""

    id: EntityId
    raw_text: str
    intent: QueryIntent
    user_id: str
    created_at: Timestamp

    # Decomposed sub-tasks (set by the Planner node)
    sub_queries: list[str] = field(default_factory=list)

    # Query refinements (set during retry loops)
    refinement_history: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, raw_text: str, user_id: str) -> Query:
        """Create a new query. Intent is set to UNKNOWN until classified."""
        return cls(
            id=new_entity_id(),
            raw_text=raw_text.strip(),
            intent=QueryIntent.UNKNOWN,
            user_id=user_id,
            created_at=now_utc(),
        )

    def classify(self, intent: QueryIntent) -> None:
        """Set the classified intent (called by the Gateway node)."""
        self.intent = intent

    def decompose(self, sub_queries: list[str]) -> None:
        """Set sub-queries from the Planner node's decomposition."""
        self.sub_queries = sub_queries

    def refine(self, refined_query: str) -> None:
        """Track query refinements during retry loops."""
        self.refinement_history.append(refined_query)


@dataclass(frozen=True)
class Citation:
    """A citation linking a claim to its source evidence.

    Every claim in the final response MUST include at least one citation.
    This is the core anti-hallucination enforcement mechanism.
    """

    evidence_id: str
    memory_id: str
    source_uri: str
    chunk_content: str
    relevance_score: float
    page_rank: float = 0.0

    @property
    def display_label(self) -> str:
        """Short display label for inline citations, e.g. [E-1]."""
        short_id = self.evidence_id[:8]
        return f"[E-{short_id}]"


@dataclass
class RetrievalResult:
    """Results from the hybrid retrieval pipeline.

    Contains chunks found via vector similarity, graph traversal,
    and lexical search, ranked by the composite evidence score.
    """

    query_id: EntityId
    citations: list[Citation] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    retrieval_time_ms: float = 0.0

    # Breakdown by retrieval method
    vector_hits: int = 0
    graph_hits: int = 0
    lexical_hits: int = 0

    @property
    def total_evidence_count(self) -> int:
        return len(self.citations)

    @property
    def has_evidence(self) -> bool:
        return len(self.citations) > 0

    def top_citations(self, n: int = 5) -> list[Citation]:
        """Return the top-N citations by relevance score."""
        return sorted(
            self.citations,
            key=lambda c: c.relevance_score,
            reverse=True,
        )[:n]


@dataclass
class ReasoningResult:
    """Output from the Reasoner node after synthesizing evidence."""

    query_id: EntityId
    reasoning_text: str
    confidence: ConfidenceScore
    citations_used: list[Citation]
    hallucination_detected: bool = False
    reasoning_time_ms: float = 0.0

    @property
    def is_high_confidence(self) -> bool:
        return float(self.confidence) >= 0.60 and not self.hallucination_detected


@dataclass
class AgentResponse:
    """Final response from the agent system, ready for the user.

    Contains the generated answer with inline citations,
    the confidence score, and the full execution trace.
    """

    id: EntityId
    query_id: EntityId
    response_text: str
    confidence: ConfidenceScore
    citations: list[Citation]
    is_degraded: bool  # True if the response hit the 3-loop retry limit

    # Execution metadata
    total_time_ms: float
    retry_count: int
    nodes_visited: list[str]

    created_at: Timestamp = field(default_factory=now_utc)

    @classmethod
    def create_degraded(
        cls,
        query_id: EntityId,
        partial_text: str,
        citations: list[Citation],
        total_time_ms: float,
        retry_count: int,
        nodes_visited: list[str],
    ) -> AgentResponse:
        """Create a degraded response when confidence threshold is not met."""
        return cls(
            id=new_entity_id(),
            query_id=query_id,
            response_text=partial_text,
            confidence=ConfidenceScore(0.0),
            citations=citations,
            is_degraded=True,
            total_time_ms=total_time_ms,
            retry_count=retry_count,
            nodes_visited=nodes_visited,
        )

    @classmethod
    def create_success(
        cls,
        query_id: EntityId,
        response_text: str,
        confidence: ConfidenceScore,
        citations: list[Citation],
        total_time_ms: float,
        retry_count: int,
        nodes_visited: list[str],
    ) -> AgentResponse:
        """Create a successful high-confidence response."""
        return cls(
            id=new_entity_id(),
            query_id=query_id,
            response_text=response_text,
            confidence=confidence,
            citations=citations,
            is_degraded=False,
            total_time_ms=total_time_ms,
            retry_count=retry_count,
            nodes_visited=nodes_visited,
        )
