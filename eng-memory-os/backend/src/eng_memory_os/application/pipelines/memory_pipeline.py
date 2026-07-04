"""
Memory Lifecycle Pipeline.

Orchestrates the full 8-stage memory processing pipeline:
1. Ingestion → 2. Normalization → 3. Semantic Chunking → 4. Entity Extraction →
5. Relationship Extraction → 6. Graph Optimization → 7. Vectorization → 8. Storage
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from eng_memory_os.domain.memory.events import MemoryProcessingCompleted, MemoryProcessingFailed
from eng_memory_os.domain.memory.value_objects import MemoryChunk, MemoryId
from eng_memory_os.domain.shared.errors import IngestionError
from eng_memory_os.domain.shared.types import new_entity_id

if TYPE_CHECKING:
    from eng_memory_os.application.knowledge.extract_entities import ExtractEntitiesUseCase
    from eng_memory_os.domain.memory.repositories import MemoryRepository
    from eng_memory_os.infrastructure.db.vector.embedding_service import EmbeddingService
    from eng_memory_os.infrastructure.db.vector.qdrant_adapter import QdrantVectorStoreAdapter
    from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class MemoryPipeline:
    """Orchestrates the full 8-stage memory processing pipeline."""

    # Chunking parameters (set lower to fit safely under 512-token embedding limit)
    TARGET_CHUNK_SIZE = 300  # tokens
    CHUNK_OVERLAP = 40  # tokens overlap between chunks
    MIN_CHUNK_SIZE = 30  # minimum tokens for a valid chunk

    def __init__(
        self,
        memory_repo: MemoryRepository,
        extract_entities_uc: ExtractEntitiesUseCase,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStoreAdapter,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._memory_repo = memory_repo
        self._extract_entities = extract_entities_uc
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._event_bus = event_bus

    async def process(self, memory_id: str) -> None:
        """Run the full pipeline for a specific memory."""
        memory = await self._memory_repo.get_by_id(MemoryId.from_str(memory_id))
        if memory is None:
            logger.error("pipeline_memory_not_found", memory_id=memory_id)
            return

        try:
            # Stage 1: Already done (memory was created via IngestMemoryUseCase)
            memory.mark_processing()
            await self._memory_repo.save(memory)

            # Stage 2: Normalization
            normalized_content = self._normalize(memory.raw_content)

            # Stage 3: Semantic Chunking
            chunks = self._semantic_chunk(normalized_content, memory_id)
            memory.chunks = chunks
            await self._memory_repo.save(memory)

            # Stage 4 & 5: Entity & Relationship Extraction
            extraction_result = await self._extract_entities.execute(memory_id)

            # Stage 6: Graph Optimization (handled via events if threshold met)

            # Stage 7: Vectorization
            chunks = await self._vectorize_chunks(chunks)

            # Stage 8: Storage
            await self._vector_store.ensure_collection(
                self._embedding_service.get_dimension()
            )
            stored_count = await self._vector_store.upsert_chunks(chunks)

            # Finalize: mark memory as active
            memory.mark_active(chunks)
            await self._memory_repo.save(memory)

            await self._event_bus.publish(
                MemoryProcessingCompleted(
                    memory_id=memory_id,
                    chunk_count=len(chunks),
                    entity_count=extraction_result.get("entities", 0),
                )
            )

            logger.info(
                "pipeline_completed",
                memory_id=memory_id,
                chunks=len(chunks),
                vectors_stored=stored_count,
                entities=extraction_result.get("entities", 0),
                relationships=extraction_result.get("relationships", 0),
            )

        except Exception as e:
            memory.mark_failed(str(e))
            await self._memory_repo.save(memory)

            await self._event_bus.publish(
                MemoryProcessingFailed(
                    memory_id=memory_id,
                    stage="pipeline",
                    error_message=str(e),
                )
            )

            logger.exception("pipeline_failed", memory_id=memory_id)
            raise IngestionError(stage="pipeline", reason=str(e)) from e

    def _normalize(self, content: str) -> str:
        """Stage 2: Normalize and clean raw content.

        - Strip excessive whitespace
        - Resolve markdown artifacts
        - Normalize line endings
        - Remove HTML tags if present
        """
        # Normalize line endings
        text = content.replace("\r\n", "\n").replace("\r", "\n")

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Collapse multiple blank lines into double newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip leading/trailing whitespace per line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)

        return text.strip()

    def _semantic_chunk(self, content: str, memory_id: str) -> list[MemoryChunk]:
        """Stage 3: Context-aware semantic chunking.

        Chunks at paragraph/section boundaries rather than arbitrary token limits.
        Falls back to sentence-level splitting if paragraphs are too large.
        """
        chunks: list[MemoryChunk] = []

        # Split by double newline (paragraphs/sections)
        sections = re.split(r"\n\n+", content)

        current_chunk_text = ""
        current_token_count = 0
        chunk_index = 0

        for section in sections:
            section = section.strip()
            if not section:
                continue

            section_tokens = self._estimate_tokens(section)

            # If this section alone exceeds target, split it by sentences
            if section_tokens > self.TARGET_CHUNK_SIZE:
                # Flush current chunk first
                if current_chunk_text:
                    chunks.append(self._create_chunk(
                        memory_id, current_chunk_text, chunk_index, current_token_count
                    ))
                    chunk_index += 1
                    current_chunk_text = ""
                    current_token_count = 0

                # Split large section by sentences
                sentence_chunks = self._split_by_sentences(section, memory_id, chunk_index)
                chunks.extend(sentence_chunks)
                chunk_index += len(sentence_chunks)
                continue

            # If adding this section would exceed target, flush current chunk
            if current_token_count + section_tokens > self.TARGET_CHUNK_SIZE and current_chunk_text:
                chunks.append(self._create_chunk(
                    memory_id, current_chunk_text, chunk_index, current_token_count
                ))
                chunk_index += 1
                current_chunk_text = ""
                current_token_count = 0

            # Append section to current chunk
            if current_chunk_text:
                current_chunk_text += "\n\n" + section
            else:
                current_chunk_text = section
            current_token_count += section_tokens

        # Flush remaining text
        if current_chunk_text and current_token_count >= self.MIN_CHUNK_SIZE:
            chunks.append(self._create_chunk(
                memory_id, current_chunk_text, chunk_index, current_token_count
            ))

        # Handle edge case: no chunks created (very short content)
        if not chunks and content.strip():
            chunks.append(self._create_chunk(
                memory_id, content.strip(), 0, self._estimate_tokens(content)
            ))

        return chunks

    def _split_by_sentences(
        self, text: str, memory_id: str, start_index: int
    ) -> list[MemoryChunk]:
        """Split a large section into chunks at sentence boundaries, falling back to line or chunk limits if needed."""
        # Simple sentence splitting using punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[MemoryChunk] = []
        current_text = ""
        current_tokens = 0
        idx = start_index

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            s_tokens = self._estimate_tokens(sentence)

            # If a single sentence exceeds target size, split it by line or raw chunk length
            if s_tokens > self.TARGET_CHUNK_SIZE:
                # Flush existing chunk
                if current_text:
                    chunks.append(self._create_chunk(memory_id, current_text, idx, current_tokens))
                    idx += 1
                    current_text = ""
                    current_tokens = 0

                # Split the long sentence by lines
                lines = sentence.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    l_tokens = self._estimate_tokens(line)
                    # If a single line still exceeds target, split it by raw characters
                    if l_tokens > self.TARGET_CHUNK_SIZE:
                        # Flush existing chunk if any
                        if current_text:
                            chunks.append(self._create_chunk(memory_id, current_text, idx, current_tokens))
                            idx += 1
                            current_text = ""
                            current_tokens = 0
                        # Split by max characters corresponding to TARGET_CHUNK_SIZE (approx 2 chars per token)
                        chunk_char_limit = self.TARGET_CHUNK_SIZE * 2
                        for i in range(0, len(line), chunk_char_limit):
                            segment = line[i:i + chunk_char_limit]
                            seg_tokens = self._estimate_tokens(segment)
                            chunks.append(self._create_chunk(memory_id, segment, idx, seg_tokens))
                            idx += 1
                        continue

                    if current_tokens + l_tokens > self.TARGET_CHUNK_SIZE and current_text:
                        chunks.append(self._create_chunk(memory_id, current_text, idx, current_tokens))
                        idx += 1
                        current_text = ""
                        current_tokens = 0
                    current_text = f"{current_text}\n{line}".strip() if current_text else line
                    current_tokens += l_tokens
                continue

            if current_tokens + s_tokens > self.TARGET_CHUNK_SIZE and current_text:
                chunks.append(self._create_chunk(memory_id, current_text, idx, current_tokens))
                idx += 1
                current_text = ""
                current_tokens = 0

            current_text = f"{current_text} {sentence}".strip() if current_text else sentence
            current_tokens += s_tokens

        if current_text and current_tokens >= self.MIN_CHUNK_SIZE:
            chunks.append(self._create_chunk(memory_id, current_text, idx, current_tokens))

        return chunks

    def _create_chunk(
        self, memory_id: str, content: str, index: int, token_count: int
    ) -> MemoryChunk:
        """Create a MemoryChunk value object."""
        import uuid

        from eng_memory_os.domain.shared.types import EntityId
        return MemoryChunk(
            chunk_id=new_entity_id(),
            memory_id=EntityId(uuid.UUID(memory_id)),
            content=content,
            chunk_index=index,
            token_count=token_count,
        )

    async def _vectorize_chunks(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        """Stage 7: Generate embeddings for all chunks."""
        if not chunks:
            return []

        texts = [c.content for c in chunks]
        embeddings = await self._embedding_service.embed_texts(texts)

        return [
            chunk.with_embedding(embedding)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate. For code/diffs, characters per token is lower.
        We use a conservative estimate (~2 characters per token) to prevent exceeding API limits.
        """
        return max(1, len(text) // 2)
