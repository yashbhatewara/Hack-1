"""
Domain-specific error hierarchy.

All domain errors extend DomainError so that outer layers (presentation,
infrastructure) can catch and translate them into appropriate HTTP
responses or log entries without leaking domain internals.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code for API consumers.
        details: Optional structured details about the error.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class EntityNotFoundError(DomainError):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found.",
            code="ENTITY_NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class ValidationError(DomainError):
    """Raised when domain invariants are violated."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


class InsufficientEvidenceError(DomainError):
    """Raised when the system cannot provide an answer due to lack of evidence.

    This is the core anti-hallucination mechanism: the system must
    explicitly declare when it doesn't have enough data rather than guessing.
    """

    def __init__(self, query: str, attempted_sources: list[str] | None = None) -> None:
        super().__init__(
            message=f"I do not have sufficient historical data to answer: '{query}'",
            code="INSUFFICIENT_EVIDENCE",
            details={
                "query": query,
                "attempted_sources": attempted_sources or [],
            },
        )


class AuthorizationError(DomainError):
    """Raised when a user lacks permission for the requested operation."""

    def __init__(self, action: str, resource: str) -> None:
        super().__init__(
            message=f"Not authorized to {action} on {resource}.",
            code="AUTHORIZATION_ERROR",
            details={"action": action, "resource": resource},
        )


class LLMGatewayError(DomainError):
    """Raised when all LLM providers fail."""

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(
            message=f"LLM provider '{provider}' failed: {reason}",
            code="LLM_GATEWAY_ERROR",
            details={"provider": provider, "reason": reason},
        )


class CircuitBreakerOpenError(DomainError):
    """Raised when a circuit breaker is in open state."""

    def __init__(self, service: str, recovery_seconds: float = 60.0) -> None:
        super().__init__(
            message=f"Circuit breaker open for service '{service}'. Requests temporarily blocked.",
            code="CIRCUIT_BREAKER_OPEN",
            details={"service": service, "recovery_seconds": recovery_seconds},
        )
        self.provider = service
        self.recovery_seconds = recovery_seconds


class IngestionError(DomainError):
    """Raised when memory ingestion fails at any pipeline stage."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(
            message=f"Ingestion failed at stage '{stage}': {reason}",
            code="INGESTION_ERROR",
            details={"stage": stage, "reason": reason},
        )
        self.stage = stage
        self.reason = reason
