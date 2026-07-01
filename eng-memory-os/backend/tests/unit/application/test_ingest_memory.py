"""Unit tests for the IngestMemoryUseCase."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from eng_memory_os.application.memory.ingest_memory import (
    IngestMemoryRequest,
    IngestMemoryUseCase,
)
from eng_memory_os.domain.memory.events import MemoryIngested


class TestIngestMemoryUseCase:
    """Tests for the IngestMemoryUseCase."""

    @pytest.fixture
    def use_case(self, mock_memory_repo, mock_event_bus):
        return IngestMemoryUseCase(
            memory_repo=mock_memory_repo,
            event_bus=mock_event_bus,
        )

    @pytest.fixture
    def valid_request(self):
        return IngestMemoryRequest(
            raw_content="This is an architecture decision record about switching to gRPC.",
            source_uri="https://github.com/org/docs/adr/042.md",
            source_type="adr",
            author="alice@company.com",
            title="ADR-042: gRPC Migration",
            tags=["architecture", "grpc"],
        )

    @pytest.mark.unit
    async def test_execute_saves_memory_to_repo(
        self, use_case, valid_request, mock_memory_repo, mock_event_bus
    ):
        mock_memory_repo.find_by_source_uri.return_value = None

        result = await use_case.execute(valid_request)

        mock_memory_repo.save.assert_called_once()
        assert result.memory_id is not None
        assert result.status == "pending"

    @pytest.mark.unit
    async def test_execute_publishes_memory_ingested_event(
        self, use_case, valid_request, mock_memory_repo, mock_event_bus
    ):
        mock_memory_repo.find_by_source_uri.return_value = None

        await use_case.execute(valid_request)

        mock_event_bus.publish_all.assert_called()
        call_args = mock_event_bus.publish_all.call_args[0][0]
        event_types = [type(event) for event in call_args]
        assert MemoryIngested in event_types

    @pytest.mark.unit
    async def test_execute_returns_importance_score(
        self, use_case, valid_request, mock_memory_repo
    ):
        mock_memory_repo.find_by_source_uri.return_value = None

        result = await use_case.execute(valid_request)

        assert 0 <= result.importance_score <= 10.0

    @pytest.mark.unit
    async def test_duplicate_source_uri_updates_existing_memory(
        self, use_case, valid_request, mock_memory_repo, mock_event_bus, sample_memory
    ):
        """Second ingest of the same URI should update content instead of raising an error."""
        mock_memory_repo.find_by_source_uri.return_value = sample_memory

        result = await use_case.execute(valid_request)

        assert result.memory_id == str(sample_memory.id)
        mock_memory_repo.save.assert_called_with(sample_memory)
        mock_event_bus.publish_all.assert_called()

    @pytest.mark.unit
    async def test_adr_source_type_gets_higher_importance(
        self, use_case, mock_memory_repo
    ):
        """ADRs and incident reports should score higher than meeting notes."""
        mock_memory_repo.find_by_source_uri.return_value = None

        adr_request = IngestMemoryRequest(
            raw_content="Architecture Decision Record content",
            source_uri="https://github.com/adr/1",
            source_type="adr",
            author="dev@co.com",
            title="ADR-1",
        )
        notes_request = IngestMemoryRequest(
            raw_content="Meeting notes content",
            source_uri="https://github.com/notes/1",
            source_type="meeting_notes",
            author="dev@co.com",
            title="Q1 Meeting",
        )

        adr_result = await use_case.execute(adr_request)
        mock_memory_repo.find_by_source_uri.return_value = None
        notes_result = await use_case.execute(notes_request)

        assert adr_result.importance_score >= notes_result.importance_score
