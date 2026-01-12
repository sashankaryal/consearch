"""Tests for Google Books resolver."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from consearch.core.identifiers import ISBN
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolverConfig
from consearch.resolution.books.google_books import GoogleBooksResolver


@pytest.fixture
def resolver() -> GoogleBooksResolver:
    """Create a Google Books resolver."""
    return GoogleBooksResolver()


@pytest.fixture
def resolver_with_key() -> GoogleBooksResolver:
    """Create a Google Books resolver with API key."""
    config = ResolverConfig(api_key="test-api-key")
    return GoogleBooksResolver(config)


@pytest.fixture
def resolver_no_retry() -> GoogleBooksResolver:
    """Create a Google Books resolver with no 429 retries (for testing rate limits)."""
    config = ResolverConfig(rate_limit=RateLimitConfig(retry_on_429=False))
    return GoogleBooksResolver(config)


@pytest.fixture
def isbn_response_data() -> dict:
    """Sample Google Books API response for ISBN lookup."""
    return {
        "kind": "books#volumes",
        "totalItems": 1,
        "items": [
            {
                "kind": "books#volume",
                "id": "hjEFCAAAQBAJ",
                "volumeInfo": {
                    "title": "Clean Code",
                    "subtitle": "A Handbook of Agile Software Craftsmanship",
                    "authors": ["Robert C. Martin"],
                    "publisher": "Pearson Education",
                    "publishedDate": "2008-08-01",
                    "description": "A handbook of agile software craftsmanship.",
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "0134093410"},
                        {"type": "ISBN_13", "identifier": "9780134093413"},
                    ],
                    "pageCount": 464,
                    "categories": ["Computers / Programming / General"],
                    "imageLinks": {
                        "thumbnail": "http://books.google.com/books/content?id=hjEFCAAAQBAJ",
                    },
                    "language": "en",
                },
            }
        ],
    }


@pytest.fixture
def empty_response_data() -> dict:
    """Sample Google Books API response with no results."""
    return {
        "kind": "books#volumes",
        "totalItems": 0,
    }


# ============================================================================
# Resolver Configuration Tests
# ============================================================================


class TestGoogleBooksResolverConfig:
    """Tests for Google Books resolver configuration."""

    def test_source_name(self, resolver: GoogleBooksResolver):
        """Source name should be GOOGLE_BOOKS."""
        assert resolver.source_name == SourceName.GOOGLE_BOOKS

    def test_base_url(self, resolver: GoogleBooksResolver):
        """Base URL should be googleapis.com."""
        assert resolver.BASE_URL == "https://www.googleapis.com/books/v1"

    def test_priority(self, resolver: GoogleBooksResolver):
        """Priority should be 50 (fallback)."""
        assert resolver.priority == 50

    def test_supported_input_types(self, resolver: GoogleBooksResolver):
        """Should support ISBN and title search."""
        assert InputType.ISBN_10 in resolver.supported_input_types
        assert InputType.ISBN_13 in resolver.supported_input_types
        assert InputType.TITLE in resolver.supported_input_types

    def test_enabled_without_key(self, resolver: GoogleBooksResolver):
        """Resolver should be enabled without API key (public API)."""
        assert resolver.is_enabled is True


# ============================================================================
# ISBN Search Tests
# ============================================================================


class TestGoogleBooksISBNSearch:
    """Tests for ISBN search functionality."""

    @respx.mock
    async def test_isbn13_success(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """Successful ISBN-13 lookup should return book record."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1
        assert result.source == SourceName.GOOGLE_BOOKS

        record = result.records[0]
        assert record.title == "Clean Code"
        assert record.identifiers.isbn_13 == "9780134093413"
        assert record.identifiers.google_books_id == "hjEFCAAAQBAJ"

    @respx.mock
    async def test_isbn_query_format(self, resolver: GoogleBooksResolver):
        """ISBN search should use isbn: query prefix."""
        route = respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json={"totalItems": 0})
        )

        isbn = ISBN.parse("9780134093413")
        await resolver.search_by_isbn(isbn)

        # Check query parameter format
        url = str(route.calls[0].request.url)
        assert "isbn:" in url or "isbn%3A" in url

    @respx.mock
    async def test_isbn_not_found(
        self,
        resolver: GoogleBooksResolver,
        empty_response_data: dict,
    ):
        """ISBN not found should return NOT_FOUND status."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=empty_response_data)
        )

        isbn = ISBN.parse("9780000000002")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0

    @respx.mock
    async def test_api_key_included(
        self,
        resolver_with_key: GoogleBooksResolver,
    ):
        """Request should include API key when provided."""
        route = respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json={"totalItems": 0})
        )

        isbn = ISBN.parse("9780134093413")
        await resolver_with_key.search_by_isbn(isbn)

        # Check key parameter
        url = str(route.calls[0].request.url)
        assert "key=" in url


# ============================================================================
# Title Search Tests
# ============================================================================


class TestGoogleBooksTitleSearch:
    """Tests for title search functionality."""

    @respx.mock
    async def test_title_search_success(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """Successful title search should return book records."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        result = await resolver.search_by_title("Clean Code")

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) >= 1

    @respx.mock
    async def test_title_search_with_author(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """Title search with author should use intitle: and inauthor: queries."""
        route = respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        result = await resolver.search_by_title("Clean Code", author="Robert Martin")

        assert result.status == ResolutionStatus.SUCCESS
        # Check query includes author
        url = str(route.calls[0].request.url)
        assert "inauthor" in url.lower() or "inauthor%3A" in url

    @respx.mock
    async def test_title_search_no_results(
        self,
        resolver: GoogleBooksResolver,
        empty_response_data: dict,
    ):
        """Title search with no results should return NOT_FOUND."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=empty_response_data)
        )

        result = await resolver.search_by_title("Nonexistent Book XYZ123")

        assert result.status == ResolutionStatus.NOT_FOUND


# ============================================================================
# Record Parsing Tests
# ============================================================================


class TestGoogleBooksRecordParsing:
    """Tests for parsing Google Books response data."""

    @respx.mock
    async def test_parses_all_fields(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """All available fields should be parsed correctly."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.title == "Clean Code"
        assert record.year == 2008
        assert record.publisher == "Pearson Education"
        assert record.pages == 464
        assert record.language == "en"
        assert len(record.authors) == 1
        assert record.authors[0].name == "Robert C. Martin"
        assert record.abstract == "A handbook of agile software craftsmanship."
        assert record.identifiers.isbn_10 == "0134093410"
        assert record.identifiers.isbn_13 == "9780134093413"
        assert record.identifiers.google_books_id == "hjEFCAAAQBAJ"

    @respx.mock
    async def test_handles_missing_fields(self, resolver: GoogleBooksResolver):
        """Missing fields should be handled gracefully."""
        minimal_data = {
            "kind": "books#volumes",
            "totalItems": 1,
            "items": [
                {
                    "id": "test123",
                    "volumeInfo": {
                        "title": "Minimal Book",
                    },
                }
            ],
        }
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
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
    async def test_image_url_extraction(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """Cover image URL should be extracted from imageLinks."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.cover_image_url is not None
        assert "books.google.com" in record.cover_image_url

    @respx.mock
    async def test_source_metadata_included(
        self,
        resolver: GoogleBooksResolver,
        isbn_response_data: dict,
    ):
        """Source metadata should be included in record."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.source_metadata is not None
        assert record.source_metadata.source == SourceName.GOOGLE_BOOKS


# ============================================================================
# Fetch by ID Tests
# ============================================================================


class TestGoogleBooksFetchById:
    """Tests for fetch_by_id method."""

    @respx.mock
    async def test_fetch_by_id_success(
        self,
        resolver: GoogleBooksResolver,
    ):
        """fetch_by_id should return book record."""
        volume_data = {
            "id": "hjEFCAAAQBAJ",
            "volumeInfo": {
                "title": "Clean Code",
            },
        }
        respx.get("https://www.googleapis.com/books/v1/volumes/hjEFCAAAQBAJ").mock(
            return_value=Response(200, json=volume_data)
        )

        record = await resolver.fetch_by_id("hjEFCAAAQBAJ")

        assert record is not None
        assert record.title == "Clean Code"

    @respx.mock
    async def test_fetch_by_id_not_found(self, resolver: GoogleBooksResolver):
        """fetch_by_id with invalid ID should return None."""
        respx.get("https://www.googleapis.com/books/v1/volumes/invalid").mock(
            return_value=Response(404)
        )

        record = await resolver.fetch_by_id("invalid")

        assert record is None


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestGoogleBooksErrorHandling:
    """Tests for error handling."""

    @respx.mock
    async def test_server_error(self, resolver: GoogleBooksResolver):
        """Server error should return ERROR status."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(500)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.ERROR
        assert result.error_message is not None

    @respx.mock
    async def test_rate_limit_error(self, resolver_no_retry: GoogleBooksResolver):
        """Rate limit error should be handled."""
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=Response(429)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver_no_retry.search_by_isbn(isbn)

        assert result.status in (ResolutionStatus.RATE_LIMITED, ResolutionStatus.ERROR)
