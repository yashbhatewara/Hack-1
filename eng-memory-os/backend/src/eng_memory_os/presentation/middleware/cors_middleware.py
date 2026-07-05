"""
CORS middleware configuration.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def configure_cors(app: FastAPI, allowed_origins: list[str] | None = None) -> None:
    """Configure CORS for the FastAPI application.

    Origins are read from the CORS_ORIGINS env var (comma-separated).
    Falls back to localhost dev origins if not set.
    """
    env_origins = os.environ.get("CORS_ORIGINS", "")
    env_list = [o.strip() for o in env_origins.split(",") if o.strip()]

    origins = allowed_origins or env_list or [
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
