"""
Shared type aliases used across all bounded contexts.

These are pure Python types with no external framework dependencies,
ensuring the domain layer remains entirely framework-agnostic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import NewType


# --- Identity Types ---
EntityId = NewType("EntityId", uuid.UUID)


def new_entity_id() -> EntityId:
    """Generate a new unique entity identifier."""
    return EntityId(uuid.uuid4())


def entity_id_from_str(value: str) -> EntityId:
    """Parse an entity ID from its string representation."""
    return EntityId(uuid.UUID(value))


# --- Temporal Types ---
Timestamp = NewType("Timestamp", datetime)


def now_utc() -> Timestamp:
    """Get the current UTC timestamp."""
    return Timestamp(datetime.now(timezone.utc))


def timestamp_from_iso(value: str) -> Timestamp:
    """Parse a timestamp from an ISO 8601 string."""
    return Timestamp(datetime.fromisoformat(value))


# --- Score Types ---
class BoundedFloat:
    """A float constrained to a [min_val, max_val] range.

    Used as a base for confidence scores, importance scores, etc.
    Immutable after creation.
    """

    __slots__ = ("_value", "_min_val", "_max_val")

    def __init__(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> None:
        if not (min_val <= value <= max_val):
            raise ValueError(
                f"Value {value} out of bounds [{min_val}, {max_val}]"
            )
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_min_val", min_val)
        object.__setattr__(self, "_max_val", max_val)

    @property
    def value(self) -> float:
        return self._value  # type: ignore[return-value]

    def __float__(self) -> float:
        return self._value  # type: ignore[return-value]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BoundedFloat):
            return self._value == other._value
        if isinstance(other, (int, float)):
            return self._value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{self.__class__.__name__} is immutable")


class ConfidenceScore(BoundedFloat):
    """A confidence score in the range [0.0, 1.0]."""

    def __init__(self, value: float) -> None:
        super().__init__(value, min_val=0.0, max_val=1.0)


class ImportanceScore(BoundedFloat):
    """An importance score in the range [1, 10]."""

    def __init__(self, value: float) -> None:
        super().__init__(value, min_val=1.0, max_val=10.0)


class DecayFactor(BoundedFloat):
    """A decay factor in the range [0.0, 1.0]. 1.0 = fully retained, 0.0 = fully decayed."""

    def __init__(self, value: float) -> None:
        super().__init__(value, min_val=0.0, max_val=1.0)
