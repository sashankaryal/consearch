"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConsearchSettings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="CONSEARCH_",
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://consearch:consearch@localhost:5433/consearch",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: RedisDsn | None = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (optional)",
    )
    cache_ttl: int = Field(
        default=3600,
        description="Default cache TTL in seconds",
    )

    # Meilisearch
    meilisearch_url: str | None = Field(
        default="http://localhost:7700",
        description="Meilisearch URL (optional)",
    )
    meilisearch_key: str | None = Field(
        default="dev-master-key",
        description="Meilisearch API key",
    )

    # External APIs - Books
    isbndb_api_key: str | None = Field(
        default=None,
        description="ISBNdb API key (required for primary book resolver)",
    )
    google_books_api_key: str | None = Field(
        default=None,
        description="Google Books API key (optional, increases rate limits)",
    )

    # External APIs - Papers
    crossref_email: str | None = Field(
        default=None,
        description="Email for Crossref polite pool (recommended)",
    )
    semantic_scholar_api_key: str | None = Field(
        default=None,
        description="Semantic Scholar API key (optional, increases rate limits)",
    )

    # App settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Rate limiting defaults
    default_rate_limit_rps: float = Field(
        default=1.0,
        description="Default requests per second for resolvers",
    )

    # Deduplication settings
    fuzzy_match_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for fuzzy matching",
    )


@lru_cache
def get_settings() -> ConsearchSettings:
    """Get cached settings instance."""
    return ConsearchSettings()
