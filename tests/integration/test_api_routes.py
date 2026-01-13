"""Integration tests for API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = [pytest.mark.integration]


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthEndpoint:
    """Tests for the /api/v1/health endpoint."""

    async def test_health_returns_200(self, test_client: AsyncClient):
        """Health endpoint should return 200."""
        response = await test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    async def test_health_includes_version(self, test_client: AsyncClient):
        """Health response should include version."""
        response = await test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    async def test_health_includes_services(self, test_client: AsyncClient):
        """Health response should include service statuses."""
        response = await test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        # Should have at least these services
        assert isinstance(data["services"], dict)


class TestReadinessEndpoint:
    """Tests for the /api/v1/ready endpoint."""

    async def test_ready_returns_200(self, test_client: AsyncClient):
        """Readiness endpoint should return 200."""
        response = await test_client.get("/api/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert isinstance(data["ready"], bool)


# ============================================================================
# Resolve Endpoint Tests
# ============================================================================


class TestDetectEndpoint:
    """Tests for the /api/v1/resolve/detect endpoint."""

    async def test_detect_isbn13(self, test_client: AsyncClient):
        """Should detect ISBN-13."""
        response = await test_client.post(
            "/api/v1/resolve/detect",
            params={"query": "9780134093413"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedType"] == "isbn_13"
        assert data["confidence"] >= 0.9

    async def test_detect_isbn10(self, test_client: AsyncClient):
        """Should detect ISBN-10."""
        response = await test_client.post(
            "/api/v1/resolve/detect",
            params={"query": "0134093410"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedType"] == "isbn_10"

    async def test_detect_doi(self, test_client: AsyncClient):
        """Should detect DOI."""
        response = await test_client.post(
            "/api/v1/resolve/detect",
            params={"query": "10.1038/nature12373"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedType"] == "doi"
        # DOIs can be for both books and papers, so consumableType is None
        assert data["consumableType"] is None

    async def test_detect_arxiv(self, test_client: AsyncClient):
        """Should detect arXiv ID."""
        response = await test_client.post(
            "/api/v1/resolve/detect",
            params={"query": "arXiv:2301.12345"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedType"] == "arxiv"

    async def test_detect_title(self, test_client: AsyncClient):
        """Should detect title as fallback."""
        response = await test_client.post(
            "/api/v1/resolve/detect",
            params={"query": "Clean Code by Robert Martin"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedType"] == "title"


class TestResolveBookEndpoint:
    """Tests for the /api/v1/resolve/book endpoint."""

    async def test_resolve_book_validates_request(self, test_client: AsyncClient):
        """Should validate request schema."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={"query": ""},  # Empty query
        )

        assert response.status_code == 422  # Validation error

    async def test_resolve_book_accepts_valid_request(self, test_client: AsyncClient):
        """Should accept valid request."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={"query": "9780134093413"},
        )

        # May return 200 with NOT_FOUND status if no resolvers are mocked
        assert response.status_code == 200
        data = response.json()
        assert "detectedInputType" in data
        assert "status" in data
        assert "records" in data
        assert "totalDurationMs" in data

    async def test_resolve_book_with_input_type(self, test_client: AsyncClient):
        """Should accept explicit input type."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={
                "query": "9780134093413",
                "inputType": "isbn_13",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedInputType"] == "isbn_13"

    async def test_resolve_book_with_camel_case(self, test_client: AsyncClient):
        """Should accept camelCase field names."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={
                "query": "Clean Code",
                "inputType": "title",
                "includeRawData": True,
            },
        )

        assert response.status_code == 200

    async def test_resolve_book_invalid_input_type_for_book(self, test_client: AsyncClient):
        """Should reject paper-only input types."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={
                "query": "arXiv:2301.12345",
                # arXiv IDs are paper-only, should fail for book resolution
            },
        )

        # Should return 400 for paper-only input type
        assert response.status_code == 400


class TestResolvePaperEndpoint:
    """Tests for the /api/v1/resolve/paper endpoint."""

    async def test_resolve_paper_validates_request(self, test_client: AsyncClient):
        """Should validate request schema."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={"query": ""},  # Empty query
        )

        assert response.status_code == 422  # Validation error

    async def test_resolve_paper_accepts_valid_request(self, test_client: AsyncClient):
        """Should accept valid request."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={"query": "10.1038/nature12373"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "detectedInputType" in data
        assert "status" in data
        assert "records" in data
        assert "sourcesTried" in data
        assert "totalDurationMs" in data

    async def test_resolve_paper_with_doi(self, test_client: AsyncClient):
        """Should handle DOI input."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={
                "query": "10.1038/nature12373",
                "inputType": "doi",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedInputType"] == "doi"

    async def test_resolve_paper_with_arxiv(self, test_client: AsyncClient):
        """Should handle arXiv input."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={
                "query": "2301.12345",
                "inputType": "arxiv",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detectedInputType"] == "arxiv"

    async def test_resolve_paper_invalid_input_type_for_paper(self, test_client: AsyncClient):
        """Should reject book-only input types."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={
                "query": "9780134093413",
                # ISBN will be detected, which is book-only
            },
        )

        # Should return 400 for book-only input type
        assert response.status_code == 400


# ============================================================================
# Search Endpoint Tests
# ============================================================================


class TestSearchBooksEndpoint:
    """Tests for the /api/v1/search/books endpoint."""

    async def test_search_books_requires_query(self, test_client: AsyncClient):
        """Should require query parameter."""
        response = await test_client.get("/api/v1/search/books")

        assert response.status_code == 422  # Missing required parameter

    async def test_search_books_returns_503_without_meilisearch(
        self, test_client: AsyncClient
    ):
        """Should return 503 when Meilisearch is not available."""
        response = await test_client.get(
            "/api/v1/search/books",
            params={"query": "python"},
        )

        # Without Meilisearch configured, should return 503
        assert response.status_code == 503
        data = response.json()
        assert "not available" in data["detail"].lower()

    async def test_search_books_validates_pagination(self, test_client: AsyncClient):
        """Should validate pagination parameters."""
        response = await test_client.get(
            "/api/v1/search/books",
            params={
                "query": "python",
                "page": 0,  # Invalid - must be >= 1
            },
        )

        assert response.status_code == 422

    async def test_search_books_validates_page_size(self, test_client: AsyncClient):
        """Should validate page size parameter."""
        response = await test_client.get(
            "/api/v1/search/books",
            params={
                "query": "python",
                "pageSize": 1000,  # Invalid - max is 100
            },
        )

        assert response.status_code == 422


class TestSearchPapersEndpoint:
    """Tests for the /api/v1/search/papers endpoint."""

    async def test_search_papers_requires_query(self, test_client: AsyncClient):
        """Should require query parameter."""
        response = await test_client.get("/api/v1/search/papers")

        assert response.status_code == 422

    async def test_search_papers_returns_503_without_meilisearch(
        self, test_client: AsyncClient
    ):
        """Should return 503 when Meilisearch is not available."""
        response = await test_client.get(
            "/api/v1/search/papers",
            params={"query": "machine learning"},
        )

        assert response.status_code == 503

    async def test_search_papers_validates_year_range(self, test_client: AsyncClient):
        """Should validate year range parameters."""
        response = await test_client.get(
            "/api/v1/search/papers",
            params={
                "query": "AI",
                "yearMin": 500,  # Invalid - must be >= 1000
            },
        )

        assert response.status_code == 422


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling across endpoints."""

    async def test_404_for_unknown_endpoint(self, test_client: AsyncClient):
        """Should return 404 for unknown endpoints."""
        response = await test_client.get("/api/v1/unknown")

        assert response.status_code == 404

    async def test_405_for_wrong_method(self, test_client: AsyncClient):
        """Should return 405 for wrong HTTP method."""
        response = await test_client.get("/api/v1/resolve/book")

        assert response.status_code == 405

    async def test_json_content_type(self, test_client: AsyncClient):
        """Responses should have JSON content type."""
        response = await test_client.get("/api/v1/health")

        assert response.headers["content-type"].startswith("application/json")


# ============================================================================
# Response Schema Tests
# ============================================================================


class TestResponseSchemas:
    """Tests for response schema compliance."""

    async def test_resolve_book_response_schema(self, test_client: AsyncClient):
        """Book resolution response should match expected schema."""
        response = await test_client.post(
            "/api/v1/resolve/book",
            json={"query": "Clean Code", "inputType": "title"},
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "detectedInputType" in data
        assert "status" in data
        assert "records" in data
        assert isinstance(data["records"], list)
        assert "sourcesTried" in data
        assert isinstance(data["sourcesTried"], list)
        assert "totalDurationMs" in data
        assert isinstance(data["totalDurationMs"], (int, float))

    async def test_resolve_paper_response_schema(self, test_client: AsyncClient):
        """Paper resolution response should match expected schema."""
        response = await test_client.post(
            "/api/v1/resolve/paper",
            json={"query": "machine learning", "inputType": "title"},
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "detectedInputType" in data
        assert "status" in data
        assert "records" in data
        assert isinstance(data["records"], list)
        assert "sourcesTried" in data
        assert "totalDurationMs" in data

    async def test_health_response_schema(self, test_client: AsyncClient):
        """Health response should match expected schema."""
        response = await test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "version" in data
        assert "services" in data
        assert isinstance(data["services"], dict)


# ============================================================================
# Integration with Services (requires mocked services)
# ============================================================================


class TestWithMockedServices:
    """Tests that require mocked external services."""

    async def test_resolve_book_with_mocked_resolver(self, db_session_factory):
        """Should return book records when resolver is mocked."""
        from unittest.mock import AsyncMock

        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from consearch.api.dependencies import (
            get_cache_client,
            get_db_session,
            get_resolution_service,
            get_resolver_registry,
            get_search_indexer,
        )
        from consearch.api.routes import health_router, resolve_router, search_router
        from consearch.core.models import Author, BookRecord, Identifiers, SourceMetadata
        from consearch.core.types import ResolutionStatus, SourceName
        from consearch.resolution.base import ResolutionResult
        from consearch.resolution.chain import AggregatedResult
        from consearch.resolution.registry import ResolverRegistry

        # Create a mock resolution service that returns test data
        mock_service = AsyncMock()
        mock_service.resolve_book.return_value = AggregatedResult(
            primary_result=ResolutionResult(
                status=ResolutionStatus.SUCCESS,
                source=SourceName.OPEN_LIBRARY,
                records=[
                    BookRecord(
                        title="Clean Code",
                        authors=[Author(name="Robert C. Martin")],
                        year=2008,
                        identifiers=Identifiers(
                            isbn_13="9780132350884",
                            isbn_10="0132350882",
                        ),
                        publisher="Prentice Hall",
                        source_metadata=SourceMetadata(
                            source=SourceName.OPEN_LIBRARY,
                            source_id="OL12345W",
                        ),
                    )
                ],
                duration_ms=50.0,
            ),
            fallback_results=[],
            all_records=[
                BookRecord(
                    title="Clean Code",
                    authors=[Author(name="Robert C. Martin")],
                    year=2008,
                    identifiers=Identifiers(
                        isbn_13="9780132350884",
                        isbn_10="0132350882",
                    ),
                    publisher="Prentice Hall",
                    source_metadata=SourceMetadata(
                        source=SourceName.OPEN_LIBRARY,
                        source_id="OL12345W",
                    ),
                )
            ],
        )

        # Create app with mocked service
        app = FastAPI()
        app.include_router(health_router, prefix="/api/v1")
        app.include_router(resolve_router, prefix="/api/v1")
        app.include_router(search_router, prefix="/api/v1")

        app.state.db_session_factory = db_session_factory
        app.state.cache_client = None
        app.state.search_client = None
        app.state.search_indexer = None

        registry = ResolverRegistry()
        app.state.resolver_registry = registry

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

        async def override_resolution_service():
            return mock_service

        app.dependency_overrides[get_db_session] = override_db_session
        app.dependency_overrides[get_resolver_registry] = override_resolver_registry
        app.dependency_overrides[get_cache_client] = override_cache_client
        app.dependency_overrides[get_search_indexer] = override_search_indexer
        app.dependency_overrides[get_resolution_service] = override_resolution_service

        # Test the endpoint
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resolve/book",
                json={"query": "9780132350884"},  # ISBN-13
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert len(data["records"]) == 1
            assert data["records"][0]["title"] == "Clean Code"
            assert data["records"][0]["authors"][0]["name"] == "Robert C. Martin"
            assert data["records"][0]["identifiers"]["isbn13"] == "9780132350884"

        # Cleanup
        app.dependency_overrides.clear()
        await registry.close_all()

    async def test_search_books_with_meilisearch(self, db_session_factory, search_client):
        """Should search books when Meilisearch is available."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from consearch.api.dependencies import (
            get_cache_client,
            get_db_session,
            get_resolver_registry,
            get_search_client,
            get_search_indexer,
        )
        from consearch.api.routes import health_router, resolve_router, search_router
        from consearch.resolution.registry import ResolverRegistry

        # Index some test data
        test_books = [
            {
                "id": "test-book-1",
                "title": "Clean Code",
                "authors": ["Robert C. Martin"],
                "year": 2008,
                "language": "en",
            },
            {
                "id": "test-book-2",
                "title": "The Pragmatic Programmer",
                "authors": ["David Thomas", "Andrew Hunt"],
                "year": 2019,
                "language": "en",
            },
        ]

        # Add documents to the test index
        await search_client._client.index(search_client._books_index).add_documents(test_books)
        # Wait for indexing to complete
        await search_client._client.index(search_client._books_index).wait_for_task(
            (await search_client._client.index(search_client._books_index).get_tasks()).results[0].uid
        )

        # Create app with search client
        app = FastAPI()
        app.include_router(health_router, prefix="/api/v1")
        app.include_router(resolve_router, prefix="/api/v1")
        app.include_router(search_router, prefix="/api/v1")

        app.state.db_session_factory = db_session_factory
        app.state.cache_client = None
        app.state.search_client = search_client

        registry = ResolverRegistry()
        app.state.resolver_registry = registry

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

        async def override_search_client():
            return search_client

        async def override_search_indexer():
            return None

        app.dependency_overrides[get_db_session] = override_db_session
        app.dependency_overrides[get_resolver_registry] = override_resolver_registry
        app.dependency_overrides[get_cache_client] = override_cache_client
        app.dependency_overrides[get_search_client] = override_search_client
        app.dependency_overrides[get_search_indexer] = override_search_indexer

        # Test the endpoint
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/search/books",
                params={"query": "Clean Code"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 1
            # The search should find "Clean Code"
            titles = [r["title"] for r in data["results"]]
            assert "Clean Code" in titles

        # Cleanup
        app.dependency_overrides.clear()
        await registry.close_all()
