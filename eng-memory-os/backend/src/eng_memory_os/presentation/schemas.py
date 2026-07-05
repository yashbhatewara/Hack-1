"""
Pydantic DTOs (Data Transfer Objects) for the REST API.

These schemas define the contract between the frontend and backend.
They validate input, serialize output, and are completely decoupled
from the domain entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ───────────────────────────── Enums ─────────────────────────────

class SourceTypeDTO(str, Enum):
    GITHUB_PR = "github_pr"
    GITHUB_ISSUE = "github_issue"
    JIRA_TICKET = "jira_ticket"
    SLACK_THREAD = "slack_thread"
    CONFLUENCE_PAGE = "confluence_page"
    NOTION_DOC = "notion_doc"
    INCIDENT_REPORT = "incident_report"
    ADR = "adr"
    RUNBOOK = "runbook"
    CODE_REVIEW = "code_review"
    MEETING_NOTES = "meeting_notes"
    MANUAL_INPUT = "manual_input"


class MemoryStatusDTO(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    FAILED = "failed"


# ───────────────────────────── Memory ─────────────────────────────

class IngestMemoryRequestDTO(BaseModel):
    """Request body for memory ingestion."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "raw_content": "## ADR-042: Switch from REST to gRPC for inter-service communication...",
            "source_uri": "https://github.com/org/repo/blob/main/docs/adr/042-grpc.md",
            "source_type": "adr",
            "author": "alice@company.com",
            "title": "ADR-042: REST to gRPC Migration",
            "tags": ["architecture", "grpc", "migration"],
        }
    })

    raw_content: str = Field(..., min_length=10, max_length=500_000, description="The raw text content to ingest")
    source_uri: str = Field(..., min_length=1, max_length=2048, description="Unique URI identifying the source")
    source_type: SourceTypeDTO = Field(..., description="The type of engineering artifact")
    author: str = Field(..., min_length=1, max_length=255, description="Author email or identifier")
    title: str = Field(..., min_length=1, max_length=500, description="Title of the memory")
    tags: list[str] = Field(default_factory=list, max_length=50, description="Optional tags for categorization")


class IngestMemoryResponseDTO(BaseModel):
    """Response from memory ingestion."""
    memory_id: str
    status: MemoryStatusDTO
    importance_score: float


class MemoryDTO(BaseModel):
    """Full memory representation for GET endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_uri: str
    source_type: str
    title: str
    author: str
    raw_content: str
    importance_score: float
    confidence_score: float
    decay_factor: float
    status: MemoryStatusDTO
    tags: list[str]
    access_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None


class MemoryListResponseDTO(BaseModel):
    """Paginated list of memories."""
    items: list[MemoryDTO]
    total: int
    offset: int
    limit: int


class MemoryStatsDTO(BaseModel):
    """Memory statistics by status."""
    pending: int = 0
    processing: int = 0
    active: int = 0
    stale: int = 0
    archived: int = 0
    failed: int = 0
    total: int = 0
    total_queries: int = 0


# ───────────────────────────── Query ─────────────────────────────

class QueryRequestDTO(BaseModel):
    """Request body for querying the knowledge system."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "Why did we switch from Redis to Valkey for session caching?",
            "mode": "agent",
        }
    })

    query: str = Field(..., min_length=3, max_length=2000, description="The natural language query")
    mode: str = Field("agent", description="Query execution mode: 'agent' or 'rag'")


class CitationDTO(BaseModel):
    """Citation reference in a query response."""
    evidence_id: str
    memory_id: str
    source_uri: str
    relevance_score: float
    snippet: str


class QueryResponseDTO(BaseModel):
    """Response from the query endpoint."""
    response_id: str
    response_text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_degraded: bool
    citations: list[CitationDTO]
    total_time_ms: float
    retry_count: int


# ───────────────────────────── Knowledge Graph ─────────────────────────────

class KnowledgeNodeDTO(BaseModel):
    """Knowledge graph node representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    name: str
    description: str
    aliases: list[str] = Field(default_factory=list)
    pagerank_score: float = 0.0
    degree_centrality: float = 0.0
    source_memory_count: int = 0


class KnowledgeEdgeDTO(BaseModel):
    """Knowledge graph edge representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    weight: float = 1.0
    description: str = ""


class SubgraphResponseDTO(BaseModel):
    """Subgraph response for visualization."""
    nodes: list[KnowledgeNodeDTO]
    edges: list[KnowledgeEdgeDTO]
    stats: dict[str, int] = Field(default_factory=dict)


# ───────────────────────────── System ─────────────────────────────

class HealthResponseDTO(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float
    database: str = "connected"
    qdrant: str = "connected"
    llm_providers: dict[str, str] = Field(default_factory=dict)


class ProviderStatusDTO(BaseModel):
    """LLM provider health status."""
    provider: str
    status: str
    circuit_breaker_state: str


class TokenUsageDTO(BaseModel):
    """Aggregate token usage statistics."""
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_requests: int
    provider_breakdown: dict[str, dict] = Field(default_factory=dict)


class ErrorResponseDTO(BaseModel):
    """Standard error response body."""
    error: str
    detail: str
    request_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
