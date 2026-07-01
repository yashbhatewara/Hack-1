"""
Abstract interfaces for external system integrations.

Defines the contract that all integration adapters (GitHub, Jira,
Slack, Notion) must fulfill. Each adapter converts external data
into Memory domain objects for ingestion.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from eng_memory_os.domain.memory.entities import MemorySource
from eng_memory_os.domain.shared.types import Timestamp, now_utc


class IntegrationType(enum.StrEnum):
    """Supported external integration types."""

    GITHUB = "github"
    JIRA = "jira"
    SLACK = "slack"
    NOTION = "notion"
    CONFLUENCE = "confluence"
    PAGERDUTY = "pagerduty"
    CUSTOM_WEBHOOK = "custom_webhook"


@dataclass
class IntegrationConfig:
    """Configuration for an external integration.

    API keys and secrets are encrypted at rest using AES-256.
    """

    integration_type: IntegrationType
    name: str
    base_url: str
    encrypted_api_key: str
    enabled: bool = True
    sync_interval_minutes: int = 60
    last_synced_at: Timestamp | None = None
    extra_config: dict[str, str] = field(default_factory=dict)
    created_at: Timestamp = field(default_factory=now_utc)

    @property
    def is_due_for_sync(self) -> bool:
        """Check if enough time has passed for the next sync."""
        if self.last_synced_at is None:
            return True
        from datetime import timezone
        elapsed = datetime.now(timezone.utc) - self.last_synced_at
        return elapsed.total_seconds() >= (self.sync_interval_minutes * 60)


@dataclass(frozen=True)
class IngestedItem:
    """A single item fetched from an external integration, ready for memory ingestion."""

    source_uri: str
    source_type: MemorySource
    title: str
    content: str
    author: str
    external_id: str
    external_timestamp: datetime
    tags: list[str] = field(default_factory=list)


class IntegrationAdapter(ABC):
    """Abstract adapter for external system integrations.

    Each implementation handles authentication, API calls,
    pagination, and data transformation for a specific external system.
    """

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify that the integration is properly configured and accessible."""
        ...

    @abstractmethod
    async def fetch_recent(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[IngestedItem]:
        """Fetch recent items from the external system.

        Args:
            since: Only fetch items created/updated after this timestamp.
            limit: Maximum number of items to fetch.

        Returns:
            List of IngestedItem objects ready for memory ingestion.
        """
        ...

    @abstractmethod
    async def fetch_by_id(self, external_id: str) -> IngestedItem | None:
        """Fetch a specific item by its external identifier."""
        ...

    @abstractmethod
    def get_integration_type(self) -> IntegrationType:
        """Return the type of this integration."""
        ...
