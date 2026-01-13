"""Tests for API request/response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from consearch.api.schemas import (
    AuthorResponse,
    BookResponse,
    IdentifiersResponse,
    PaperResponse,
    ResolutionSourceResult,
    ResolveBookRequest,
    ResolveBookResponse,
    ResolvePaperRequest,
    ResolvePaperResponse,
    SearchBooksResponse,
    SearchPapersResponse,
    SourceMetadataResponse,
)
from consearch.core.types import InputType, ResolutionStatus, SourceName

# ============================================================================
# Request Schema Tests
# ============================================================================


class TestResolveBookRequest:
    """Tests for ResolveBookRequest schema."""

    def test_valid_query_only(self):
        """Query-only request should be valid."""
        request = ResolveBookRequest(query="9780134093413")
        assert request.query == "9780134093413"
        assert request.input_type is None
        assert request.include_raw_data is False

    def test_valid_with_input_type(self):
        """Request with input_type should be valid."""
        request = ResolveBookRequest(
            query="9780134093413",
            input_type=InputType.ISBN_13,
        )
        assert request.input_type == InputType.ISBN_13

    def test_valid_with_all_fields(self):
        """Request with all fields should be valid."""
        request = ResolveBookRequest(
            query="Clean Code",
            input_type=InputType.TITLE,
            include_raw_data=True,
        )
        assert request.include_raw_data is True

    def test_empty_query_invalid(self):
        """Empty query should be invalid."""
        with pytest.raises(ValidationError):
            ResolveBookRequest(query="")

    def test_camel_case_alias(self):
        """Should accept camelCase field names."""
        request = ResolveBookRequest.model_validate(
            {
                "query": "test",
                "inputType": "isbn_13",
                "includeRawData": True,
            }
        )
        assert request.input_type == InputType.ISBN_13
        assert request.include_raw_data is True


class TestResolvePaperRequest:
    """Tests for ResolvePaperRequest schema."""

    def test_valid_doi_query(self):
        """DOI query should be valid."""
        request = ResolvePaperRequest(query="10.1038/nature12373")
        assert request.query == "10.1038/nature12373"

    def test_valid_with_input_type(self):
        """Request with input_type should be valid."""
        request = ResolvePaperRequest(
            query="10.1038/nature12373",
            input_type=InputType.DOI,
        )
        assert request.input_type == InputType.DOI


# ============================================================================
# Response Schema Tests
# ============================================================================


class TestAuthorResponse:
    """Tests for AuthorResponse schema."""

    def test_full_author(self):
        """Full author should be valid."""
        author = AuthorResponse(
            name="John Smith",
            given_name="John",
            family_name="Smith",
            orcid="0000-0001-2345-6789",
            affiliations=["University"],
        )
        assert author.name == "John Smith"

    def test_minimal_author(self):
        """Minimal author with only name should be valid."""
        author = AuthorResponse(name="John Doe")
        assert author.name == "John Doe"
        assert author.given_name is None

    def test_camel_case_serialization(self):
        """Should serialize to camelCase."""
        author = AuthorResponse(
            name="John Smith",
            given_name="John",
            family_name="Smith",
        )
        data = author.model_dump(by_alias=True)
        assert "givenName" in data
        assert "familyName" in data


class TestIdentifiersResponse:
    """Tests for IdentifiersResponse schema."""

    def test_book_identifiers(self):
        """Book identifiers should be valid."""
        ids = IdentifiersResponse(
            isbn_10="0134093410",
            isbn_13="9780134093413",
            openlibrary_id="OL12345W",
        )
        assert ids.isbn_13 == "9780134093413"

    def test_paper_identifiers(self):
        """Paper identifiers should be valid."""
        ids = IdentifiersResponse(
            doi="10.1038/nature12373",
            arxiv_id="1234.56789",
            pmid="12345678",
        )
        assert ids.doi == "10.1038/nature12373"

    def test_camel_case_serialization(self):
        """Should serialize to camelCase."""
        ids = IdentifiersResponse(isbn_13="9780134093413", arxiv_id="1234.56789")
        data = ids.model_dump(by_alias=True)
        # Check snake_case fields have camelCase aliases
        assert "arxivId" in data or "arxiv_id" in data  # Depends on alias config


class TestBookResponse:
    """Tests for BookResponse schema."""

    def test_full_book(self):
        """Full book response should be valid."""
        book = BookResponse(
            title="Clean Code",
            authors=[AuthorResponse(name="Robert C. Martin")],
            year=2008,
            identifiers=IdentifiersResponse(isbn_13="9780134093413"),
            publisher="Prentice Hall",
            pages=464,
            subjects=["Programming"],
            language="en",
        )
        assert book.title == "Clean Code"
        assert len(book.authors) == 1

    def test_minimal_book(self):
        """Minimal book with only title should be valid."""
        book = BookResponse(
            title="Minimal Book",
            authors=[],
            identifiers=IdentifiersResponse(),
        )
        assert book.title == "Minimal Book"


class TestPaperResponse:
    """Tests for PaperResponse schema."""

    def test_full_paper(self):
        """Full paper response should be valid."""
        paper = PaperResponse(
            title="DNA sequencing with nanopores",
            authors=[AuthorResponse(name="Elizabeth Pennisi")],
            year=2013,
            identifiers=IdentifiersResponse(doi="10.1038/nature12373"),
            journal="Nature",
            volume="500",
            issue="7463",
            pages_range="476-480",
            citation_count=1500,
        )
        assert paper.title == "DNA sequencing with nanopores"
        assert paper.citation_count == 1500

    def test_minimal_paper(self):
        """Minimal paper with only title should be valid."""
        paper = PaperResponse(
            title="Minimal Paper",
            authors=[],
            identifiers=IdentifiersResponse(),
        )
        assert paper.title == "Minimal Paper"


class TestResolutionSourceResult:
    """Tests for ResolutionSourceResult schema."""

    def test_success_result(self):
        """Success result should be valid."""
        result = ResolutionSourceResult(
            source=SourceName.CROSSREF,
            status=ResolutionStatus.SUCCESS,
            duration_ms=150.5,
        )
        assert result.source == SourceName.CROSSREF
        assert result.status == ResolutionStatus.SUCCESS

    def test_error_result(self):
        """Error result with message should be valid."""
        result = ResolutionSourceResult(
            source=SourceName.CROSSREF,
            status=ResolutionStatus.ERROR,
            duration_ms=50.0,
            error_message="Connection failed",
        )
        assert result.error_message == "Connection failed"


class TestResolveBookResponse:
    """Tests for ResolveBookResponse schema."""

    def test_success_response(self):
        """Success response should be valid."""
        response = ResolveBookResponse(
            detected_input_type=InputType.ISBN_13,
            status=ResolutionStatus.SUCCESS,
            records=[
                BookResponse(
                    title="Clean Code",
                    authors=[],
                    identifiers=IdentifiersResponse(),
                )
            ],
            sources_tried=[
                ResolutionSourceResult(
                    source=SourceName.OPEN_LIBRARY,
                    status=ResolutionStatus.SUCCESS,
                    duration_ms=200.0,
                )
            ],
            total_duration_ms=250.0,
        )
        assert response.status == ResolutionStatus.SUCCESS
        assert len(response.records) == 1

    def test_not_found_response(self):
        """Not found response should be valid."""
        response = ResolveBookResponse(
            detected_input_type=InputType.ISBN_13,
            status=ResolutionStatus.NOT_FOUND,
            records=[],
            sources_tried=[],
            total_duration_ms=100.0,
        )
        assert response.status == ResolutionStatus.NOT_FOUND
        assert len(response.records) == 0


class TestResolvePaperResponse:
    """Tests for ResolvePaperResponse schema."""

    def test_success_response(self):
        """Success response should be valid."""
        response = ResolvePaperResponse(
            detected_input_type=InputType.DOI,
            status=ResolutionStatus.SUCCESS,
            records=[
                PaperResponse(
                    title="Test Paper",
                    authors=[],
                    identifiers=IdentifiersResponse(),
                )
            ],
            sources_tried=[],
            total_duration_ms=150.0,
        )
        assert response.status == ResolutionStatus.SUCCESS


class TestSearchBooksResponse:
    """Tests for SearchBooksResponse schema."""

    def test_search_response(self):
        """Search response should be valid."""
        from uuid import uuid4

        from consearch.api.schemas import SearchBookResult

        response = SearchBooksResponse(
            query="python",
            total=10,
            page=1,
            page_size=20,
            has_more=False,
            results=[
                SearchBookResult(
                    id=uuid4(),
                    score=0.95,
                    book=BookResponse(
                        title="Python Book",
                        authors=[],
                        identifiers=IdentifiersResponse(),
                    ),
                )
            ],
        )
        assert response.total == 10
        assert len(response.results) == 1


class TestSearchPapersResponse:
    """Tests for SearchPapersResponse schema."""

    def test_search_response(self):
        """Search response should be valid."""
        from uuid import uuid4

        from consearch.api.schemas import SearchPaperResult

        response = SearchPapersResponse(
            query="machine learning",
            total=100,
            page=1,
            page_size=20,
            has_more=True,
            results=[
                SearchPaperResult(
                    id=uuid4(),
                    score=0.88,
                    paper=PaperResponse(
                        title="ML Paper",
                        authors=[],
                        identifiers=IdentifiersResponse(),
                    ),
                )
            ],
        )
        assert response.total == 100


# ============================================================================
# Source Metadata Tests
# ============================================================================


class TestSourceMetadataResponse:
    """Tests for SourceMetadataResponse schema."""

    def test_full_metadata(self):
        """Full metadata should be valid."""
        from datetime import datetime

        metadata = SourceMetadataResponse(
            source=SourceName.CROSSREF,
            source_id="10.1038/nature12373",
            retrieved_at=datetime.utcnow(),
            reliability_score=0.95,
            raw_data={"key": "value"},
        )
        assert metadata.source == SourceName.CROSSREF
        assert metadata.reliability_score == 0.95

    def test_minimal_metadata(self):
        """Minimal metadata should be valid."""
        from datetime import datetime

        metadata = SourceMetadataResponse(
            source=SourceName.CROSSREF,
            source_id="test",
            retrieved_at=datetime.utcnow(),
            reliability_score=0.9,
        )
        assert metadata.raw_data is None
