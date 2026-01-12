"""Unit test fixtures with HTTP mocking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import respx
from httpx import Response

from consearch.resolution.base import RateLimitConfig, ResolverConfig

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ============================================================================
# HTTP Mocking Fixtures
# ============================================================================


@pytest.fixture
def respx_mock():
    """Provide a respx mock router for HTTP mocking.

    Use this when you need fine-grained control over mocked responses.
    The mock is automatically started and stopped by respx.
    """
    with respx.mock(assert_all_called=False) as router:
        yield router


# ============================================================================
# Resolver Configuration Fixtures
# ============================================================================


@pytest.fixture
def resolver_config() -> ResolverConfig:
    """Create a resolver config for testing."""
    return ResolverConfig(
        api_key="test-api-key",
        timeout=10.0,
        rate_limit=RateLimitConfig(
            requests_per_second=10.0,  # High limit for tests
            burst_size=10,
            retry_on_429=True,
            max_429_retries=2,
        ),
        enabled=True,
    )


@pytest.fixture
def resolver_config_no_key() -> ResolverConfig:
    """Create a resolver config without API key."""
    return ResolverConfig(
        api_key=None,
        timeout=10.0,
        enabled=True,
    )


@pytest.fixture
def resolver_config_disabled() -> ResolverConfig:
    """Create a disabled resolver config."""
    return ResolverConfig(enabled=False)


# ============================================================================
# Fixture Loading Utilities
# ============================================================================


def load_fixture(category: str, name: str) -> dict[str, Any]:
    """Load a JSON fixture file.

    Args:
        category: Fixture category (e.g., "books", "papers")
        name: Fixture filename without extension (e.g., "openlibrary_isbn")

    Returns:
        Parsed JSON data
    """
    fixture_path = FIXTURES_DIR / category / f"{name}.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text())


@pytest.fixture
def load_book_fixture():
    """Factory fixture to load book API response fixtures."""
    def _load(name: str) -> dict[str, Any]:
        return load_fixture("books", name)
    return _load


@pytest.fixture
def load_paper_fixture():
    """Factory fixture to load paper API response fixtures."""
    def _load(name: str) -> dict[str, Any]:
        return load_fixture("papers", name)
    return _load


# ============================================================================
# Mock Response Helpers
# ============================================================================


def mock_json_response(data: dict[str, Any], status_code: int = 200) -> Response:
    """Create a mock JSON response."""
    return Response(
        status_code=status_code,
        json=data,
        headers={"Content-Type": "application/json"},
    )


def mock_error_response(status_code: int, message: str = "Error") -> Response:
    """Create a mock error response."""
    return Response(
        status_code=status_code,
        json={"error": message},
        headers={"Content-Type": "application/json"},
    )


def mock_rate_limit_response(retry_after: int = 60) -> Response:
    """Create a mock 429 rate limit response."""
    return Response(
        status_code=429,
        json={"error": "Rate limit exceeded"},
        headers={
            "Content-Type": "application/json",
            "Retry-After": str(retry_after),
        },
    )


@pytest.fixture
def mock_responses():
    """Provide helper functions for creating mock responses."""
    return {
        "json": mock_json_response,
        "error": mock_error_response,
        "rate_limit": mock_rate_limit_response,
    }


# ============================================================================
# Book API Response Fixtures
# ============================================================================


@pytest.fixture
def openlibrary_isbn_response() -> dict[str, Any]:
    """Sample OpenLibrary API response for ISBN lookup."""
    return {
        "ISBN:9780134093413": {
            "url": "https://openlibrary.org/books/OL12345M/Clean_Code",
            "key": "/books/OL12345M",
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "authors": [{"url": "https://openlibrary.org/authors/OL123A", "name": "Robert C. Martin"}],
            "publishers": [{"name": "Prentice Hall"}],
            "publish_date": "2008",
            "number_of_pages": 464,
            "subjects": [
                {"name": "Computer programming", "url": "..."},
                {"name": "Software engineering", "url": "..."},
            ],
            "cover": {
                "small": "https://covers.openlibrary.org/b/id/123-S.jpg",
                "medium": "https://covers.openlibrary.org/b/id/123-M.jpg",
                "large": "https://covers.openlibrary.org/b/id/123-L.jpg",
            },
            "identifiers": {
                "isbn_10": ["0134093410"],
                "isbn_13": ["9780134093413"],
                "openlibrary": ["OL12345M"],
            },
        }
    }


@pytest.fixture
def isbndb_isbn_response() -> dict[str, Any]:
    """Sample ISBNDb API response for ISBN lookup."""
    return {
        "book": {
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "title_long": "Clean Code: A Handbook of Agile Software Craftsmanship",
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
        }
    }


@pytest.fixture
def google_books_isbn_response() -> dict[str, Any]:
    """Sample Google Books API response for ISBN lookup."""
    return {
        "kind": "books#volumes",
        "totalItems": 1,
        "items": [
            {
                "kind": "books#volume",
                "id": "abc123",
                "volumeInfo": {
                    "title": "Clean Code",
                    "subtitle": "A Handbook of Agile Software Craftsmanship",
                    "authors": ["Robert C. Martin"],
                    "publisher": "Prentice Hall",
                    "publishedDate": "2008-08-01",
                    "description": "A handbook of agile software craftsmanship.",
                    "pageCount": 464,
                    "categories": ["Computers / Programming / General"],
                    "imageLinks": {
                        "thumbnail": "https://books.google.com/books/content?id=abc123",
                    },
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "0134093410"},
                        {"type": "ISBN_13", "identifier": "9780134093413"},
                    ],
                    "language": "en",
                },
            }
        ],
    }


# ============================================================================
# Paper API Response Fixtures
# ============================================================================


@pytest.fixture
def crossref_doi_response() -> dict[str, Any]:
    """Sample Crossref API response for DOI lookup."""
    return {
        "status": "ok",
        "message-type": "work",
        "message": {
            "DOI": "10.1038/nature12373",
            "title": ["DNA sequencing with nanopores"],
            "author": [
                {
                    "given": "John",
                    "family": "Smith",
                    "affiliation": [{"name": "Example University"}],
                    "ORCID": "https://orcid.org/0000-0001-2345-6789",
                }
            ],
            "container-title": ["Nature"],
            "published-print": {"date-parts": [[2013, 8, 22]]},
            "volume": "500",
            "issue": "7463",
            "page": "476-480",
            "is-referenced-by-count": 1500,
            "references-count": 30,
            "abstract": "<jats:p>Abstract text here.</jats:p>",
            "URL": "https://doi.org/10.1038/nature12373",
        },
    }


@pytest.fixture
def semantic_scholar_doi_response() -> dict[str, Any]:
    """Sample Semantic Scholar API response for DOI lookup."""
    return {
        "paperId": "abc123def456",
        "title": "DNA sequencing with nanopores",
        "authors": [
            {
                "authorId": "12345",
                "name": "John Smith",
            }
        ],
        "year": 2013,
        "abstract": "Abstract text here.",
        "venue": "Nature",
        "publicationDate": "2013-08-22",
        "citationCount": 1500,
        "referenceCount": 30,
        "externalIds": {
            "DOI": "10.1038/nature12373",
            "ArXiv": "1234.56789",
            "PubMed": "12345678",
        },
        "openAccessPdf": {
            "url": "https://example.com/paper.pdf",
            "status": "GREEN",
        },
    }
