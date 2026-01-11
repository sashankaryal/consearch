"""Crossref resolver implementation."""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any, ClassVar

from consearch.core.identifiers import DOI
from consearch.core.models import Author, Identifiers, PaperRecord, SourceMetadata
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolutionResult, ResolverConfig
from consearch.resolution.papers.base import AbstractPaperResolver


class CrossrefResolver(AbstractPaperResolver):
    """
    Crossref API resolver (primary paper source).

    API Documentation: https://api.crossref.org/swagger-ui/index.html
    """

    SOURCE_NAME: ClassVar[SourceName] = SourceName.CROSSREF
    BASE_URL: ClassVar[str] = "https://api.crossref.org"
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=50.0,  # Polite pool limit
        burst_size=5,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset({
        InputType.DOI,
        InputType.TITLE,
        InputType.CITATION,
    })
    _BASE_RELIABILITY: ClassVar[float] = 0.95  # Authoritative source for DOIs

    def __init__(self, config: ResolverConfig | None = None) -> None:
        super().__init__(config)
        # Crossref encourages providing contact email
        self._mailto = config.api_key if config and config.api_key else None

    @property
    def priority(self) -> int:
        return 10  # Primary source (high priority)

    def _get_default_headers(self) -> dict[str, str]:
        headers = super()._get_default_headers()
        if self._mailto:
            headers["User-Agent"] = f"consearch/1.0 (mailto:{self._mailto})"
        return headers

    async def search_by_doi(
        self,
        doi: DOI,
    ) -> ResolutionResult[PaperRecord]:
        """Search Crossref by DOI."""
        start = time.monotonic()

        try:
            response = await self._make_request(
                "GET",
                f"/works/{doi.value}",
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

            record = self._parse_work(data.get("message", {}))

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
        author: str | None = None,
    ) -> ResolutionResult[PaperRecord]:
        """Search Crossref by title."""
        start = time.monotonic()

        params: dict[str, Any] = {
            "query.title": title,
            "rows": 10,
            "select": "DOI,title,author,published,container-title,abstract,reference-count",
        }

        if author:
            params["query.author"] = author

        try:
            response = await self._make_request(
                "GET",
                "/works",
                params=params,
            )

            duration_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()

            data = response.json()
            items = data.get("message", {}).get("items", [])

            records = [self._parse_work(item) for item in items]
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
        """Fetch a paper by DOI."""
        doi = self.parse_doi(identifier)
        if not doi:
            return None
        result = await self.search_by_doi(doi)
        return result.records[0] if result.records else None

    def _parse_work(self, data: dict[str, Any]) -> PaperRecord | None:
        """Parse Crossref work response into PaperRecord."""
        if not data:
            return None

        # Parse DOI
        doi = None
        if doi_val := data.get("DOI"):
            try:
                doi = DOI(value=doi_val)
            except ValueError:
                pass

        # Parse authors
        authors = []
        for author_data in data.get("author", []):
            given = author_data.get("given", "")
            family = author_data.get("family", "")
            name = f"{given} {family}".strip() or "Unknown"

            authors.append(Author(
                name=name,
                given_name=given or None,
                family_name=family or None,
                orcid=author_data.get("ORCID"),
                affiliations=[
                    aff.get("name", "") for aff in author_data.get("affiliation", [])
                ],
            ))

        # Parse title (can be a list)
        title = data.get("title", ["Unknown"])
        if isinstance(title, list):
            title = title[0] if title else "Unknown"

        # Parse publication date
        pub_date = None
        year = None
        if date_parts := data.get("published", {}).get("date-parts", [[]])[0]:
            year_val = date_parts[0] if len(date_parts) > 0 else None
            month = date_parts[1] if len(date_parts) > 1 else 1
            day = date_parts[2] if len(date_parts) > 2 else 1
            if year_val:
                year = year_val
                try:
                    pub_date = date(year_val, month, day)
                except ValueError:
                    pass

        # Parse journal
        journal = data.get("container-title", [])
        if isinstance(journal, list):
            journal = journal[0] if journal else None

        identifiers = Identifiers(
            doi=doi.value if doi else None,
            crossref_id=data.get("DOI"),
        )

        return PaperRecord(
            title=title,
            authors=authors,
            year=year,
            publication_date=pub_date,
            identifiers=identifiers,
            abstract=data.get("abstract"),
            journal=journal,
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages_range=data.get("page"),
            url=doi.url if doi else None,
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=data.get("DOI", ""),
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
                raw_data=data,
            ),
        )
