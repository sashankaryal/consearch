"""Integration test fixtures for database, Redis, and Meilisearch."""

from __future__ import annotations

import os
from typing import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from consearch.core.normalization import normalize_title
from consearch.core.types import ConsumableType
from consearch.db.base import Base
from consearch.db.models.author import AuthorModel
from consearch.db.models.work import WorkModel


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get test database URL from environment or use default."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://consearch:consearch@localhost:5433/consearch_test",
    )


@pytest.fixture(scope="function")
async def db_engine(database_url: str):
    """
    Create a fresh database engine for each test.

    Each test gets its own engine to avoid event loop mismatch issues
    with asyncpg connection pools.
    """
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=2,
        max_overflow=5,
        pool_pre_ping=True,
    )

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up all data and dispose engine
    async with engine.begin() as conn:
        # Delete in correct order to respect foreign key constraints
        await conn.execute(text("DELETE FROM work_authors"))
        await conn.execute(text("DELETE FROM work_relations"))
        await conn.execute(text("DELETE FROM works"))
        await conn.execute(text("DELETE FROM authors"))

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    """Create session factory from engine."""
    return async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(db_session_factory) -> AsyncIterator[AsyncSession]:
    """
    Get database session with automatic cleanup.

    Each test gets a fresh session. Data is committed to allow proper
    testing of persistence, but cleaned up after the test.
    """
    async with db_session_factory() as session:
        yield session


# ============================================================================
# Sample Data Fixtures
# ============================================================================


def _create_sample_author() -> AuthorModel:
    """Create a sample author model (not persisted)."""
    return AuthorModel(
        id=uuid4(),
        name="Robert C. Martin",
        name_normalized="robert c martin",
        external_ids={"orcid": "0000-0001-2345-6789"},
    )


def _create_sample_book_work(author: AuthorModel | None = None) -> WorkModel:
    """Create a sample book work model (not persisted)."""
    work = WorkModel(
        id=uuid4(),
        work_type=ConsumableType.BOOK,
        title="Clean Code: A Handbook of Agile Software Craftsmanship",
        title_normalized=normalize_title("Clean Code: A Handbook of Agile Software Craftsmanship"),
        year=2008,
        language="en",
        identifiers={
            "isbn_13": "9780134093413",
            "isbn_10": "0134093410",
            "openlibrary_id": "OL12345W",
        },
        confidence=1.0,
    )
    if author:
        work.authors.append(author)
    return work


@pytest.fixture
async def sample_author(db_session: AsyncSession) -> AuthorModel:
    """Create a sample author in the database."""
    author = _create_sample_author()
    db_session.add(author)
    await db_session.commit()
    return author


@pytest.fixture
async def sample_book_work(db_session: AsyncSession) -> WorkModel:
    """Create a sample book work with author in the database."""
    author = _create_sample_author()
    db_session.add(author)

    work = _create_sample_book_work(author)
    db_session.add(work)
    await db_session.commit()
    return work


@pytest.fixture
async def sample_paper_work(db_session: AsyncSession) -> WorkModel:
    """Create a sample paper work in the database."""
    author = AuthorModel(
        id=uuid4(),
        name="Elizabeth Pennisi",
        name_normalized="elizabeth pennisi",
        external_ids={},
    )
    db_session.add(author)

    work = WorkModel(
        id=uuid4(),
        work_type=ConsumableType.PAPER,
        title="DNA sequencing with nanopores",
        title_normalized=normalize_title("DNA sequencing with nanopores"),
        year=2013,
        language="en",
        identifiers={
            "doi": "10.1038/nature12373",
            "semantic_scholar_id": "abc123def456",
        },
        confidence=1.0,
    )
    work.authors.append(author)
    db_session.add(work)
    await db_session.commit()
    return work


@pytest.fixture
async def multiple_works(db_session: AsyncSession) -> list[WorkModel]:
    """Create multiple works for pagination/search tests."""
    works = []
    for i in range(5):
        work = WorkModel(
            id=uuid4(),
            work_type=ConsumableType.BOOK,
            title=f"Test Book {i + 1}",
            title_normalized=normalize_title(f"Test Book {i + 1}"),
            year=2020 + i,
            language="en",
            identifiers={"isbn_13": f"978000000000{i}"},
            confidence=1.0,
        )
        db_session.add(work)
        works.append(work)
    await db_session.commit()
    return works


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================


@pytest.fixture
async def test_app(db_session_factory):
    """Create test FastAPI application with mocked dependencies."""
    from fastapi import FastAPI

    from consearch.api.dependencies import (
        get_cache_client,
        get_db_session,
        get_resolver_registry,
        get_search_indexer,
    )
    from consearch.api.routes import health_router, resolve_router, search_router
    from consearch.resolution.registry import ResolverRegistry

    # Create a minimal app for testing
    app = FastAPI()
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(resolve_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")

    # Store in app state (for routes that access state directly)
    app.state.db_session_factory = db_session_factory
    app.state.cache_client = None
    app.state.search_client = None
    app.state.search_indexer = None

    registry = ResolverRegistry()
    app.state.resolver_registry = registry

    # Override dependency injection functions
    async def override_db_session():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_resolver_registry():
        return registry

    async def override_cache_client():
        return None

    async def override_search_indexer():
        return None

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_resolver_registry] = override_resolver_registry
    app.dependency_overrides[get_cache_client] = override_cache_client
    app.dependency_overrides[get_search_indexer] = override_search_indexer

    yield app

    # Cleanup
    app.dependency_overrides.clear()
    await registry.close_all()


@pytest.fixture
async def test_client(test_app) -> AsyncIterator[AsyncClient]:
    """Create async HTTP test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# Redis Fixtures (Optional - skipped if not available)
# ============================================================================


@pytest.fixture
def redis_url() -> str:
    """Get test Redis URL from environment or use default."""
    return os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
async def redis_client(redis_url: str):
    """Create Redis client for testing (optional)."""
    try:
        from consearch.cache.client import AsyncRedisClient

        client = AsyncRedisClient(redis_url)
        # Verify connection
        await client.ping()
        # Clear test database
        await client._redis.flushdb()
        yield client
        # Cleanup
        await client._redis.flushdb()
        await client.close()
    except Exception:
        pytest.skip("Redis not available for integration tests")


# ============================================================================
# Meilisearch Fixtures (Optional - skipped if not available)
# ============================================================================


@pytest.fixture
def meilisearch_url() -> str:
    """Get test Meilisearch URL from environment or use default."""
    return os.getenv("TEST_MEILISEARCH_URL", "http://localhost:7700")


@pytest.fixture
def meilisearch_key() -> str | None:
    """Get test Meilisearch key from environment."""
    return os.getenv("TEST_MEILISEARCH_KEY")


@pytest.fixture
async def search_client(meilisearch_url: str, meilisearch_key: str | None):
    """Create Meilisearch client for testing (optional)."""
    try:
        from consearch.search.client import AsyncMeilisearchClient

        client = AsyncMeilisearchClient(meilisearch_url, meilisearch_key)
        # Verify connection
        await client.health()
        # Setup test indexes with unique names
        test_suffix = uuid4().hex[:8]
        client._books_index = f"books_test_{test_suffix}"
        client._papers_index = f"papers_test_{test_suffix}"
        await client.setup_indexes()
        yield client
        # Cleanup - delete test indexes
        try:
            await client._client.delete_index(client._books_index)
            await client._client.delete_index(client._papers_index)
        except Exception:
            pass
        await client.close()
    except Exception:
        pytest.skip("Meilisearch not available for integration tests")


# ============================================================================
# Marker Registration
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test requiring external services",
    )
    config.addinivalue_line(
        "markers",
        "requires_db: mark test as requiring database connection",
    )
    config.addinivalue_line(
        "markers",
        "requires_redis: mark test as requiring Redis connection",
    )
    config.addinivalue_line(
        "markers",
        "requires_meilisearch: mark test as requiring Meilisearch connection",
    )
