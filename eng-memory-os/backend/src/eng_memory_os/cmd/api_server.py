"""
FastAPI application factory.

Creates the API server with:
- Lifespan management (startup/shutdown)
- CORS middleware
- Request logging middleware
- Global exception handlers
- REST API routes (memories, knowledge, system)
- WebSocket endpoint (streaming queries)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from eng_memory_os.cmd.config import Settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and tear down services."""
    from eng_memory_os.presentation.dependencies import (
        get_settings,
        initialize_services,
        shutdown_services,
    )

    settings = get_settings()
    logger.info(
        "starting_eng_memory_os",
        environment=settings.app_env,
        debug=settings.app_debug,
    )

    await initialize_services(settings)
    logger.info("all_services_ready")

    yield

    await shutdown_services()
    logger.info("eng_memory_os_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    app = FastAPI(
        title="Engineering Memory OS",
        description=(
            "AI-powered organizational memory system for engineering teams. "
            "Ingests engineering artifacts, builds a knowledge graph, and answers "
            "questions with citation-backed, anti-hallucination responses."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # --- Middleware ---
    from eng_memory_os.presentation.middleware.cors_middleware import configure_cors
    from eng_memory_os.presentation.middleware.logging_middleware import (
        RequestLoggingMiddleware,
        register_exception_handlers,
    )

    configure_cors(app)
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    # --- REST Routes ---
    from eng_memory_os.presentation.routes.memory_routes import router as memory_router
    from eng_memory_os.presentation.routes.knowledge_routes import router as knowledge_router
    from eng_memory_os.presentation.routes.system_routes import router as system_router
    from eng_memory_os.presentation.routes.integration_routes import router as integration_router

    app.include_router(memory_router)
    app.include_router(knowledge_router)
    app.include_router(system_router)
    app.include_router(integration_router)

    # --- WebSocket ---
    from eng_memory_os.presentation.ws.query_stream import router as ws_router
    app.include_router(ws_router)

    # --- Root endpoint ---
    @app.get("/", tags=["root"])
    async def root():
        return {
            "name": "Engineering Memory OS",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/system/health",
        }

    return app


# Entry point for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "eng_memory_os.cmd.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
