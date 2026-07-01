"""
CORS middleware configuration.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def configure_cors(app: FastAPI, allowed_origins: list[str] | None = None) -> None:
    """Configure CORS for the FastAPI application.

    In development, allows all origins. In production, restricts to
    the provided list of allowed origins.
    """
    origins = allowed_origins or [
        "http://localhost:3000",      # Next.js dev server
        "http://localhost:3001",      # Alternative dev port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Response-Time-Ms",
        ],
    )
