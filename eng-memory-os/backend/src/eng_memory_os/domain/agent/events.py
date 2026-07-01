"""Domain events emitted by the Agent bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field

from eng_memory_os.domain.shared.events import DomainEvent


@dataclass(frozen=True)
class QueryReceived(DomainEvent):
    """Emitted when a new query enters the agent system."""

    query_id: str = ""
    raw_text: str = ""
    user_id: str = ""
    classified_intent: str = ""


@dataclass(frozen=True)
class RetrievalCompleted(DomainEvent):
    """Emitted when the hybrid retrieval pipeline finishes."""

    query_id: str = ""
    evidence_count: int = 0
    vector_hits: int = 0
    graph_hits: int = 0
    lexical_hits: int = 0
    retrieval_time_ms: float = 0.0


@dataclass(frozen=True)
class ReasoningCompleted(DomainEvent):
    """Emitted when the Reasoner node produces a synthesis."""

    query_id: str = ""
    confidence: float = 0.0
    hallucination_detected: bool = False
    citations_count: int = 0
    reasoning_time_ms: float = 0.0


@dataclass(frozen=True)
class CriticRejected(DomainEvent):
    """Emitted when the Critic node rejects the reasoning and triggers a retry."""

    query_id: str = ""
    loop_number: int = 0
    rejection_reason: str = ""
    refined_query: str = ""


@dataclass(frozen=True)
class ResponseGenerated(DomainEvent):
    """Emitted when the final response is generated."""

    query_id: str = ""
    response_id: str = ""
    is_degraded: bool = False
    confidence: float = 0.0
    total_time_ms: float = 0.0
    retry_count: int = 0
