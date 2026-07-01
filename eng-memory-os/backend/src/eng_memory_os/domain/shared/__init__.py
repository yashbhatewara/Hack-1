"""Shared kernel: cross-cutting domain primitives used by all bounded contexts."""

from eng_memory_os.domain.shared.events import DomainEvent
from eng_memory_os.domain.shared.errors import (
    DomainError,
    EntityNotFoundError,
    ValidationError,
    InsufficientEvidenceError,
    AuthorizationError,
)
from eng_memory_os.domain.shared.types import EntityId, Timestamp

__all__ = [
    "DomainEvent",
    "DomainError",
    "EntityNotFoundError",
    "ValidationError",
    "InsufficientEvidenceError",
    "AuthorizationError",
    "EntityId",
    "Timestamp",
]
