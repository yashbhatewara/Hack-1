"""
Anthropic provider adapter.

Handles communication with the Anthropic API for completions.
Anthropic does not currently provide an embedding API,
so embedding requests fall back to other providers.
"""

from __future__ import annotations

import time

import anthropic
import structlog

from eng_memory_os.domain.gateway.entities import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class AnthropicProvider:
    """Adapter for the Anthropic API."""

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to Anthropic."""
        start_time = time.perf_counter()

        # Anthropic uses a separate 'system' parameter
        system_prompt = request.system_prompt or ""

        # Convert messages format
        messages = []
        for msg in request.messages:
            role = msg.get("role", "user")
            # Anthropic only supports 'user' and 'assistant' roles in messages
            if role == "system":
                system_prompt = msg.get("content", "")
                continue
            messages.append({
                "role": role,
                "content": msg.get("content", ""),
            })

        response = await self._client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
            temperature=request.temperature,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content from response
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        token_usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        logger.info(
            "anthropic_completion",
            model=request.model,
            latency_ms=round(latency_ms, 1),
            tokens=token_usage.total_tokens,
        )

        return LLMResponse(
            request_id=request.id,
            provider=LLMProvider.ANTHROPIC,
            model=request.model,
            content=content,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )
