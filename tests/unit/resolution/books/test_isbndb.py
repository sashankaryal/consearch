"""Tests for ISBNdb resolver."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from consearch.core.identifiers import ISBN
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolverConfig
from consearch.resolution.books.isbndb import ISBNDbResolver


@pytest.fixture
def resolver() -> ISBNDbResolver:
    """Create an ISBNdb resolver with test API key."""
    config = ResolverConfig(api_key="test-api-key")
    return ISBNDbResolver(config)


@pytest.fixture
def resolver_no_retry() -> ISBNDbResolver:
    """Create an ISBNdb resolver with no 429 retries (for testing rate limits)."""
    config = ResolverConfig(
        api_key="test-api-key",
        rate_limit=RateLimitConfig(retry_on_429=False),
    )
    return ISBNDbResolver(config)


@pytest.fixture
def isbn_response_data() -> dict:
    """Sample ISBNdb API response."""
    return {
        "book": {
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "title_long": "Clean Code: A Handbook of Agile Software Craftsmanship (Robert C. Martin Series)",
            "isbn": "0134093410",
            "isbn13": "9780134093413",
            "authors": ["Robert C. Martin"],
            "publisher": "Prentice Hall",
            "date_published": "2008-08-01",
            "pages": 464,
            "subjects": ["Computer programming", "Software engineering"],
            "synopsis": "A handbook of agile software craftsmanship.",
            "image": "https://images.isbndb.com/covers/34/13/9780134093413.jpg",
            "language": "en",
            "edition": "1st",
        }
    }


@pytest.fixture
def search_response_data() -> dict:
    """Sample ISBNdb search response."""
    return {
        "total": 1,
        "books": [
            {
                "title": "Clean Code",
                "isbn13": "9780134093413",
                "authors": ["Robert C. Martin"],
                "publisher": "Prentice Hall",
            }
        ],
    }


# ============================================================================
# Resolver Configuration Tests
# ============================================================================


class TestISBNDbResolverConfig:
    """Tests for ISBNdb resolver configuration."""

    def test_source_name(self, resolver: ISBNDbResolver):
        """Source name should be ISBNDB."""
        assert resolver.source_name == SourceName.ISBNDB

    def test_base_url(self, resolver: ISBNDbResolver):
        """Base URL should be api2.isbndb.com."""
        assert resolver.BASE_URL == "https://api2.isbndb.com"

    def test_priority(self, resolver: ISBNDbResolver):
        """Priority should be 10 (primary)."""
        assert resolver.priority == 10

    def test_supported_input_types(self, resolver: ISBNDbResolver):
        """Should support ISBN and title search."""
        assert InputType.ISBN_10 in resolver.supported_input_types
        assert InputType.ISBN_13 in resolver.supported_input_types
        assert InputType.TITLE in resolver.supported_input_types

    def test_requires_api_key(self):
        """Should raise ValueError without API key."""
        with pytest.raises(ValueError, match="ISBNDb requires an API key"):
            ISBNDbResolver()

    def test_enabled_with_api_key(self, resolver: ISBNDbResolver):
        """Resolver should be enabled with API key."""
        assert resolver.is_enabled is True


# ============================================================================
# ISBN Search Tests
# ============================================================================


class TestISBNDbISBNSearch:
    """Tests for ISBN search functionality."""

    @respx.mock
    async def test_isbn13_success(
        self,
        resolver: ISBNDbResolver,
        isbn_response_data: dict,
    ):
        """Successful ISBN-13 lookup should return book record."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1
        assert result.source == SourceName.ISBNDB

        record = result.records[0]
        assert "Clean Code" in record.title
        assert record.identifiers.isbn_13 == "9780134093413"
        assert record.publisher == "Prentice Hall"
        assert record.pages == 464

    @respx.mock
    async def test_isbn_not_found(self, resolver: ISBNDbResolver):
        """ISBN not found should return NOT_FOUND status."""
        respx.get("https://api2.isbndb.com/book/9780000000002").mock(
            return_value=Response(404, json={"message": "Not found"})
        )

        isbn = ISBN.parse("9780000000002")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0

    @respx.mock
    async def test_authorization_header(self, resolver: ISBNDbResolver):
        """Request should include Authorization header with API key."""
        route = respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(200, json={"book": {"title": "Test"}})
        )

        isbn = ISBN.parse("9780134093413")
        await resolver.search_by_isbn(isbn)

        # Check Authorization header was sent
        assert "Authorization" in route.calls[0].request.headers
        assert route.calls[0].request.headers["Authorization"] == "test-api-key"

    @respx.mock
    async def test_rate_limit_error(self, resolver_no_retry: ISBNDbResolver):
        """Rate limit error should be handled."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(429, headers={"Retry-After": "60"})
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver_no_retry.search_by_isbn(isbn)

        assert result.status in (ResolutionStatus.RATE_LIMITED, ResolutionStatus.ERROR)


# ============================================================================
# Title Search Tests
# ============================================================================


class TestISBNDbTitleSearch:
    """Tests for title search functionality."""

    @respx.mock
    async def test_title_search_success(
        self,
        resolver: ISBNDbResolver,
        search_response_data: dict,
    ):
        """Successful title search should return book records."""
        respx.get("https://api2.isbndb.com/books/Clean%20Code").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.search_by_title("Clean Code")

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) >= 1

    @respx.mock
    async def test_title_search_no_results(self, resolver: ISBNDbResolver):
        """Title search with no results should return NOT_FOUND."""
        respx.get("https://api2.isbndb.com/books/Nonexistent").mock(
            return_value=Response(200, json={"total": 0, "books": []})
        )

        result = await resolver.search_by_title("Nonexistent")

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0


# ============================================================================
# Record Parsing Tests
# ============================================================================


class TestISBNDbRecordParsing:
    """Tests for parsing ISBNdb response data."""

    @respx.mock
    async def test_parses_all_fields(
        self,
        resolver: ISBNDbResolver,
        isbn_response_data: dict,
    ):
        """All available fields should be parsed correctly."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.title == "Clean Code: A Handbook of Agile Software Craftsmanship"
        assert record.year == 2008
        assert record.publisher == "Prentice Hall"
        assert record.pages == 464
        assert record.edition == "1st"
        assert record.language == "en"
        assert len(record.authors) == 1
        assert record.authors[0].name == "Robert C. Martin"
        assert record.abstract == "A handbook of agile software craftsmanship."
        assert "images.isbndb.com" in record.cover_image_url

    @respx.mock
    async def test_handles_missing_fields(self, resolver: ISBNDbResolver):
        """Missing fields should be handled gracefully."""
        minimal_data = {
            "book": {
                "title": "Minimal Book",
                "isbn13": "9780134093413",
            }
        }
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(200, json=minimal_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        record = result.records[0]
        assert record.title == "Minimal Book"
        assert record.year is None
        assert record.publisher is None

    @respx.mock
    async def test_source_metadata_included(
        self,
        resolver: ISBNDbResolver,
        isbn_response_data: dict,
    ):
        """Source metadata should be included in record."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.source_metadata is not None
        assert record.source_metadata.source == SourceName.ISBNDB


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestISBNDbErrorHandling:
    """Tests for error handling."""

    @respx.mock
    async def test_server_error(self, resolver: ISBNDbResolver):
        """Server error should return ERROR status."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(return_value=Response(500))

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.ERROR
        assert result.error_message is not None

    @respx.mock
    async def test_unauthorized_error(self, resolver: ISBNDbResolver):
        """Unauthorized error should return ERROR status."""
        respx.get("https://api2.isbndb.com/book/9780134093413").mock(
            return_value=Response(401, json={"message": "Unauthorized"})
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.ERROR
