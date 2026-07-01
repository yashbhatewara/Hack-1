"""
Concrete LLM Gateway implementation.

Orchestrates provider routing, fallback logic, circuit breakers,
and token tracking. This is the single entry point for all LLM
interactions across the application.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.gateway.entities import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderStatus,
    TokenUsage,
)
from eng_memory_os.domain.gateway.interfaces import LLMGateway
from eng_memory_os.domain.shared.errors import CircuitBreakerOpenError, LLMGatewayError
from eng_memory_os.infrastructure.llm.circuit_breaker import CircuitBreaker
from eng_memory_os.infrastructure.llm.providers.anthropic_provider import AnthropicProvider
from eng_memory_os.infrastructure.llm.providers.ollama_provider import OllamaProvider
from eng_memory_os.infrastructure.llm.providers.openai_provider import OpenAIProvider
from eng_memory_os.infrastructure.llm.token_tracker import TokenTracker

logger = structlog.get_logger(__name__)


class LLMGatewayImpl(LLMGateway):
    """Production LLM Gateway with provider fallback and circuit breakers.

    Provider priority order:
    1. Primary provider (configurable, default: OpenAI)
    2. Secondary provider (configurable, default: Anthropic)
    3. Fallback provider (configurable, default: Ollama / local)

    Circuit breakers independently track each provider's health.
    If the primary trips, requests automatically route to the next available.
    """

    def __init__(
        self,
        primary_provider: LLMProvider = LLMProvider.OPENAI,
        fallback_provider: LLMProvider = LLMProvider.OLLAMA,
        openai_api_key: str = "",
        anthropic_api_key: str = "",
        ollama_base_url: str = "http://localhost:11434",
        openai_model: str = "gpt-4o",
        anthropic_model: str = "claude-sonnet-4-20250514",
        ollama_model: str = "llama3",
        circuit_breaker_threshold_ms: float = 5000.0,
    ) -> None:
        self._primary = primary_provider
        self._fallback = fallback_provider
        self._token_tracker = TokenTracker()

        # Initialize providers
        self._providers: dict[LLMProvider, object] = {}
        self._default_models: dict[LLMProvider, str] = {}

        if openai_api_key:
            self._providers[LLMProvider.OPENAI] = OpenAIProvider(openai_api_key)
            self._default_models[LLMProvider.OPENAI] = openai_model

        if anthropic_api_key:
            self._providers[LLMProvider.ANTHROPIC] = AnthropicProvider(anthropic_api_key)
            self._default_models[LLMProvider.ANTHROPIC] = anthropic_model

        self._providers[LLMProvider.OLLAMA] = OllamaProvider(ollama_base_url)
        self._default_models[LLMProvider.OLLAMA] = ollama_model

        # Circuit breakers per provider
        self._circuit_breakers: dict[LLMProvider, CircuitBreaker] = {
            provider: CircuitBreaker(
                name=provider.value,
                latency_threshold_ms=circuit_breaker_threshold_ms,
            )
            for provider in self._providers
        }

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request with automatic fallback."""
        # Build provider priority list
        providers_to_try = self._get_provider_order(request.provider)

        last_error: Exception | None = None

        for provider in providers_to_try:
            cb = self._circuit_breakers.get(provider)
            if cb and cb.is_open:
                logger.debug("provider_circuit_open", provider=provider.value)
                continue

            adapter = self._providers.get(provider)
            if adapter is None:
                continue

            try:
                # Override model if using a different provider than requested
                if provider != request.provider:
                    request = LLMRequest.create(
                        provider=provider,
                        model=self._default_models.get(provider, request.model),
                        messages=request.messages,
                        system_prompt=request.system_prompt,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                    )

                response = await adapter.complete(request)  # type: ignore[union-attr]

                # Record success
                if cb:
                    cb.record_success(response.latency_ms)
                self._token_tracker.record(
                    provider=provider,
                    model=response.model,
                    usage=response.token_usage,
                )

                return response

            except Exception as e:
                last_error = e
                if cb:
                    cb.record_failure(str(e))
                logger.warning(
                    "provider_failed",
                    provider=provider.value,
                    error=str(e),
                )
                continue

        raise LLMGatewayError(
            provider="all",
            reason=f"All providers failed. Last error: {last_error}",
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings with provider fallback."""
        # Embedding providers: OpenAI first, then Ollama
        providers_to_try = [LLMProvider.OPENAI, LLMProvider.OLLAMA]

        last_error: Exception | None = None

        for provider in providers_to_try:
            adapter = self._providers.get(provider)
            if adapter is None or not hasattr(adapter, "embed"):
                continue

            try:
                response = await adapter.embed(request)  # type: ignore[union-attr]
                self._token_tracker.record(
                    provider=provider,
                    model=response.model,
                    usage=response.token_usage,
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning("embedding_provider_failed", provider=provider.value, error=str(e))
                continue

        raise LLMGatewayError(
            provider="all",
            reason=f"All embedding providers failed. Last error: {last_error}",
        )

    async def get_provider_status(self, provider: LLMProvider) -> ProviderStatus:
        cb = self._circuit_breakers.get(provider)
        if cb is None:
            return ProviderStatus.UNAVAILABLE
        if cb.is_open:
            return ProviderStatus.CIRCUIT_OPEN
        if cb.is_closed:
            return ProviderStatus.HEALTHY
        return ProviderStatus.DEGRADED

    async def get_all_provider_statuses(self) -> dict[LLMProvider, ProviderStatus]:
        return {
            provider: await self.get_provider_status(provider)
            for provider in self._providers
        }

    async def get_total_token_usage(self) -> dict[str, int]:
        totals = self._token_tracker.get_totals()
        return {k: int(v) if isinstance(v, float) else v for k, v in totals.items()}  # type: ignore[misc]

    def _get_provider_order(self, requested: LLMProvider) -> list[LLMProvider]:
        """Determine provider priority order."""
        order = [requested]

        # Add primary if different from requested
        if self._primary != requested and self._primary in self._providers:
            order.append(self._primary)

        # Add all other configured providers
        for provider in self._providers:
            if provider not in order:
                order.append(provider)

        return order
