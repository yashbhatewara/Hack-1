"""Domain events emitted by the Gateway bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from eng_memory_os.domain.shared.events import DomainEvent


@dataclass(frozen=True)
class LLMRequestSent(DomainEvent):
    """Emitted when an LLM request is dispatched to a provider."""

    request_id: str = ""
    provider: str = ""
    model: str = ""
    prompt_tokens_estimate: int = 0


@dataclass(frozen=True)
class LLMResponseReceived(DomainEvent):
    """Emitted when an LLM response is successfully received."""

    request_id: str = ""
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class LLMFallbackTriggered(DomainEvent):
    """Emitted when the primary LLM provider fails and fallback is used."""

    failed_provider: str = ""
    fallback_provider: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class CircuitBreakerTripped(DomainEvent):
    """Emitted when a circuit breaker opens due to repeated failures or latency."""

    provider: str = ""
    failure_count: int = 0
    threshold_ms: int = 0


@dataclass(frozen=True)
class CircuitBreakerReset(DomainEvent):
    """Emitted when a circuit breaker resets to closed state."""

    provider: str = ""
    downtime_seconds: float = 0.0
