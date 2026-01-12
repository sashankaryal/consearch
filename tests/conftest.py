"""Shared test fixtures for all tests."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from consearch.config import ConsearchSettings
from consearch.core.models import (
    Author,
    BookRecord,
    Identifiers,
    PaperRecord,
    SourceMetadata,
)
from consearch.core.types import SourceName

if TYPE_CHECKING:
    pass


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_author() -> Author:
    """Create a sample author."""
    return Author(
        name="Jane Smith",
        given_name="Jane",
        family_name="Smith",
        orcid="0000-0001-2345-6789",
        affiliations=["Example University", "Research Institute"],
    )


@pytest.fixture
def sample_author_minimal() -> Author:
    """Create a minimal author with only required fields."""
    return Author(name="John Doe")


@pytest.fixture
def sample_identifiers_book() -> Identifiers:
    """Create sample book identifiers."""
    return Identifiers(
        isbn_10="0134093410",
        isbn_13="9780134093413",
        doi="10.1234/example.book",
        openlibrary_id="OL12345W",
        google_books_id="abc123",
    )


@pytest.fixture
def sample_identifiers_paper() -> Identifiers:
    """Create sample paper identifiers."""
    return Identifiers(
        doi="10.1038/nature12373",
        arxiv_id="1234.56789",
        pmid="12345678",
        semantic_scholar_id="abc123def456",
        crossref_id="10.1038/nature12373",
    )


@pytest.fixture
def sample_source_metadata() -> SourceMetadata:
    """Create sample source metadata."""
    return SourceMetadata(
        source=SourceName.OPEN_LIBRARY,
        source_id="OL12345W",
        retrieved_at=datetime(2024, 1, 15, 12, 0, 0),
        reliability_score=0.95,
        raw_data={"key": "value"},
    )


@pytest.fixture
def sample_book_record(
    sample_author: Author,
    sample_identifiers_book: Identifiers,
    sample_source_metadata: SourceMetadata,
) -> BookRecord:
    """Create a fully populated sample book record."""
    return BookRecord(
        id=uuid4(),
        title="The Art of Programming",
        authors=[sample_author],
        year=2023,
        publication_date=None,
        abstract="A comprehensive guide to programming best practices.",
        url="https://example.com/book",
        language="en",
        identifiers=sample_identifiers_book,
        source_metadata=sample_source_metadata,
        confidence=1.0,
        publisher="Tech Press",
        edition="2nd Edition",
        pages=450,
        subjects=["Programming", "Software Engineering", "Computer Science"],
        cover_image_url="https://example.com/cover.jpg",
    )


@pytest.fixture
def sample_book_record_minimal() -> BookRecord:
    """Create a minimal book record with only required fields."""
    return BookRecord(title="Minimal Book")


@pytest.fixture
def sample_paper_record(
    sample_author: Author,
    sample_identifiers_paper: Identifiers,
) -> PaperRecord:
    """Create a fully populated sample paper record."""
    return PaperRecord(
        id=uuid4(),
        title="Deep Learning for Natural Language Processing",
        authors=[sample_author],
        year=2023,
        publication_date=None,
        abstract="We present a novel approach to NLP using transformer architectures.",
        url="https://doi.org/10.1038/nature12373",
        language="en",
        identifiers=sample_identifiers_paper,
        source_metadata=SourceMetadata(
            source=SourceName.CROSSREF,
            source_id="10.1038/nature12373",
            reliability_score=0.90,
        ),
        confidence=1.0,
        journal="Nature",
        volume="500",
        issue="7463",
        pages_range="476-480",
        citation_count=1500,
        references=["10.1000/ref1", "10.1000/ref2"],
        fields_of_study=["Machine Learning", "Natural Language Processing"],
        pdf_url="https://arxiv.org/pdf/1234.56789.pdf",
    )


@pytest.fixture
def sample_paper_record_minimal() -> PaperRecord:
    """Create a minimal paper record with only required fields."""
    return PaperRecord(title="Minimal Paper")


# ============================================================================
# Settings Fixtures
# ============================================================================


@pytest.fixture
def mock_settings() -> ConsearchSettings:
    """Create mock settings for testing."""
    return ConsearchSettings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/15",  # Use DB 15 for tests
        meilisearch_url="http://localhost:7700",
        meilisearch_key="test-master-key",
        isbndb_api_key="test-isbndb-key",
        google_books_api_key="test-google-key",
        crossref_email="test@example.com",
        semantic_scholar_api_key="test-s2-key",
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
def mock_settings_minimal() -> ConsearchSettings:
    """Create minimal settings without optional services."""
    return ConsearchSettings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url=None,
        meilisearch_url=None,
        meilisearch_key=None,
        isbndb_api_key=None,
        google_books_api_key=None,
        crossref_email=None,
        semantic_scholar_api_key=None,
    )


# ============================================================================
# Test Data Constants
# ============================================================================


# Valid identifiers for testing
VALID_ISBN_10 = "0134093410"  # Clean Code
VALID_ISBN_10_X = "155860832X"  # Has X check digit
VALID_ISBN_13 = "9780134093413"
VALID_DOI = "10.1038/nature12373"
VALID_DOI_WITH_PREFIX = "doi:10.1038/nature12373"
VALID_DOI_URL = "https://doi.org/10.1038/nature12373"
VALID_ARXIV_NEW = "1234.56789"
VALID_ARXIV_NEW_VERSION = "1234.56789v2"
VALID_ARXIV_OLD = "hep-th/9901001"
VALID_PMID = "12345678"

# Invalid identifiers for testing
INVALID_ISBN_10 = "0134093411"  # Bad checksum
INVALID_ISBN_13 = "9780134093412"  # Bad checksum
INVALID_DOI = "not-a-doi"
INVALID_ARXIV = "invalid-arxiv"


@pytest.fixture
def valid_identifiers() -> dict[str, str]:
    """Return a dictionary of valid identifiers."""
    return {
        "isbn_10": VALID_ISBN_10,
        "isbn_10_x": VALID_ISBN_10_X,
        "isbn_13": VALID_ISBN_13,
        "doi": VALID_DOI,
        "doi_prefix": VALID_DOI_WITH_PREFIX,
        "doi_url": VALID_DOI_URL,
        "arxiv_new": VALID_ARXIV_NEW,
        "arxiv_versioned": VALID_ARXIV_NEW_VERSION,
        "arxiv_old": VALID_ARXIV_OLD,
        "pmid": VALID_PMID,
    }


@pytest.fixture
def invalid_identifiers() -> dict[str, str]:
    """Return a dictionary of invalid identifiers."""
    return {
        "isbn_10": INVALID_ISBN_10,
        "isbn_13": INVALID_ISBN_13,
        "doi": INVALID_DOI,
        "arxiv": INVALID_ARXIV,
    }
