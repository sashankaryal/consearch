"""Tests for Semantic Scholar resolver."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from consearch.core.identifiers import DOI, ArXivID
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolverConfig
from consearch.resolution.papers.semantic_scholar import SemanticScholarResolver


@pytest.fixture
def resolver() -> SemanticScholarResolver:
    """Create a Semantic Scholar resolver."""
    return SemanticScholarResolver()


@pytest.fixture
def resolver_with_key() -> SemanticScholarResolver:
    """Create a Semantic Scholar resolver with API key."""
    config = ResolverConfig(api_key="test-api-key")
    return SemanticScholarResolver(config)


@pytest.fixture
def resolver_no_retry() -> SemanticScholarResolver:
    """Create a Semantic Scholar resolver with no 429 retries (for testing rate limits)."""
    config = ResolverConfig(rate_limit=RateLimitConfig(retry_on_429=False))
    return SemanticScholarResolver(config)


@pytest.fixture
def paper_response_data() -> dict:
    """Sample Semantic Scholar API response for paper lookup."""
    return {
        "paperId": "abc123def456",
        "title": "DNA sequencing with nanopores",
        "authors": [
            {
                "authorId": "12345",
                "name": "Elizabeth Pennisi",
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
            "ArXiv": "1308.4567",
            "PubMed": "23965470",
        },
        "openAccessPdf": {
            "url": "https://example.com/paper.pdf",
            "status": "GREEN",
        },
    }


@pytest.fixture
def search_response_data() -> dict:
    """Sample Semantic Scholar search response."""
    return {
        "total": 1,
        "data": [
            {
                "paperId": "abc123",
                "title": "DNA sequencing with nanopores",
                "authors": [{"name": "Elizabeth Pennisi"}],
                "year": 2013,
                "citationCount": 1500,
            }
        ],
    }


# ============================================================================
# Resolver Configuration Tests
# ============================================================================


class TestSemanticScholarResolverConfig:
    """Tests for Semantic Scholar resolver configuration."""

    def test_source_name(self, resolver: SemanticScholarResolver):
        """Source name should be SEMANTIC_SCHOLAR."""
        assert resolver.source_name == SourceName.SEMANTIC_SCHOLAR

    def test_base_url(self, resolver: SemanticScholarResolver):
        """Base URL should be api.semanticscholar.org."""
        assert resolver.BASE_URL == "https://api.semanticscholar.org/graph/v1"

    def test_priority(self, resolver: SemanticScholarResolver):
        """Priority should be 50 (fallback)."""
        assert resolver.priority == 50

    def test_supported_input_types(self, resolver: SemanticScholarResolver):
        """Should support DOI, arXiv, PMID, and title search."""
        assert InputType.DOI in resolver.supported_input_types
        assert InputType.ARXIV in resolver.supported_input_types
        assert InputType.PMID in resolver.supported_input_types
        assert InputType.TITLE in resolver.supported_input_types

    def test_enabled_without_key(self, resolver: SemanticScholarResolver):
        """Resolver should be enabled without API key."""
        assert resolver.is_enabled is True


# ============================================================================
# DOI Lookup Tests
# ============================================================================


class TestSemanticScholarDOILookup:
    """Tests for DOI lookup functionality."""

    @respx.mock
    async def test_doi_lookup_success(
        self,
        resolver: SemanticScholarResolver,
        paper_response_data: dict,
    ):
        """Successful DOI lookup should return paper record."""
        # Note: Semantic Scholar uses DOI: prefix
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373").mock(
            return_value=Response(200, json=paper_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1
        assert result.source == SourceName.SEMANTIC_SCHOLAR

        record = result.records[0]
        assert record.title == "DNA sequencing with nanopores"
        assert record.identifiers.doi == "10.1038/nature12373"
        assert record.identifiers.semantic_scholar_id == "abc123def456"
        assert record.citation_count == 1500

    @respx.mock
    async def test_doi_not_found(self, resolver: SemanticScholarResolver):
        """DOI not found should return NOT_FOUND status."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.0000/notfound").mock(
            return_value=Response(404)
        )

        doi = DOI(value="10.0000/notfound")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.NOT_FOUND

    @respx.mock
    async def test_api_key_header_included(
        self,
        resolver_with_key: SemanticScholarResolver,
    ):
        """Request should include x-api-key header when provided."""
        route = respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/test").mock(
            return_value=Response(200, json={"paperId": "test", "title": "Test"})
        )

        doi = DOI(value="10.1038/test")
        await resolver_with_key.search_by_doi(doi)

        # Check x-api-key header
        request = route.calls[0].request
        assert "x-api-key" in request.headers
        assert request.headers["x-api-key"] == "test-api-key"


# ============================================================================
# ArXiv Lookup Tests
# ============================================================================


class TestSemanticScholarArXivLookup:
    """Tests for arXiv ID lookup functionality."""

    @respx.mock
    async def test_arxiv_lookup_success(
        self,
        resolver: SemanticScholarResolver,
        paper_response_data: dict,
    ):
        """Successful arXiv lookup should return paper record."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/arXiv:1234.56789").mock(
            return_value=Response(200, json=paper_response_data)
        )

        arxiv = ArXivID.parse("1234.56789")
        result = await resolver.search_by_arxiv(arxiv)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1

    @respx.mock
    async def test_arxiv_old_format(
        self,
        resolver: SemanticScholarResolver,
        paper_response_data: dict,
    ):
        """Old arXiv format should work."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/arXiv:hep-th/9901001").mock(
            return_value=Response(200, json=paper_response_data)
        )

        arxiv = ArXivID.parse("hep-th/9901001")
        result = await resolver.search_by_arxiv(arxiv)

        assert result.status == ResolutionStatus.SUCCESS


# ============================================================================
# Title Search Tests
# ============================================================================


class TestSemanticScholarTitleSearch:
    """Tests for title search functionality."""

    @respx.mock
    async def test_title_search_success(
        self,
        resolver: SemanticScholarResolver,
        search_response_data: dict,
    ):
        """Successful title search should return paper records."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.search_by_title("DNA sequencing")

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) >= 1

    @respx.mock
    async def test_title_search_no_results(self, resolver: SemanticScholarResolver):
        """Title search with no results should return NOT_FOUND."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(200, json={"total": 0, "data": []})
        )

        result = await resolver.search_by_title("Nonexistent Paper XYZ")

        assert result.status == ResolutionStatus.NOT_FOUND


# ============================================================================
# Record Parsing Tests
# ============================================================================


class TestSemanticScholarRecordParsing:
    """Tests for parsing Semantic Scholar response data."""

    @respx.mock
    async def test_parses_all_fields(
        self,
        resolver: SemanticScholarResolver,
        paper_response_data: dict,
    ):
        """All available fields should be parsed correctly."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373").mock(
            return_value=Response(200, json=paper_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        record = result.records[0]
        assert record.title == "DNA sequencing with nanopores"
        assert record.year == 2013
        assert record.journal == "Nature"
        assert record.citation_count == 1500
        assert record.reference_count == 30
        assert record.abstract == "Abstract text here."
        assert record.identifiers.doi == "10.1038/nature12373"
        assert record.identifiers.arxiv_id == "1308.4567"
        assert record.identifiers.pmid == "23965470"
        assert record.identifiers.semantic_scholar_id == "abc123def456"
        assert record.pdf_url == "https://example.com/paper.pdf"

        # Check author parsing
        assert len(record.authors) == 1
        assert record.authors[0].name == "Elizabeth Pennisi"

    @respx.mock
    async def test_handles_missing_fields(self, resolver: SemanticScholarResolver):
        """Missing fields should be handled gracefully."""
        minimal_data = {
            "paperId": "test123",
            "title": "Minimal Paper",
        }
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/test").mock(
            return_value=Response(200, json=minimal_data)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.SUCCESS
        record = result.records[0]
        assert record.title == "Minimal Paper"
        assert record.year is None
        assert record.journal is None
        assert record.pdf_url is None

    @respx.mock
    async def test_source_metadata_included(
        self,
        resolver: SemanticScholarResolver,
        paper_response_data: dict,
    ):
        """Source metadata should be included in record."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373").mock(
            return_value=Response(200, json=paper_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        record = result.records[0]
        assert record.source_metadata is not None
        assert record.source_metadata.source == SourceName.SEMANTIC_SCHOLAR


# ============================================================================
# Fields Parameter Tests
# ============================================================================


class TestSemanticScholarFieldsParameter:
    """Tests for fields parameter in API requests."""

    @respx.mock
    async def test_fields_parameter_included(self, resolver: SemanticScholarResolver):
        """Request should include fields parameter."""
        route = respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/test").mock(
            return_value=Response(200, json={"paperId": "test", "title": "Test"})
        )

        doi = DOI(value="10.1038/test")
        await resolver.search_by_doi(doi)

        # Check fields parameter
        url = str(route.calls[0].request.url)
        assert "fields=" in url


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestSemanticScholarErrorHandling:
    """Tests for error handling."""

    @respx.mock
    async def test_server_error(self, resolver: SemanticScholarResolver):
        """Server error should return ERROR status."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/test").mock(
            return_value=Response(500)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.ERROR
        assert result.error_message is not None

    @respx.mock
    async def test_rate_limit_error(self, resolver_no_retry: SemanticScholarResolver):
        """Rate limit error should be handled."""
        respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/test").mock(
            return_value=Response(429)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver_no_retry.search_by_doi(doi)

        assert result.status in (ResolutionStatus.RATE_LIMITED, ResolutionStatus.ERROR)
