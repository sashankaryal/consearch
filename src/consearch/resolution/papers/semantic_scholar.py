"""Semantic Scholar resolver implementation."""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any, ClassVar

from consearch.core.identifiers import DOI, ArXivID
from consearch.core.models import Author, Identifiers, PaperRecord, SourceMetadata
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolutionResult, ResolverConfig
from consearch.resolution.papers.base import AbstractPaperResolver


class SemanticScholarResolver(AbstractPaperResolver):
    """
    Semantic Scholar API resolver (fallback paper source).

    API Documentation: https://api.semanticscholar.org/api-docs/

    Works without API key but rate limited to shared pool.
    With API key, 1 request/second guaranteed.
    """

    SOURCE_NAME: ClassVar[SourceName] = SourceName.SEMANTIC_SCHOLAR
    BASE_URL: ClassVar[str] = "https://api.semanticscholar.org/graph/v1"
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=1.0,  # Conservative for shared pool
        burst_size=1,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset(
        {
            InputType.DOI,
            InputType.ARXIV,
            InputType.PMID,
            InputType.TITLE,
        }
    )
    _BASE_RELIABILITY: ClassVar[float] = 0.85

    # Fields to request from API
    PAPER_FIELDS: ClassVar[str] = (
        "paperId,title,authors,year,abstract,venue,"
        "publicationDate,citationCount,referenceCount,"
        "externalIds,openAccessPdf,url"
    )

    def __init__(self, config: ResolverConfig | None = None) -> None:
        super().__init__(config)
        # API key is optional
        self._api_key = config.api_key if config else None

    @property
    def priority(self) -> int:
        return 50  # Fallback source (medium priority)

    def _get_default_headers(self) -> dict[str, str]:
        headers = super()._get_default_headers()
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def search_by_doi(
        self,
        doi: DOI,
    ) -> ResolutionResult[PaperRecord]:
        """Search Semantic Scholar by DOI."""
        start = time.monotonic()

        try:
            # Semantic Scholar expects DOI: prefix
            paper_id = f"DOI:{doi.value}"

            response = await self._make_request(
                "GET",
                f"/paper/{paper_id}",
                params={"fields": self.PAPER_FIELDS},
            )

            duration_ms = (time.monotonic() - start) * 1000

            if response.status_code == 404:
                return ResolutionResult(
                    status=ResolutionStatus.NOT_FOUND,
                    source=self.source_name,
                    duration_ms=duration_ms,
                )

            response.raise_for_status()
            data = response.json()

            record = self._parse_paper(data)

            return ResolutionResult(
                status=ResolutionStatus.SUCCESS if record else ResolutionStatus.NOT_FOUND,
                records=[record] if record else [],
                source=self.source_name,
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._record_failure()
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=self.source_name,
                error_message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    async def search_by_arxiv(
        self,
        arxiv_id: ArXivID,
    ) -> ResolutionResult[PaperRecord]:
        """Search Semantic Scholar by arXiv ID."""
        start = time.monotonic()

        try:
            # Semantic Scholar expects arXiv: prefix
            paper_id = f"arXiv:{arxiv_id.value}"

            response = await self._make_request(
                "GET",
                f"/paper/{paper_id}",
                params={"fields": self.PAPER_FIELDS},
            )

            duration_ms = (time.monotonic() - start) * 1000

            if response.status_code == 404:
                return ResolutionResult(
                    status=ResolutionStatus.NOT_FOUND,
                    source=self.source_name,
                    duration_ms=duration_ms,
                )

            response.raise_for_status()
            data = response.json()

            record = self._parse_paper(data)

            return ResolutionResult(
                status=ResolutionStatus.SUCCESS if record else ResolutionStatus.NOT_FOUND,
                records=[record] if record else [],
                source=self.source_name,
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._record_failure()
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=self.source_name,
                error_message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    async def search_by_title(
        self,
        title: str,
        _author: str | None = None,
    ) -> ResolutionResult[PaperRecord]:
        """Search Semantic Scholar by title."""
        start = time.monotonic()

        try:
            query = title
            # Note: Semantic Scholar doesn't support author filtering in search API

            params: dict[str, Any] = {
                "query": query,
                "fields": self.PAPER_FIELDS,
                "limit": 10,
            }

            response = await self._make_request(
                "GET",
                "/paper/search",
                params=params,
            )

            duration_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()
            data = response.json()

            papers = data.get("data", [])
            records = [self._parse_paper(paper) for paper in papers]
            records = [r for r in records if r is not None]

            return ResolutionResult(
                status=ResolutionStatus.SUCCESS if records else ResolutionStatus.NOT_FOUND,
                records=records,
                source=self.source_name,
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._record_failure()
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=self.source_name,
                error_message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    async def fetch_by_id(self, identifier: str) -> PaperRecord | None:
        """Fetch a paper by Semantic Scholar paper ID."""
        try:
            response = await self._make_request(
                "GET",
                f"/paper/{identifier}",
                params={"fields": self.PAPER_FIELDS},
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            return self._parse_paper(data)

        except Exception:
            return None

    def _parse_paper(self, data: dict[str, Any]) -> PaperRecord | None:
        """Parse Semantic Scholar paper response into PaperRecord."""
        if not data:
            return None

        title = data.get("title", "Unknown")

        # Parse authors
        authors = []
        for author_data in data.get("authors", []):
            name = author_data.get("name", "Unknown")
            authors.append(
                Author(
                    name=name,
                    # Semantic Scholar doesn't split given/family names
                )
            )

        year = data.get("year")

        # Parse publication date
        pub_date = None
        if pub_date_str := data.get("publicationDate"):
            try:
                pub_date = date.fromisoformat(pub_date_str)
            except ValueError:
                pass

        # Extract external IDs
        external_ids = data.get("externalIds", {})
        doi_value = external_ids.get("DOI")
        arxiv_value = external_ids.get("ArXiv")
        pmid_value = external_ids.get("PubMed")

        identifiers = Identifiers(
            doi=doi_value,
            arxiv_id=arxiv_value,
            pmid=pmid_value,
            semantic_scholar_id=data.get("paperId"),
        )

        # Get PDF URL if available
        pdf_url = None
        if open_access := data.get("openAccessPdf"):
            pdf_url = open_access.get("url")

        return PaperRecord(
            title=title,
            authors=authors,
            year=year,
            publication_date=pub_date,
            identifiers=identifiers,
            abstract=data.get("abstract"),
            journal=data.get("venue"),  # Semantic Scholar uses "venue"
            citation_count=data.get("citationCount"),
            reference_count=data.get("referenceCount"),
            url=data.get("url"),
            pdf_url=pdf_url,
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=data.get("paperId", ""),
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
                raw_data=data,
            ),
        )
