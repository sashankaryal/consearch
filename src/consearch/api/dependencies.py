"""FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from consearch.cache.client import AsyncRedisClient
    from consearch.config import ConsearchSettings
    from consearch.resolution.registry import ResolverRegistry
    from consearch.search.client import AsyncMeilisearchClient
    from consearch.search.indexer import SearchIndexer
    from consearch.services.resolution import ResolutionService
    from consearch.services.search import SearchService


@lru_cache
def get_settings() -> ConsearchSettings:
    """Get cached application settings."""
    from consearch.config import ConsearchSettings

    return ConsearchSettings()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """
    Get database session from app state.

    Yields a session that is automatically closed after the request.
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_cache_client(request: Request) -> AsyncRedisClient | None:
    """Get Redis cache client from app state."""
    return getattr(request.app.state, "cache_client", None)


async def get_resolver_registry(request: Request) -> ResolverRegistry:
    """Get resolver registry from app state."""
    return request.app.state.resolver_registry


async def get_search_client(request: Request) -> AsyncMeilisearchClient | None:
    """Get Meilisearch client from app state."""
    return getattr(request.app.state, "search_client", None)


async def get_search_indexer(request: Request) -> SearchIndexer | None:
    """Get search indexer from app state."""
    return getattr(request.app.state, "search_indexer", None)


async def get_resolution_service(
    session: AsyncSession = Depends(get_db_session),
    registry: ResolverRegistry = Depends(get_resolver_registry),
    cache: AsyncRedisClient | None = Depends(get_cache_client),
    indexer: SearchIndexer | None = Depends(get_search_indexer),
) -> ResolutionService:
    """Get resolution service with all dependencies."""
    from consearch.services.resolution import ResolutionService

    return ResolutionService(
        session=session,
        resolver_registry=registry,
        cache=cache,
        indexer=indexer,
    )


async def get_search_service(
    session: AsyncSession = Depends(get_db_session),
    search_client: AsyncMeilisearchClient | None = Depends(get_search_client),
) -> SearchService | None:
    """Get search service if Meilisearch is available."""
    if search_client is None:
        return None

    from consearch.services.search import SearchService

    return SearchService(session=session, search_client=search_client)


# Type aliases for cleaner dependency injection
Settings = Annotated["ConsearchSettings", Depends(get_settings)]
DBSession = Annotated["AsyncSession", Depends(get_db_session)]
CacheClient = Annotated["AsyncRedisClient | None", Depends(get_cache_client)]
Resolvers = Annotated["ResolverRegistry", Depends(get_resolver_registry)]
SearchClient = Annotated["AsyncMeilisearchClient | None", Depends(get_search_client)]
ResolveService = Annotated["ResolutionService", Depends(get_resolution_service)]
SearchSvc = Annotated["SearchService | None", Depends(get_search_service)]
