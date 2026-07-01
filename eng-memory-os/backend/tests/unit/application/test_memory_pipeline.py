"""Unit tests for the MemoryPipeline semantic chunker."""

from __future__ import annotations

import pytest


class TestMemoryPipelineChunker:
    """Tests for the pipeline's internal _normalize and _semantic_chunk methods."""

    @pytest.fixture
    def pipeline(self, mock_memory_repo, mock_event_bus, mock_embedding_service,
                 mock_vector_store):
        from eng_memory_os.application.pipelines.memory_pipeline import MemoryPipeline
        from unittest.mock import AsyncMock

        extract_uc = AsyncMock()
        extract_uc.execute = AsyncMock(return_value={"entities": 3, "relationships": 2})

        return MemoryPipeline(
            memory_repo=mock_memory_repo,
            extract_entities_uc=extract_uc,
            embedding_service=mock_embedding_service,
            vector_store=mock_vector_store,
            event_bus=mock_event_bus,
        )

    @pytest.mark.unit
    def test_normalize_strips_html_tags(self, pipeline):
        content = "<h1>Title</h1><p>Body text.</p>"
        result = pipeline._normalize(content)
        assert "<h1>" not in result
        assert "<p>" not in result
        assert "Title" in result
        assert "Body text." in result

    @pytest.mark.unit
    def test_normalize_collapses_blank_lines(self, pipeline):
        content = "Line 1\n\n\n\n\nLine 2"
        result = pipeline._normalize(content)
        assert "\n\n\n" not in result

    @pytest.mark.unit
    def test_normalize_collapses_multiple_spaces(self, pipeline):
        content = "Word1    Word2     Word3"
        result = pipeline._normalize(content)
        assert "  " not in result

    @pytest.mark.unit
    def test_normalize_handles_crlf_line_endings(self, pipeline):
        content = "Line1\r\nLine2\r\nLine3"
        result = pipeline._normalize(content)
        assert "\r" not in result

    @pytest.mark.unit
    def test_semantic_chunk_short_content_gives_one_chunk(self, pipeline):
        import uuid
        content = "Short content that fits in one chunk."
        mem_id = str(uuid.uuid4())
        chunks = pipeline._semantic_chunk(content, mem_id)
        assert len(chunks) == 1
        assert chunks[0].content == content

    @pytest.mark.unit
    def test_semantic_chunk_respects_target_size(self, pipeline):
        import uuid
        import os
        # Generate content larger than TARGET_CHUNK_SIZE (512 tokens ≈ 2048 chars)
        para = "This is a paragraph of content. " * 20  # ~640 chars ≈ 160 tokens
        content = "\n\n".join([para] * 15)  # 15 paragraphs ≈ 2400 tokens
        mem_id = str(uuid.uuid4())
        chunks = pipeline._semantic_chunk(content, mem_id)
        # Should have more than 1 chunk
        assert len(chunks) > 1

    @pytest.mark.unit
    def test_semantic_chunk_indices_are_sequential(self, pipeline):
        import uuid
        para = "Paragraph content here. " * 30
        content = "\n\n".join([para] * 10)
        mem_id = str(uuid.uuid4())
        chunks = pipeline._semantic_chunk(content, mem_id)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    @pytest.mark.unit
    def test_semantic_chunk_each_chunk_has_content(self, pipeline):
        import uuid
        content = "Para 1.\n\nPara 2.\n\nPara 3."
        mem_id = str(uuid.uuid4())
        chunks = pipeline._semantic_chunk(content, mem_id)
        for chunk in chunks:
            assert chunk.content.strip() != ""

    @pytest.mark.unit
    def test_estimate_tokens_reasonable(self, pipeline):
        text = "a" * 400  # 400 chars ≈ 100 tokens
        assert pipeline._estimate_tokens(text) == 100


class TestMemoryPipelineNormalize:
    """Additional normalization edge cases."""

    @pytest.fixture
    def pipeline(self, mock_memory_repo, mock_event_bus, mock_embedding_service,
                 mock_vector_store):
        from eng_memory_os.application.pipelines.memory_pipeline import MemoryPipeline
        from unittest.mock import AsyncMock
        extract_uc = AsyncMock()
        extract_uc.execute = AsyncMock(return_value={"entities": 0, "relationships": 0})
        return MemoryPipeline(
            memory_repo=mock_memory_repo,
            extract_entities_uc=extract_uc,
            embedding_service=mock_embedding_service,
            vector_store=mock_vector_store,
            event_bus=mock_event_bus,
        )

    @pytest.mark.unit
    def test_normalize_already_clean_content_unchanged(self, pipeline):
        content = "Clean content.\n\nSecond paragraph."
        result = pipeline._normalize(content)
        assert "Clean content." in result
        assert "Second paragraph." in result

    @pytest.mark.unit
    def test_normalize_returns_stripped(self, pipeline):
        content = "   Hello world.   "
        result = pipeline._normalize(content)
        assert result == result.strip()
