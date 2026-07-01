"""Gateway bounded context: LLM routing, provider fallback, and token/cost management."""

from eng_memory_os.domain.gateway.entities import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    TokenUsage,
    ProviderStatus,
)
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.domain.gateway.events import (
    LLMRequestSent,
    LLMResponseReceived,
    LLMFallbackTriggered,
    CircuitBreakerTripped,
    CircuitBreakerReset,
)

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "TokenUsage",
    "ProviderStatus",
    "LLMGateway",
    "LLMRequestSent",
    "LLMResponseReceived",
    "LLMFallbackTriggered",
    "CircuitBreakerTripped",
    "CircuitBreakerReset",
]
