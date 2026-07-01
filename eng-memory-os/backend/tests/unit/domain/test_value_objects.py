"""Unit tests for the Memory value objects."""

from __future__ import annotations

import pytest

from eng_memory_os.domain.memory.value_objects import (
    MemoryChunk,
    MemoryId,
    Provenance,
    SourceUri,
)
from eng_memory_os.domain.shared.types import new_entity_id


class TestMemoryId:
    def test_generate_creates_unique_ids(self):
        id1 = MemoryId.generate()
        id2 = MemoryId.generate()
        assert id1 != id2

    def test_from_str_roundtrip(self):
        original = MemoryId.generate()
        reconstructed = MemoryId.from_str(str(original))
        assert original == reconstructed

    def test_from_str_invalid_uuid_raises(self):
        with pytest.raises(ValueError):
            MemoryId.from_str("not-a-uuid")


class TestSourceUri:
    def test_valid_github_uri(self):
        uri = SourceUri("https://github.com/org/repo/pull/123")
        assert uri.scheme == "https"

    def test_empty_uri_raises(self):
        with pytest.raises(ValueError, match="empty"):
            SourceUri("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            SourceUri("   ")

    def test_str_repr(self):
        raw = "https://jira.io/PROJ/1"
        assert str(SourceUri(raw)) == raw


class TestProvenance:
    def test_from_content_produces_sha256_hash(self):
        p = Provenance.from_content("hello world")
        assert p.hash_algorithm == "sha256"
        assert len(p.hash_value) == 64

    def test_verify_correct_content(self):
        content = "Engineering artifact content"
        p = Provenance.from_content(content)
        assert p.verify(content) is True

    def test_verify_wrong_content(self):
        p = Provenance.from_content("original content")
        assert p.verify("different content") is False

    def test_str_format(self):
        p = Provenance.from_content("test")
        assert "sha256:" in str(p)

    def test_same_content_same_hash(self):
        content = "deterministic content"
        p1 = Provenance.from_content(content)
        p2 = Provenance.from_content(content)
        assert p1.hash_value == p2.hash_value


class TestMemoryChunk:
    def test_create_chunk_without_embedding(self):
        chunk = MemoryChunk.create(
            memory_id=new_entity_id(),
            content="Some text content here.",
            chunk_index=0,
            token_count=5,
        )
        assert chunk.embedding_vector is None
        assert not chunk.is_embedded

    def test_with_embedding_returns_new_instance(self):
        chunk = MemoryChunk.create(
            memory_id=new_entity_id(),
            content="Text",
            chunk_index=0,
            token_count=1,
        )
        vector = [0.1] * 1536
        embedded_chunk = chunk.with_embedding(vector)
        assert embedded_chunk is not chunk  # Immutable: new instance
        assert embedded_chunk.embedding_vector == vector
        assert embedded_chunk.is_embedded
        assert chunk.embedding_vector is None  # Original unchanged

    def test_with_embedding_preserves_other_fields(self):
        chunk = MemoryChunk.create(
            memory_id=new_entity_id(),
            content="Important text",
            chunk_index=3,
            token_count=10,
        )
        embedded = chunk.with_embedding([0.5] * 512)
        assert embedded.content == chunk.content
        assert embedded.chunk_index == chunk.chunk_index
        assert embedded.token_count == chunk.token_count
        assert embedded.chunk_id == chunk.chunk_id
