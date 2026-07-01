"""
Gateway domain entities.

Data structures for LLM requests, responses, token tracking,
and provider status management.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime

from eng_memory_os.domain.shared.types import EntityId, Timestamp, new_entity_id, now_utc


class LLMProvider(enum.StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ProviderStatus(enum.StrEnum):
    """Health status of an LLM provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TokenUsage:
    """Token usage metrics for a single LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    # Cost calculation (per 1M tokens)
    prompt_cost_per_million: float = 0.0
    completion_cost_per_million: float = 0.0

    @property
    def total_cost(self) -> float:
        """Calculate the total cost of this LLM call in USD."""
        prompt_cost = (self.prompt_tokens / 1_000_000) * self.prompt_cost_per_million
        completion_cost = (self.completion_tokens / 1_000_000) * self.completion_cost_per_million
        return prompt_cost + completion_cost

    @classmethod
    def zero(cls) -> TokenUsage:
        return cls(prompt_tokens=0, completion_tokens=0, total_tokens=0)


@dataclass
class LLMRequest:
    """A request to an LLM provider."""

    id: EntityId
    provider: LLMProvider
    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str | None = None
    created_at: Timestamp = field(default_factory=now_utc)

    @classmethod
    def create(
        cls,
        provider: LLMProvider,
        model: str,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMRequest:
        return cls(
            id=new_entity_id(),
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM provider."""

    request_id: EntityId
    provider: LLMProvider
    model: str
    content: str
    token_usage: TokenUsage
    latency_ms: float
    created_at: Timestamp = field(default_factory=now_utc)

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()


@dataclass
class EmbeddingRequest:
    """A request to generate embeddings."""

    id: EntityId
    provider: LLMProvider
    model: str
    texts: list[str]
    created_at: Timestamp = field(default_factory=now_utc)

    @classmethod
    def create(
        cls,
        provider: LLMProvider,
        model: str,
        texts: list[str],
    ) -> EmbeddingRequest:
        return cls(
            id=new_entity_id(),
            provider=provider,
            model=model,
            texts=texts,
        )


@dataclass(frozen=True)
class EmbeddingResponse:
    """Response containing generated embeddings."""

    request_id: EntityId
    provider: LLMProvider
    model: str
    embeddings: list[list[float]]
    token_usage: TokenUsage
    latency_ms: float
    dimensions: int

    @property
    def count(self) -> int:
        return len(self.embeddings)
