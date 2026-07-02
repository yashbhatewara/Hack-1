"""
Application configuration via environment variables.

Uses pydantic-settings for typed, validated configuration with
automatic .env file loading.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-to-a-secure-random-string"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "eng_memory"
    postgres_password: str = "eng_memory_dev_password"
    postgres_db: str = "eng_memory_os"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection: str = "eng_memory_chunks"

    # --- Cognee ---
    cognee_graph_backend: str = "networkx"

    # --- LLM Gateway ---
    llm_primary_provider: str = "openai"
    llm_fallback_provider: str = "ollama"

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 1536
    nvidia_api_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_embedding_model: str = "nomic-embed-text"

    # LLM Circuit Breaker
    llm_circuit_breaker_threshold_ms: int = 5000
    llm_max_retries: int = 3
    llm_retry_backoff_base: float = 2.0

    # --- JWT ---
    jwt_secret_key: str = "change-me-to-a-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- Encryption ---
    encryption_key: str = "change-me-to-a-32-byte-hex-key"

    # --- CORS ---
    @property
    def cors_origins(self) -> list[str]:
        if self.app_env == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return []

    # --- Observability ---
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "eng-memory-os"
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings instance."""
    return Settings()
