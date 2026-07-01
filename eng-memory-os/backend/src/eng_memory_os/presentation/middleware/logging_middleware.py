"""
Request logging and error handling middleware.

Provides structured request/response logging with correlation IDs,
and a global exception handler that converts domain errors to HTTP responses.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from eng_memory_os.domain.shared.errors import (
    CircuitBreakerOpenError,
    DomainError,
    EntityNotFoundError,
    IngestionError,
    InsufficientEvidenceError,
    LLMGatewayError,
    ValidationError,
)

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with timing, status code, and correlation ID."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        # Bind request context to structlog
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Add request_id to request state for downstream use
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 1),
            )

            # Add correlation headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 1))

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request_failed",
                duration_ms=round(duration_ms, 1),
                error=str(exc),
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars(
                "request_id", "method", "path"
            )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for domain errors."""

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "error": "EntityNotFound",
                "detail": str(exc),
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "detail": str(exc),
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(IngestionError)
    async def ingestion_error_handler(request: Request, exc: IngestionError):
        return JSONResponse(
            status_code=500,
            content={
                "error": "IngestionError",
                "detail": f"Stage: {exc.stage} — {exc.reason}",
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(InsufficientEvidenceError)
    async def insufficient_evidence_handler(request: Request, exc: InsufficientEvidenceError):
        return JSONResponse(
            status_code=200,  # Still 200 — degraded responses are valid
            content={
                "error": "InsufficientEvidence",
                "detail": str(exc),
                "is_degraded": True,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(CircuitBreakerOpenError)
    async def circuit_breaker_handler(request: Request, exc: CircuitBreakerOpenError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "CircuitBreakerOpen",
                "detail": f"Provider '{exc.provider}' is temporarily unavailable. "
                          f"Recovery in {exc.recovery_seconds}s.",
                "request_id": getattr(request.state, "request_id", ""),
            },
            headers={"Retry-After": str(int(exc.recovery_seconds))},
        )

    @app.exception_handler(LLMGatewayError)
    async def llm_gateway_handler(request: Request, exc: LLMGatewayError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "LLMGatewayError",
                "detail": str(exc),
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=500,
            content={
                "error": exc.__class__.__name__,
                "detail": str(exc),
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
