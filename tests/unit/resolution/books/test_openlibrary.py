"""Tests for OpenLibrary resolver."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from consearch.core.identifiers import ISBN
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.books.openlibrary import OpenLibraryResolver


@pytest.fixture
def resolver() -> OpenLibraryResolver:
    """Create an OpenLibrary resolver."""
    return OpenLibraryResolver()


@pytest.fixture
def isbn_response_data() -> dict:
    """Sample OpenLibrary ISBN response."""
    return {
        "key": "/books/OL12345M",
        "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
        "authors": [{"key": "/authors/OL123A"}],
        "publishers": ["Prentice Hall"],
        "publish_date": "2008",
        "number_of_pages": 464,
        "covers": [8090614],
        "isbn_10": ["0134093410"],
        "isbn_13": ["9780134093413"],
        "subjects": ["Computer programming", "Software engineering"],
        "works": [{"key": "/works/OL45678W"}],
    }


@pytest.fixture
def search_response_data() -> dict:
    """Sample OpenLibrary search response."""
    return {
        "numFound": 1,
        "docs": [
            {
                "key": "/works/OL45678W",
                "title": "Clean Code",
                "author_name": ["Robert C. Martin"],
                "first_publish_year": 2008,
                "isbn": ["0134093410", "9780134093413"],
                "publisher": ["Prentice Hall"],
                "subject": ["Computer programming"],
            }
        ],
    }


# ============================================================================
# Resolver Configuration Tests
# ============================================================================


class TestOpenLibraryResolverConfig:
    """Tests for OpenLibrary resolver configuration."""

    def test_source_name(self, resolver: OpenLibraryResolver):
        """Source name should be OPEN_LIBRARY."""
        assert resolver.source_name == SourceName.OPEN_LIBRARY

    def test_base_url(self, resolver: OpenLibraryResolver):
        """Base URL should be openlibrary.org."""
        assert resolver.BASE_URL == "https://openlibrary.org"

    def test_priority(self, resolver: OpenLibraryResolver):
        """Priority should be 100 (fallback)."""
        assert resolver.priority == 100

    def test_supported_input_types(self, resolver: OpenLibraryResolver):
        """Should support ISBN and title search."""
        assert InputType.ISBN_10 in resolver.supported_input_types
        assert InputType.ISBN_13 in resolver.supported_input_types
        assert InputType.TITLE in resolver.supported_input_types
        assert InputType.DOI not in resolver.supported_input_types

    def test_supports_isbn10(self, resolver: OpenLibraryResolver):
        """Should support ISBN-10."""
        assert resolver.supports(InputType.ISBN_10) is True

    def test_supports_isbn13(self, resolver: OpenLibraryResolver):
        """Should support ISBN-13."""
        assert resolver.supports(InputType.ISBN_13) is True

    def test_supports_title(self, resolver: OpenLibraryResolver):
        """Should support title search."""
        assert resolver.supports(InputType.TITLE) is True


# ============================================================================
# ISBN Search Tests
# ============================================================================


class TestOpenLibraryISBNSearch:
    """Tests for ISBN search functionality."""

    @respx.mock
    async def test_isbn13_success(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """Successful ISBN-13 lookup should return book record."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1
        assert result.source == SourceName.OPEN_LIBRARY

        record = result.records[0]
        assert "Clean Code" in record.title
        assert record.identifiers.isbn_13 == "9780134093413"

    @respx.mock
    async def test_isbn10_success(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """Successful ISBN-10 lookup should return book record."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("0134093410")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1

    @respx.mock
    async def test_isbn_not_found(self, resolver: OpenLibraryResolver):
        """ISBN not found should return NOT_FOUND status."""
        respx.get("https://openlibrary.org/isbn/9780000000002.json").mock(
            return_value=Response(404)
        )

        isbn = ISBN.parse("9780000000002")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0

    @respx.mock
    async def test_isbn_server_error(self, resolver: OpenLibraryResolver):
        """Server error should return ERROR status."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(500)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.ERROR
        assert result.error_message is not None


# ============================================================================
# Title Search Tests
# ============================================================================


class TestOpenLibraryTitleSearch:
    """Tests for title search functionality."""

    @respx.mock
    async def test_title_search_success(
        self,
        resolver: OpenLibraryResolver,
        search_response_data: dict,
    ):
        """Successful title search should return book records."""
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.search_by_title("Clean Code")

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) >= 1
        assert result.source == SourceName.OPEN_LIBRARY

    @respx.mock
    async def test_title_search_with_author(
        self,
        resolver: OpenLibraryResolver,
        search_response_data: dict,
    ):
        """Title search with author should include author in request."""
        route = respx.get("https://openlibrary.org/search.json").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.search_by_title("Clean Code", author="Robert Martin")

        assert result.status == ResolutionStatus.SUCCESS
        # Verify author was passed in params
        assert "author" in str(route.calls[0].request.url)

    @respx.mock
    async def test_title_search_no_results(self, resolver: OpenLibraryResolver):
        """Title search with no results should return NOT_FOUND."""
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=Response(200, json={"numFound": 0, "docs": []})
        )

        result = await resolver.search_by_title("Nonexistent Book XYZ123")

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0


# ============================================================================
# Resolve Method Tests
# ============================================================================


class TestOpenLibraryResolve:
    """Tests for the resolve method."""

    @respx.mock
    async def test_resolve_isbn13(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """resolve() with ISBN-13 should call search_by_isbn."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        result = await resolver.resolve("9780134093413", InputType.ISBN_13)

        assert result.status == ResolutionStatus.SUCCESS
        assert result.records[0].identifiers.isbn_13 == "9780134093413"

    @respx.mock
    async def test_resolve_title(
        self,
        resolver: OpenLibraryResolver,
        search_response_data: dict,
    ):
        """resolve() with TITLE should call search_by_title."""
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.resolve("Clean Code", InputType.TITLE)

        assert result.status == ResolutionStatus.SUCCESS


# ============================================================================
# Record Parsing Tests
# ============================================================================


class TestOpenLibraryRecordParsing:
    """Tests for parsing OpenLibrary response data."""

    @respx.mock
    async def test_parses_all_fields(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """All available fields should be parsed correctly."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.title == "Clean Code: A Handbook of Agile Software Craftsmanship"
        assert record.year == 2008
        assert record.publisher == "Prentice Hall"
        assert record.pages == 464
        assert record.identifiers.isbn_10 == "0134093410"
        assert record.identifiers.isbn_13 == "9780134093413"
        assert "Computer programming" in record.subjects
        assert record.cover_image_url is not None
        assert "8090614" in record.cover_image_url

    @respx.mock
    async def test_handles_missing_fields(self, resolver: OpenLibraryResolver):
        """Missing fields should be handled gracefully."""
        minimal_data = {
            "key": "/books/OL12345M",
            "title": "Minimal Book",
        }
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=minimal_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        assert result.status == ResolutionStatus.SUCCESS
        record = result.records[0]
        assert record.title == "Minimal Book"
        assert record.year is None
        assert record.publisher is None
        assert record.pages is None

    @respx.mock
    async def test_source_metadata_included(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """Source metadata should be included in record."""
        respx.get("https://openlibrary.org/isbn/9780134093413.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        isbn = ISBN.parse("9780134093413")
        result = await resolver.search_by_isbn(isbn)

        record = result.records[0]
        assert record.source_metadata is not None
        assert record.source_metadata.source == SourceName.OPEN_LIBRARY
        assert record.source_metadata.raw_data == isbn_response_data


# ============================================================================
# Fetch by ID Tests
# ============================================================================


class TestOpenLibraryFetchById:
    """Tests for fetch_by_id method."""

    @respx.mock
    async def test_fetch_by_id_success(
        self,
        resolver: OpenLibraryResolver,
        isbn_response_data: dict,
    ):
        """fetch_by_id should return book record."""
        respx.get("https://openlibrary.org/books/OL12345M.json").mock(
            return_value=Response(200, json=isbn_response_data)
        )

        record = await resolver.fetch_by_id("/books/OL12345M")

        assert record is not None
        assert "Clean Code" in record.title

    @respx.mock
    async def test_fetch_by_id_not_found(self, resolver: OpenLibraryResolver):
        """fetch_by_id with invalid ID should return None."""
        respx.get("https://openlibrary.org/books/OL99999M.json").mock(return_value=Response(404))

        record = await resolver.fetch_by_id("/books/OL99999M")

        assert record is None
