"""
Base domain event infrastructure.

All bounded contexts publish domain events through this base class.
Events are immutable data records that describe something that happened
in the domain. They are consumed by event handlers in the application layer,
enabling loose coupling between bounded contexts via the Event-Driven Architecture.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Attributes:
        event_id: Unique identifier for this event instance.
        occurred_at: UTC timestamp when the event occurred.
        event_type: Fully qualified name of the event class (auto-populated).
        metadata: Optional key-value metadata (correlation IDs, causation IDs, etc.).
    """

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Return the fully qualified event type name."""
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

    def with_metadata(self, **kwargs: Any) -> DomainEvent:
        """Return a new event with additional metadata merged in.

        Since events are frozen dataclasses, this creates a copy
        with the merged metadata dictionary.
        """
        merged = {**self.metadata, **kwargs}
        # Use object.__setattr__ because frozen=True prevents normal assignment
        new_event = self.__class__(**{
            f.name: getattr(self, f.name)
            for f in self.__dataclass_fields__.values()
            if f.name != "metadata"
        }, metadata=merged)
        return new_event

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary for transport/logging."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": self.metadata,
            "payload": {
                f.name: _serialize_field(getattr(self, f.name))
                for f in self.__dataclass_fields__.values()
                if f.name not in ("event_id", "occurred_at", "metadata")
            },
        }


def _serialize_field(value: Any) -> Any:
    """Recursively serialize a field value for JSON transport."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_serialize_field(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_field(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "value"):
        return value.value
    return value
