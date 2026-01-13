"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from consearch.api.routes import health_router, resolve_router, search_router
from consearch.config import ConsearchSettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown of resources.
    """
    settings = ConsearchSettings()

    # Initialize database
    from consearch.db.base import create_engine, create_session_factory

    logger.info("Initializing database connection...")
    app.state.db_engine = create_engine(str(settings.database_url))
    app.state.db_session_factory = create_session_factory(app.state.db_engine)

    # Initialize Redis cache (optional)
    if settings.redis_url:
        try:
            from consearch.cache.client import AsyncRedisClient

            logger.info("Initializing Redis cache...")
            app.state.cache_client = AsyncRedisClient(str(settings.redis_url))
            await app.state.cache_client.connect()
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
            app.state.cache_client = None
    else:
        app.state.cache_client = None

    # Initialize Meilisearch (optional)
    if settings.meilisearch_url:
        try:
            from consearch.search.client import AsyncMeilisearchClient
            from consearch.search.indexer import SearchIndexer

            logger.info("Initializing Meilisearch...")
            app.state.search_client = AsyncMeilisearchClient(
                settings.meilisearch_url,
                settings.meilisearch_key,
            )
            # Setup indexes
            await app.state.search_client.setup_indexes()
            # Create indexer
            app.state.search_indexer = SearchIndexer(app.state.search_client)
            logger.info("Meilisearch initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Meilisearch: {e}")
            app.state.search_client = None
            app.state.search_indexer = None
    else:
        app.state.search_client = None
        app.state.search_indexer = None

    # Initialize resolver registry
    from consearch.resolution.registry import ResolverRegistry

    logger.info("Initializing resolver registry...")
    app.state.resolver_registry = ResolverRegistry.from_settings(settings)

    logger.info("Application startup complete")

    yield

    # Cleanup
    logger.info("Shutting down application...")

    # Close resolvers
    if hasattr(app.state, "resolver_registry"):
        await app.state.resolver_registry.close_all()

    # Close search client
    if hasattr(app.state, "search_client") and app.state.search_client:
        await app.state.search_client.close()

    # Close cache
    if hasattr(app.state, "cache_client") and app.state.cache_client:
        await app.state.cache_client.close()

    # Close database connections
    if hasattr(app.state, "db_engine"):
        await app.state.db_engine.dispose()

    logger.info("Application shutdown complete")


def create_app(
    *,
    title: str = "Consearch API",
    description: str = "Unified consumable search and resolution API",
    version: str = "0.1.0",
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for OpenAPI docs
        description: API description for OpenAPI docs
        version: API version
        cors_origins: List of allowed CORS origins

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Configure CORS
    if cors_origins is None:
        cors_origins = ["http://localhost:3000"]  # Default for Next.js dev

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(resolve_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")

    return app


# For uvicorn direct execution
app = create_app()
