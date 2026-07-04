"""
Integration API routes.

Provides endpoints for triggering and managing external system synchronizations.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from eng_memory_os.application.memory.ingest_memory import (
    IngestMemoryRequest,
    IngestMemoryUseCase,
)
from eng_memory_os.infrastructure.integration.github_adapter import GitHubAdapter
from eng_memory_os.presentation.dependencies import (
    get_event_bus,
    get_memory_repo,
)
from eng_memory_os.presentation.schemas import ErrorResponseDTO

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


class GitHubSyncRequestDTO(BaseModel):
    """Payload to trigger a GitHub repository sync."""

    repo_url: str = Field(
        ...,
        description="URL of the GitHub repository to sync (e.g. https://github.com/owner/repo)",
        examples=["https://github.com/huggingface/transformers"],
    )
    github_token: str | None = Field(
        None,
        description="Optional Personal Access Token (PAT) to avoid rate limits.",
    )
    limit: int = Field(
        30,
        ge=1,
        le=100,
        description="Maximum number of recent issues and pull requests to ingest.",
    )


class GitHubSyncResponseDTO(BaseModel):
    """Response returned after triggering repository sync."""

    status: str = Field(..., description="Sync outcome status.")
    repo_owner: str = Field(..., description="Repository owner name.")
    repo_name: str = Field(..., description="Repository name.")
    synced_count: int = Field(..., description="Number of issues/PRs synced.")


@router.post(
    "/github/sync",
    response_model=GitHubSyncResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Sync a GitHub repository",
    description="Fetches recent issues and pull requests (with discussion history) "
                "from a public or private GitHub repository and ingests them into memory.",
    responses={
        400: {"model": ErrorResponseDTO, "description": "Invalid repository URL or connection failed"},
        500: {"model": ErrorResponseDTO, "description": "Internal server error during synchronization"},
    },
)
async def sync_github_repository(
    body: GitHubSyncRequestDTO,
    background_tasks: BackgroundTasks,
    memory_repo=Depends(get_memory_repo),  # noqa: B008
    event_bus=Depends(get_event_bus),  # noqa: B008
):
    try:
        adapter = GitHubAdapter.from_url(body.repo_url, body.github_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # 1. Verify access to the repository
    connected = await adapter.test_connection()
    if not connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not connect to GitHub repository: {body.repo_url}. "
                   "Verify the URL and ensure you provide a valid token if the repository is private.",
        )

    # 2. Fetch recent issues/PRs
    try:
        logger.info(
            "github_sync_started",
            owner=adapter.repo_owner,
            repo=adapter.repo_name,
            limit=body.limit,
        )
        items = await adapter.fetch_recent(limit=body.limit)
    except Exception as e:
        logger.exception("github_fetch_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch items from GitHub: {e!s}",
        ) from e

    # 3. Ingest items into Memory OS in the background (prevents HTTP timeouts!)
    use_case = IngestMemoryUseCase(memory_repo=memory_repo, event_bus=event_bus)

    async def process_ingestion_background():
        success_count = 0
        for item in items:
            try:
                request = IngestMemoryRequest(
                    raw_content=item.content,
                    source_uri=item.source_uri,
                    source_type=item.source_type.value,
                    author=item.author,
                    title=item.title,
                    tags=item.tags,
                )
                await use_case.execute(request)
                success_count += 1
            except Exception:
                logger.exception("github_item_ingest_failed", uri=item.source_uri)
                continue
        logger.info(
            "github_sync_background_completed",
            owner=adapter.repo_owner,
            repo=adapter.repo_name,
            successful=success_count,
        )

    background_tasks.add_task(process_ingestion_background)

    logger.info(
        "github_sync_queued",
        owner=adapter.repo_owner,
        repo=adapter.repo_name,
        requested_limit=body.limit,
        discovered=len(items),
    )

    return GitHubSyncResponseDTO(
        status="success",
        repo_owner=adapter.repo_owner,
        repo_name=adapter.repo_name,
        synced_count=len(items),
    )
