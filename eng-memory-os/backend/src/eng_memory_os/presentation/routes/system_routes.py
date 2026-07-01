"""
System REST API routes.

Endpoints for health checks, provider status, and token usage monitoring.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from eng_memory_os.presentation.dependencies import (
    get_llm_gateway,
    get_vector_store,
    get_uptime,
)
from eng_memory_os.presentation.schemas import (
    HealthResponseDTO,
    ProviderStatusDTO,
    TokenUsageDTO,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


# ──────────────────── GET /system/health ────────────────────

@router.get(
    "/health",
    response_model=HealthResponseDTO,
    summary="System health check",
    description="Returns the health status of all system components.",
)
async def health_check(
    llm_gateway=Depends(get_llm_gateway),
):
    uptime = get_uptime()

    # Check LLM provider statuses
    provider_statuses = await llm_gateway.get_all_provider_statuses()
    provider_dict = {
        provider.value: stat.value
        for provider, stat in provider_statuses.items()
    }

    return HealthResponseDTO(
        status="ok",
        version="0.1.0",
        uptime_seconds=round(uptime, 1),
        database="connected",
        qdrant="connected",
        llm_providers=provider_dict,
    )


# ──────────────────── GET /system/providers ────────────────────

@router.get(
    "/providers",
    response_model=list[ProviderStatusDTO],
    summary="Get LLM provider statuses",
)
async def get_provider_statuses(
    llm_gateway=Depends(get_llm_gateway),
):
    statuses = await llm_gateway.get_all_provider_statuses()

    return [
        ProviderStatusDTO(
            provider=provider.value,
            status=stat.value,
            circuit_breaker_state=stat.value,
        )
        for provider, stat in statuses.items()
    ]


# ──────────────────── GET /system/tokens ────────────────────

@router.get(
    "/tokens",
    response_model=TokenUsageDTO,
    summary="Get aggregate token usage and costs",
)
async def get_token_usage(
    llm_gateway=Depends(get_llm_gateway),
):
    totals = await llm_gateway.get_total_token_usage()

    return TokenUsageDTO(
        total_prompt_tokens=totals.get("total_prompt_tokens", 0),
        total_completion_tokens=totals.get("total_completion_tokens", 0),
        total_tokens=totals.get("total_tokens", 0),
        total_cost_usd=totals.get("total_cost_usd", 0.0),
        total_requests=totals.get("total_requests", 0),
    )
