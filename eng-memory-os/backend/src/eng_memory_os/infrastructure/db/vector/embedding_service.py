"""
Embedding service abstraction.

Provides a unified interface for generating embeddings across
different providers (OpenAI, fastembed/local), decoupled from
the vector store.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService(ABC):
    """Abstract embedding generation service."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single embedding vector for a search query.

        Some models use different embeddings for queries vs documents.
        """
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI-based embedding service using text-embedding-3-small."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        import openai
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimension = dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API with batching."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = 100  # OpenAI supports up to 2048 inputs per request

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                input=batch,
                model=self._model,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.debug(
                "embeddings_generated",
                batch_index=i // batch_size,
                batch_size=len(batch),
                model=self._model,
            )

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        response = await self._client.embeddings.create(
            input=[query],
            model=self._model,
        )
        return response.data[0].embedding

    def get_dimension(self) -> int:
        return self._dimension


class OllamaEmbeddingService(EmbeddingService):
    """Local embedding service using Ollama (nomic-embed-text or similar)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        import httpx
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http_client = httpx.AsyncClient(timeout=60.0)
        # nomic-embed-text produces 768-dimensional vectors
        self._dimension = 768

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Ollama API (one at a time, as Ollama
        doesn't support batch embedding natively)."""
        embeddings: list[list[float]] = []

        for text in texts:
            response = await self._http_client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embedding"])

        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        response = await self._http_client.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": query},
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def get_dimension(self) -> int:
        return self._dimension

    async def close(self) -> None:
        await self._http_client.aclose()
