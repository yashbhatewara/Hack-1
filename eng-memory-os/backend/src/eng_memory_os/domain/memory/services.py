"""
Memory domain service.

Contains domain logic that doesn't naturally belong to a single entity,
such as decay calculations and importance scoring heuristics.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from eng_memory_os.domain.shared.types import DecayFactor, ImportanceScore


class MemoryDomainService:
    """Stateless domain service for Memory-related calculations."""

    # Default half-life in hours: a memory loses half its relevance
    # after this many hours without being accessed.
    DEFAULT_HALF_LIFE_HOURS: float = 168.0  # 1 week

    @staticmethod
    def calculate_decay(
        current_decay: DecayFactor,
        hours_since_last_access: float,
        half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
    ) -> DecayFactor:
        """Calculate the new decay factor using exponential decay.

        Uses the formula: D(t) = D₀ × e^(-λt)
        where λ = ln(2) / half_life

        Args:
            current_decay: The current decay factor.
            hours_since_last_access: Hours since the memory was last accessed.
            half_life_hours: The half-life in hours (how long until decay reaches 50%).

        Returns:
            The new DecayFactor, clamped to [0.0, 1.0].
        """
        if hours_since_last_access <= 0:
            return current_decay

        decay_constant = math.log(2) / half_life_hours
        new_value = float(current_decay) * math.exp(-decay_constant * hours_since_last_access)
        return DecayFactor(max(0.0, min(1.0, new_value)))

    @staticmethod
    def calculate_importance(
        source_type: str,
        content_length: int,
        has_code_blocks: bool = False,
        has_architecture_keywords: bool = False,
        mention_count: int = 0,
    ) -> ImportanceScore:
        """Heuristic importance scoring for newly ingested memories.

        Assigns a base score based on source type, then applies
        boosting factors for content characteristics.

        Args:
            source_type: The MemorySource type string.
            content_length: Length of the raw content in characters.
            has_code_blocks: Whether the content contains code blocks.
            has_architecture_keywords: Whether architecture-related terms are present.
            mention_count: Number of @-mentions or cross-references.

        Returns:
            An ImportanceScore in [1, 10].
        """
        # Base scores by source type
        base_scores: dict[str, float] = {
            "postmortem": 9.0,
            "incident_report": 8.5,
            "architecture_doc": 8.0,
            "pull_request": 6.0,
            "code_review": 6.0,
            "meeting_notes": 5.0,
            "jira_ticket": 5.0,
            "slack_thread": 4.0,
            "notion_page": 5.5,
            "manual_input": 5.0,
        }

        score = base_scores.get(source_type, 5.0)

        # Content length boost: longer, detailed content is generally more valuable
        if content_length > 5000:
            score += 0.5
        elif content_length > 2000:
            score += 0.3

        # Code blocks indicate technical specificity
        if has_code_blocks:
            score += 0.5

        # Architecture keywords indicate high-level decisions
        if has_architecture_keywords:
            score += 1.0

        # Cross-references indicate connected knowledge
        if mention_count > 0:
            score += min(mention_count * 0.2, 1.0)

        return ImportanceScore(max(1.0, min(10.0, score)))

    @staticmethod
    def hours_since(timestamp: datetime) -> float:
        """Calculate hours elapsed since the given timestamp."""
        delta = datetime.now(timezone.utc) - timestamp
        return delta.total_seconds() / 3600.0

    @staticmethod
    def detect_architecture_keywords(content: str) -> bool:
        """Check if content contains architecture-related terminology."""
        keywords = {
            "architecture", "design decision", "adr", "trade-off", "tradeoff",
            "scalability", "microservice", "monolith", "event-driven",
            "cqrs", "saga", "bounded context", "domain model",
            "api gateway", "load balancer", "circuit breaker",
            "database migration", "schema change", "breaking change",
            "deployment strategy", "blue-green", "canary",
            "service mesh", "observability", "sla", "slo", "sli",
        }
        content_lower = content.lower()
        return any(kw in content_lower for kw in keywords)

    @staticmethod
    def detect_code_blocks(content: str) -> bool:
        """Check if content contains fenced code blocks."""
        return "```" in content or content.count("    ") > 5
