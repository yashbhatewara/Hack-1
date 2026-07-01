"""Unit tests for the Memory domain entity."""

from __future__ import annotations

import pytest

from eng_memory_os.domain.memory.entities import Memory, MemorySource, MemoryStatus
from eng_memory_os.domain.memory.events import (
    MemoryArchived,
    MemoryDecayed,
    MemoryIngested,
    MemoryUpdated,
)
from eng_memory_os.domain.memory.value_objects import MemoryChunk
from eng_memory_os.domain.shared.types import new_entity_id


# ─── Creation ────────────────────────────────────────────────────────────────

class TestMemoryCreation:
    def test_ingest_creates_memory_with_pending_status(self):
        memory = Memory.ingest(
            raw_content="Service X migration plan",
            source_uri="https://jira.io/PROJ-1",
            source_type=MemorySource.JIRA_TICKET,
            author="alice@co.com",
            title="Migration Plan",
        )
        assert memory.status == MemoryStatus.PENDING
        assert memory.access_count == 0
        assert float(memory.decay_factor) == 1.0
        assert float(memory.confidence_score) == 1.0

    def test_ingest_emits_memory_ingested_event(self):
        memory = Memory.ingest(
            raw_content="Content",
            source_uri="https://github.com/pr/1",
            source_type=MemorySource.GITHUB_PR,
            author="bob@co.com",
            title="PR #1",
        )
        events = memory.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], MemoryIngested)
        assert events[0].source_uri == "https://github.com/pr/1"

    def test_ingest_empty_content_raises(self):
        with pytest.raises(ValueError, match="empty"):
            Memory.ingest(
                raw_content="   ",
                source_uri="https://x.com",
                source_type=MemorySource.MANUAL_INPUT,
                author="alice@co.com",
                title="Empty",
            )

    def test_ingest_computes_provenance_hash(self):
        m = Memory.ingest(
            raw_content="Hello world",
            source_uri="https://example.com",
            source_type=MemorySource.MANUAL_INPUT,
            author="dev@co.com",
            title="Test",
        )
        assert m.provenance.hash_algorithm == "sha256"
        assert len(m.provenance.hash_value) == 64
        assert m.provenance.verify("Hello world")

    def test_ingest_tags_are_stored(self):
        m = Memory.ingest(
            raw_content="Content",
            source_uri="https://x.com",
            source_type=MemorySource.ADR,
            author="dev@co.com",
            title="ADR-1",
            tags=["architecture", "grpc"],
        )
        assert "architecture" in m.tags
        assert "grpc" in m.tags


# ─── Lifecycle State Transitions ─────────────────────────────────────────────

class TestMemoryLifecycle:
    def _make_chunk(self, memory: Memory) -> MemoryChunk:
        return MemoryChunk(
            chunk_id=new_entity_id(),
            memory_id=memory.id.value,
            content="Some chunk content",
            chunk_index=0,
            token_count=5,
        )

    def test_mark_processing_transitions_to_processing(self, pending_memory: Memory):
        pending_memory.mark_processing()
        assert pending_memory.status == MemoryStatus.PROCESSING

    def test_mark_processing_from_non_pending_raises(self, pending_memory: Memory):
        pending_memory.mark_processing()
        with pytest.raises(ValueError, match="pending"):
            pending_memory.mark_processing()

    def test_mark_active_requires_chunks(self, pending_memory: Memory):
        pending_memory.mark_processing()
        with pytest.raises(ValueError, match="zero chunks"):
            pending_memory.mark_active([])

    def test_mark_active_from_processing_succeeds(self, pending_memory: Memory):
        pending_memory.mark_processing()
        chunk = self._make_chunk(pending_memory)
        pending_memory.mark_active([chunk])
        assert pending_memory.status == MemoryStatus.ACTIVE
        assert len(pending_memory.chunks) == 1

    def test_mark_failed_always_succeeds(self, pending_memory: Memory):
        pending_memory.mark_failed("Test failure")
        assert pending_memory.status == MemoryStatus.FAILED

    def test_archive_emits_event(self, sample_memory: Memory):
        sample_memory.archive()
        events = sample_memory.collect_events()
        assert any(isinstance(e, MemoryArchived) for e in events)

    def test_collect_events_drains_queue(self, pending_memory: Memory):
        # Events from ingest
        events1 = pending_memory.collect_events()
        assert len(events1) == 1
        # Queue is now empty
        events2 = pending_memory.collect_events()
        assert len(events2) == 0


# ─── Access Recording ─────────────────────────────────────────────────────────

class TestMemoryAccess:
    def test_record_access_increments_count(self, sample_memory: Memory):
        initial = sample_memory.access_count
        sample_memory.record_access()
        assert sample_memory.access_count == initial + 1

    def test_record_access_boosts_decay_factor(self, sample_memory: Memory):
        # Artificially lower the decay factor
        from eng_memory_os.domain.shared.types import DecayFactor
        sample_memory.decay_factor = DecayFactor(0.8)
        sample_memory.record_access()
        assert float(sample_memory.decay_factor) > 0.8

    def test_record_access_decay_capped_at_one(self, sample_memory: Memory):
        sample_memory.record_access()
        assert float(sample_memory.decay_factor) <= 1.0

    def test_record_access_sets_last_accessed_at(self, sample_memory: Memory):
        assert sample_memory.last_accessed_at is None or True  # may be set
        sample_memory.record_access()
        assert sample_memory.last_accessed_at is not None


# ─── Decay ────────────────────────────────────────────────────────────────────

class TestMemoryDecay:
    def test_apply_decay_reduces_factor(self, sample_memory: Memory):
        initial = float(sample_memory.decay_factor)
        sample_memory.apply_decay(decay_rate=0.99)
        assert float(sample_memory.decay_factor) < initial

    def test_apply_decay_transitions_to_stale_below_threshold(self, sample_memory: Memory):
        from eng_memory_os.domain.shared.types import DecayFactor
        sample_memory.decay_factor = DecayFactor(0.31)
        sample_memory.apply_decay(decay_rate=0.9)  # 0.31 * 0.9 = 0.279 < 0.3
        assert sample_memory.status == MemoryStatus.STALE

    def test_apply_decay_emits_decayed_event_on_stale(self, sample_memory: Memory):
        from eng_memory_os.domain.shared.types import DecayFactor
        sample_memory.decay_factor = DecayFactor(0.31)
        sample_memory.apply_decay(decay_rate=0.9)
        events = sample_memory.collect_events()
        assert any(isinstance(e, MemoryDecayed) for e in events)

    def test_apply_decay_no_effect_on_archived(self, sample_memory: Memory):
        sample_memory.archive()
        initial = float(sample_memory.decay_factor)
        sample_memory.apply_decay(decay_rate=0.5)
        assert float(sample_memory.decay_factor) == initial

    def test_effective_score_formula(self, sample_memory: Memory):
        score = sample_memory.effective_score
        expected = (
            float(sample_memory.importance_score) * 0.4
            + float(sample_memory.confidence_score) * 0.3
            + float(sample_memory.decay_factor) * 0.3
        )
        assert abs(score - expected) < 0.001


# ─── Content Updates ──────────────────────────────────────────────────────────

class TestMemoryContentUpdate:
    def test_update_content_recomputes_provenance(self, sample_memory: Memory):
        old_hash = sample_memory.provenance.hash_value
        sample_memory.update_content("New content entirely", "bob@co.com")
        assert sample_memory.provenance.hash_value != old_hash

    def test_update_content_resets_to_pending(self, sample_memory: Memory):
        sample_memory.update_content("New content", "bob@co.com")
        assert sample_memory.status == MemoryStatus.PENDING
        assert sample_memory.chunks == []

    def test_update_content_emits_memory_updated_event(self, sample_memory: Memory):
        sample_memory.update_content("Updated content", "bob@co.com")
        events = sample_memory.collect_events()
        assert any(isinstance(e, MemoryUpdated) for e in events)

    def test_update_empty_content_raises(self, sample_memory: Memory):
        with pytest.raises(ValueError, match="empty"):
            sample_memory.update_content("   ", "bob@co.com")
