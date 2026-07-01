"""Integration bounded context: adapters for external systems (GitHub, Jira, Slack, Notion)."""

from eng_memory_os.domain.integration.interfaces import (
    IntegrationAdapter,
    IntegrationConfig,
    IntegrationType,
)

__all__ = [
    "IntegrationAdapter",
    "IntegrationConfig",
    "IntegrationType",
]
