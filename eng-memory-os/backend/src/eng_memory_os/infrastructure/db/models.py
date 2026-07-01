"""
SQLAlchemy ORM models.

Maps domain entities to database tables. These models live in the
infrastructure layer — the domain layer never imports from here.
Conversion between domain entities and ORM models happens in the repository.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class MemoryModel(Base):
    """ORM model for the Memory aggregate."""

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_uri: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Scores
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    decay_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Provenance
    provenance_algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="sha256")
    provenance_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Tags
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Indexes
    __table_args__ = (
        Index("ix_memories_status", "status"),
        Index("ix_memories_author", "author"),
        Index("ix_memories_source_type", "source_type"),
        Index("ix_memories_decay_factor", "decay_factor"),
        Index("ix_memories_created_at", "created_at"),
        Index("ix_memories_updated_at", "updated_at"),
    )


class MemoryChunkModel(Base):
    """ORM model for memory chunks (used for metadata; vectors are in Qdrant)."""

    __tablename__ = "memory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_chunks_memory_id_index", "memory_id", "chunk_index"),
    )


class KnowledgeNodeModel(Base):
    """ORM model for knowledge graph nodes (relational metadata)."""

    __tablename__ = "knowledge_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_memory_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    pagerank_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    degree_centrality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_nodes_entity_type", "entity_type"),
        Index("ix_nodes_name", "name"),
    )


class KnowledgeEdgeModel(Base):
    """ORM model for knowledge graph edges."""

    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_memory_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_edges_source_target", "source_node_id", "target_node_id"),
        Index("ix_edges_relationship_type", "relationship_type"),
    )


class UserModel(Base):
    """ORM model for system users (authentication & RBAC)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QueryLogModel(Base):
    """ORM model for query audit logs."""

    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    classified_intent: Mapped[str] = mapped_column(String(50), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feedback_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5 thumbs
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_query_logs_user_created", "user_id", "created_at"),
    )
