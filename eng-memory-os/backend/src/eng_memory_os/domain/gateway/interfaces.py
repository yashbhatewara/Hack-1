"""
Abstract LLM Gateway interface.

The domain layer depends on this interface — never on concrete
LLM provider implementations. This ensures the business logic
remains entirely agnostic of OpenAI, Anthropic, or any specific provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from eng_memory_os.domain.gateway.entities import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderStatus,
)


class LLMGateway(ABC):
    """Abstract interface for the LLM gateway.

    Implementations handle provider routing, fallback logic,
    circuit breakers, and token tracking.
    """

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the configured LLM provider.

        If the primary provider fails or the circuit breaker is open,
        automatically falls back to the next available provider.

        Raises:
            LLMGatewayError: If all providers fail.
            CircuitBreakerOpenError: If all circuit breakers are open.
        """
        ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings for a batch of texts.

        Raises:
            LLMGatewayError: If embedding generation fails.
        """
        ...

    @abstractmethod
    async def get_provider_status(self, provider: LLMProvider) -> ProviderStatus:
        """Check the health status of a specific provider."""
        ...

    @abstractmethod
    async def get_all_provider_statuses(self) -> dict[LLMProvider, ProviderStatus]:
        """Get health status of all configured providers."""
        ...

    @abstractmethod
    async def get_total_token_usage(self) -> dict[str, int]:
        """Get aggregate token usage across all providers.

        Returns dict with keys: total_prompt_tokens, total_completion_tokens,
        total_tokens, total_cost_usd.
        """
        ...
