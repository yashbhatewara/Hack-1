"""
Token usage and cost tracker.

Aggregates token usage and cost across all LLM providers,
providing both per-query and cumulative metrics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import structlog

from eng_memory_os.domain.gateway.entities import LLMProvider, TokenUsage

logger = structlog.get_logger(__name__)

# Cost per million tokens (USD) as of 2025-2026
PROVIDER_COSTS: dict[str, dict[str, float]] = {
    "openai:gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "openai:gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "openai:text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
    "anthropic:claude-sonnet-4-20250514": {"prompt": 3.00, "completion": 15.00},
    "anthropic:claude-3-5-haiku-20241022": {"prompt": 0.80, "completion": 4.00},
    "ollama:*": {"prompt": 0.0, "completion": 0.0},  # Local, no cost
}


def get_costs(provider: str, model: str) -> tuple[float, float]:
    """Look up the per-million-token costs for a provider/model combo."""
    key = f"{provider}:{model}"
    if key in PROVIDER_COSTS:
        costs = PROVIDER_COSTS[key]
        return costs["prompt"], costs["completion"]

    # Check for wildcard provider match (e.g., ollama:*)
    wildcard_key = f"{provider}:*"
    if wildcard_key in PROVIDER_COSTS:
        costs = PROVIDER_COSTS[wildcard_key]
        return costs["prompt"], costs["completion"]

    return 0.0, 0.0


@dataclass
class QueryTokenRecord:
    """Token usage record for a single query."""

    query_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


class TokenTracker:
    """Thread-safe aggregator for LLM token usage and costs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_cost_usd: float = 0.0
        self._records: list[QueryTokenRecord] = []
        self._provider_totals: dict[str, dict[str, int | float]] = {}

    def record(
        self,
        provider: LLMProvider,
        model: str,
        usage: TokenUsage,
        query_id: str = "",
    ) -> QueryTokenRecord:
        """Record token usage from a single LLM call."""
        prompt_cost_per_m, completion_cost_per_m = get_costs(provider.value, model)
        cost = (
            (usage.prompt_tokens / 1_000_000) * prompt_cost_per_m
            + (usage.completion_tokens / 1_000_000) * completion_cost_per_m
        )

        record = QueryTokenRecord(
            query_id=query_id,
            provider=provider.value,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=cost,
        )

        with self._lock:
            self._total_prompt_tokens += usage.prompt_tokens
            self._total_completion_tokens += usage.completion_tokens
            self._total_cost_usd += cost
            self._records.append(record)

            # Update per-provider totals
            pkey = provider.value
            if pkey not in self._provider_totals:
                self._provider_totals[pkey] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "request_count": 0,
                }
            self._provider_totals[pkey]["prompt_tokens"] += usage.prompt_tokens  # type: ignore[operator]
            self._provider_totals[pkey]["completion_tokens"] += usage.completion_tokens  # type: ignore[operator]
            self._provider_totals[pkey]["total_tokens"] += usage.total_tokens  # type: ignore[operator]
            self._provider_totals[pkey]["cost_usd"] += cost  # type: ignore[operator]
            self._provider_totals[pkey]["request_count"] += 1  # type: ignore[operator]

        logger.debug(
            "tokens_recorded",
            provider=provider.value,
            model=model,
            prompt=usage.prompt_tokens,
            completion=usage.completion_tokens,
            cost_usd=f"{cost:.6f}",
        )

        return record

    def get_totals(self) -> dict[str, int | float]:
        """Get aggregate token usage and cost across all providers."""
        with self._lock:
            return {
                "total_prompt_tokens": self._total_prompt_tokens,
                "total_completion_tokens": self._total_completion_tokens,
                "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
                "total_cost_usd": round(self._total_cost_usd, 6),
                "total_requests": len(self._records),
            }

    def get_provider_breakdown(self) -> dict[str, dict[str, int | float]]:
        """Get per-provider token usage breakdown."""
        with self._lock:
            return dict(self._provider_totals)

    def get_recent_records(self, n: int = 50) -> list[QueryTokenRecord]:
        """Get the N most recent token usage records."""
        with self._lock:
            return list(reversed(self._records[-n:]))
