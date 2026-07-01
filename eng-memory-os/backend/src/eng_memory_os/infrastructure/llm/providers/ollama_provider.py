"""
Ollama provider adapter (local LLM fallback).

Handles communication with the Ollama API for offline/privacy mode.
Ollama runs locally and supports both completions and embeddings.
"""

from __future__ import annotations

import time

import httpx
import structlog

from eng_memory_os.domain.gateway.entities import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class OllamaProvider:
    """Adapter for the Ollama local LLM API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to Ollama."""
        start_time = time.perf_counter()

        # Build the prompt from messages
        prompt_parts: list[str] = []
        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}")
        for msg in request.messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")

        # Use Ollama's chat API
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": request.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        latency_ms = (time.perf_counter() - start_time) * 1000

        content = data.get("message", {}).get("content", "")

        # Ollama provides token counts in the response
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        logger.info(
            "ollama_completion",
            model=request.model,
            latency_ms=round(latency_ms, 1),
            tokens=token_usage.total_tokens,
        )

        return LLMResponse(
            request_id=request.id,
            provider=LLMProvider.OLLAMA,
            model=request.model,
            content=content,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using Ollama."""
        start_time = time.perf_counter()

        embeddings: list[list[float]] = []
        total_tokens = 0

        for text in request.texts:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": request.model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embedding"])
            # Rough token estimate (Ollama doesn't always return token counts for embeddings)
            total_tokens += len(text.split()) * 2

        latency_ms = (time.perf_counter() - start_time) * 1000
        dimension = len(embeddings[0]) if embeddings else 0

        return EmbeddingResponse(
            request_id=request.id,
            provider=LLMProvider.OLLAMA,
            model=request.model,
            embeddings=embeddings,
            token_usage=TokenUsage(
                prompt_tokens=total_tokens,
                completion_tokens=0,
                total_tokens=total_tokens,
            ),
            latency_ms=latency_ms,
            dimensions=dimension,
        )

    async def is_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = await self._client.get(f"{self._base_url}/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        await self._client.aclose()
