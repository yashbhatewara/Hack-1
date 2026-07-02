"""
OpenAI provider adapter.

Handles communication with the OpenAI API for both completions and embeddings.
"""

from __future__ import annotations

import time

import openai
import structlog

from eng_memory_os.domain.gateway.entities import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)
from eng_memory_os.domain.shared.types import new_entity_id, now_utc

logger = structlog.get_logger(__name__)


class OpenAIProvider:
    """Adapter for the OpenAI API."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to OpenAI."""
        start_time = time.perf_counter()

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        response = await self._client.chat.completions.create(
            model=request.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        usage = response.usage
        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

        content = response.choices[0].message.content or ""

        logger.info(
            "openai_completion",
            model=request.model,
            latency_ms=round(latency_ms, 1),
            tokens=token_usage.total_tokens,
        )

        return LLMResponse(
            request_id=request.id,
            provider=LLMProvider.OPENAI,
            model=request.model,
            content=content,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using OpenAI."""
        start_time = time.perf_counter()

        kwargs = {}
        if "nvidia" in str(self._client.base_url) or request.model.startswith("nvidia/"):
            kwargs["extra_body"] = {"input_type": "passage"}

        response = await self._client.embeddings.create(
            input=request.texts,
            model=request.model,
            **kwargs
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        embeddings = [item.embedding for item in response.data]
        dimension = len(embeddings[0]) if embeddings else 0

        usage = response.usage
        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=0,
            total_tokens=usage.total_tokens if usage else 0,
        )

        return EmbeddingResponse(
            request_id=request.id,
            provider=LLMProvider.OPENAI,
            model=request.model,
            embeddings=embeddings,
            token_usage=token_usage,
            latency_ms=latency_ms,
            dimensions=dimension,
        )
