"""Tests for Crossref resolver."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from consearch.core.identifiers import DOI
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolverConfig
from consearch.resolution.papers.crossref import CrossrefResolver


@pytest.fixture
def resolver() -> CrossrefResolver:
    """Create a Crossref resolver."""
    return CrossrefResolver()


@pytest.fixture
def resolver_with_email() -> CrossrefResolver:
    """Create a Crossref resolver with mailto for polite pool."""
    config = ResolverConfig(api_key="test@example.com")
    return CrossrefResolver(config)


@pytest.fixture
def resolver_no_retry() -> CrossrefResolver:
    """Create a Crossref resolver with no 429 retries (for testing rate limits)."""
    config = ResolverConfig(rate_limit=RateLimitConfig(retry_on_429=False))
    return CrossrefResolver(config)


@pytest.fixture
def doi_response_data() -> dict:
    """Sample Crossref API response for DOI lookup."""
    return {
        "status": "ok",
        "message-type": "work",
        "message": {
            "DOI": "10.1038/nature12373",
            "title": ["DNA sequencing with nanopores"],
            "author": [
                {
                    "given": "Elizabeth",
                    "family": "Pennisi",
                    "affiliation": [{"name": "Science Magazine"}],
                    "ORCID": "https://orcid.org/0000-0002-1234-5678",
                },
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
def search_response_data() -> dict:
    """Sample Crossref search response."""
    return {
        "status": "ok",
        "message-type": "work-list",
        "message": {
            "total-results": 1,
            "items": [
                {
                    "DOI": "10.1038/nature12373",
                    "title": ["DNA sequencing with nanopores"],
                    "author": [{"family": "Pennisi", "given": "Elizabeth"}],
                    "container-title": ["Nature"],
                }
            ],
        },
    }


# ============================================================================
# Resolver Configuration Tests
# ============================================================================


class TestCrossrefResolverConfig:
    """Tests for Crossref resolver configuration."""

    def test_source_name(self, resolver: CrossrefResolver):
        """Source name should be CROSSREF."""
        assert resolver.source_name == SourceName.CROSSREF

    def test_base_url(self, resolver: CrossrefResolver):
        """Base URL should be api.crossref.org."""
        assert resolver.BASE_URL == "https://api.crossref.org"

    def test_priority(self, resolver: CrossrefResolver):
        """Priority should be 10 (primary)."""
        assert resolver.priority == 10

    def test_supported_input_types(self, resolver: CrossrefResolver):
        """Should support DOI and title search."""
        assert InputType.DOI in resolver.supported_input_types
        assert InputType.TITLE in resolver.supported_input_types
        assert InputType.ISBN_10 not in resolver.supported_input_types

    def test_enabled_without_key(self, resolver: CrossrefResolver):
        """Resolver should be enabled without API key."""
        assert resolver.is_enabled is True


# ============================================================================
# DOI Lookup Tests
# ============================================================================


class TestCrossrefDOILookup:
    """Tests for DOI lookup functionality."""

    @respx.mock
    async def test_doi_lookup_success(
        self,
        resolver: CrossrefResolver,
        doi_response_data: dict,
    ):
        """Successful DOI lookup should return paper record."""
        respx.get("https://api.crossref.org/works/10.1038/nature12373").mock(
            return_value=Response(200, json=doi_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) == 1
        assert result.source == SourceName.CROSSREF

        record = result.records[0]
        assert record.title == "DNA sequencing with nanopores"
        assert record.identifiers.doi == "10.1038/nature12373"
        assert record.journal == "Nature"
        assert record.citation_count == 1500

    @respx.mock
    async def test_doi_not_found(self, resolver: CrossrefResolver):
        """DOI not found should return NOT_FOUND status."""
        respx.get("https://api.crossref.org/works/10.0000/notfound").mock(
            return_value=Response(404)
        )

        doi = DOI(value="10.0000/notfound")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.NOT_FOUND
        assert len(result.records) == 0

    @respx.mock
    async def test_mailto_header_included(
        self,
        resolver_with_email: CrossrefResolver,
    ):
        """Request should include mailto for polite pool."""
        route = respx.get("https://api.crossref.org/works/10.1038/nature12373").mock(
            return_value=Response(200, json={"status": "ok", "message": {"title": ["Test"]}})
        )

        doi = DOI(value="10.1038/nature12373")
        await resolver_with_email.search_by_doi(doi)

        # Check User-Agent or mailto parameter
        request = route.calls[0].request
        assert "mailto" in str(request.url) or "test@example.com" in request.headers.get("User-Agent", "")


# ============================================================================
# Title Search Tests
# ============================================================================


class TestCrossrefTitleSearch:
    """Tests for title search functionality."""

    @respx.mock
    async def test_title_search_success(
        self,
        resolver: CrossrefResolver,
        search_response_data: dict,
    ):
        """Successful title search should return paper records."""
        respx.get("https://api.crossref.org/works").mock(
            return_value=Response(200, json=search_response_data)
        )

        result = await resolver.search_by_title("DNA sequencing")

        assert result.status == ResolutionStatus.SUCCESS
        assert len(result.records) >= 1

    @respx.mock
    async def test_title_search_no_results(self, resolver: CrossrefResolver):
        """Title search with no results should return NOT_FOUND."""
        respx.get("https://api.crossref.org/works").mock(
            return_value=Response(200, json={
                "status": "ok",
                "message": {"total-results": 0, "items": []},
            })
        )

        result = await resolver.search_by_title("Nonexistent Paper XYZ")

        assert result.status == ResolutionStatus.NOT_FOUND


# ============================================================================
# Record Parsing Tests
# ============================================================================


class TestCrossrefRecordParsing:
    """Tests for parsing Crossref response data."""

    @respx.mock
    async def test_parses_all_fields(
        self,
        resolver: CrossrefResolver,
        doi_response_data: dict,
    ):
        """All available fields should be parsed correctly."""
        respx.get("https://api.crossref.org/works/10.1038/nature12373").mock(
            return_value=Response(200, json=doi_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        record = result.records[0]
        assert record.title == "DNA sequencing with nanopores"
        assert record.year == 2013
        assert record.journal == "Nature"
        assert record.volume == "500"
        assert record.issue == "7463"
        assert record.pages_range == "476-480"
        assert record.citation_count == 1500
        assert record.reference_count == 30
        assert "Abstract text here" in record.abstract

        # Check author parsing
        assert len(record.authors) == 1
        assert record.authors[0].name == "Elizabeth Pennisi"
        assert record.authors[0].given_name == "Elizabeth"
        assert record.authors[0].family_name == "Pennisi"

    @respx.mock
    async def test_handles_missing_fields(self, resolver: CrossrefResolver):
        """Missing fields should be handled gracefully."""
        minimal_data = {
            "status": "ok",
            "message": {
                "DOI": "10.1038/test",
                "title": ["Minimal Paper"],
            },
        }
        respx.get("https://api.crossref.org/works/10.1038/test").mock(
            return_value=Response(200, json=minimal_data)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.SUCCESS
        record = result.records[0]
        assert record.title == "Minimal Paper"
        assert record.year is None
        assert record.journal is None

    @respx.mock
    async def test_strips_jats_tags_from_abstract(
        self,
        resolver: CrossrefResolver,
    ):
        """JATS XML tags should be stripped from abstract."""
        data = {
            "status": "ok",
            "message": {
                "DOI": "10.1038/test",
                "title": ["Test"],
                "abstract": "<jats:p>Clean abstract text.</jats:p>",
            },
        }
        respx.get("https://api.crossref.org/works/10.1038/test").mock(
            return_value=Response(200, json=data)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver.search_by_doi(doi)

        record = result.records[0]
        assert "<jats" not in record.abstract
        assert "Clean abstract text" in record.abstract

    @respx.mock
    async def test_source_metadata_included(
        self,
        resolver: CrossrefResolver,
        doi_response_data: dict,
    ):
        """Source metadata should be included in record."""
        respx.get("https://api.crossref.org/works/10.1038/nature12373").mock(
            return_value=Response(200, json=doi_response_data)
        )

        doi = DOI(value="10.1038/nature12373")
        result = await resolver.search_by_doi(doi)

        record = result.records[0]
        assert record.source_metadata is not None
        assert record.source_metadata.source == SourceName.CROSSREF


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestCrossrefErrorHandling:
    """Tests for error handling."""

    @respx.mock
    async def test_server_error(self, resolver: CrossrefResolver):
        """Server error should return ERROR status."""
        respx.get("https://api.crossref.org/works/10.1038/test").mock(
            return_value=Response(500)
        )

        doi = DOI(value="10.1038/test")
        result = await resolver.search_by_doi(doi)

        assert result.status == ResolutionStatus.ERROR
        assert result.error_message is not None

    @respx.mock
    async def test_rate_limit_error(self, resolver_no_retry: CrossrefResolver):
        """Rate limit error should be handled."""
        respx.get("https://api.crossref.org/works/10.1038/test").mock(
            return_value=Response(429, headers={"Retry-After": "60"})
        )

        doi = DOI(value="10.1038/test")
        result = await resolver_no_retry.search_by_doi(doi)

        assert result.status in (ResolutionStatus.RATE_LIMITED, ResolutionStatus.ERROR)
