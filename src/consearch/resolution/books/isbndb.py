"""ISBNDb resolver implementation."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, ClassVar

from consearch.core.identifiers import ISBN
from consearch.core.models import Author, BookRecord, Identifiers, SourceMetadata
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolutionResult, ResolverConfig
from consearch.resolution.books.base import AbstractBookResolver


class ISBNDbResolver(AbstractBookResolver):
    """
    ISBNDb API resolver (primary book source).

    API Documentation: https://isbndb.com/isbndb-api-documentation-v2

    Requires API key. Different subscription tiers have different base URLs:
    - Default: api2.isbndb.com (1 req/sec)
    - Premium: api.premium.isbndb.com (3 req/sec)
    - Pro: api.pro.isbndb.com (5 req/sec)
    - Enterprise: api.enterprise.isbndb.com (10 req/sec)
    """

    SOURCE_NAME: ClassVar[SourceName] = SourceName.ISBNDB
    BASE_URL: ClassVar[str] = "https://api2.isbndb.com"
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=1.0,
        burst_size=1,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset({
        InputType.ISBN_10,
        InputType.ISBN_13,
        InputType.TITLE,
    })
    _BASE_RELIABILITY: ClassVar[float] = 0.90

    def __init__(self, config: ResolverConfig | None = None) -> None:
        super().__init__(config)
        if not config or not config.api_key:
            raise ValueError("ISBNDb requires an API key")
        self._api_key = config.api_key

    @property
    def priority(self) -> int:
        return 10  # Primary source (highest priority)

    def _get_default_headers(self) -> dict[str, str]:
        headers = super()._get_default_headers()
        headers["Authorization"] = self._api_key
        return headers

    async def search_by_isbn(
        self,
        isbn: ISBN,
    ) -> ResolutionResult[BookRecord]:
        """Search ISBNDb by ISBN."""
        start = time.monotonic()

        try:
            # Use ISBN-13 if available, otherwise ISBN-10
            isbn10, isbn13 = self.normalize_isbn(isbn)
            isbn_to_use = isbn13 or isbn10

            if not isbn_to_use:
                return ResolutionResult(
                    status=ResolutionStatus.ERROR,
                    source=self.source_name,
                    error_message="Invalid ISBN",
                )

            response = await self._make_request(
                "GET",
                f"/book/{isbn_to_use}",
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

            book_data = data.get("book", {})
            record = self._parse_book(book_data)

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
    ) -> ResolutionResult[BookRecord]:
        """Search ISBNDb by title."""
        start = time.monotonic()

        try:
            # ISBNDb uses the query in the URL path
            query = title
            if author:
                query = f"{title} {author}"

            # URL encode is handled by httpx
            params: dict[str, Any] = {
                "page": 1,
                "pageSize": 10,
            }

            response = await self._make_request(
                "GET",
                f"/books/{query}",
                params=params,
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

            books = data.get("books", [])
            records = [self._parse_book(book) for book in books]
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

    async def fetch_by_id(self, identifier: str) -> BookRecord | None:
        """Fetch a book by ISBN."""
        try:
            isbn = ISBN.parse(identifier)
        except ValueError:
            return None

        result = await self.search_by_isbn(isbn)
        return result.records[0] if result.records else None

    def _parse_book(self, data: dict[str, Any]) -> BookRecord | None:
        """Parse ISBNDb book response into BookRecord."""
        if not data:
            return None

        title = data.get("title", "Unknown")

        # Parse authors (ISBNDb returns list of author strings)
        authors = []
        for author_name in data.get("authors", []):
            if author_name:
                authors.append(Author(name=author_name))

        # Extract publication year from publish_date
        year = None
        if publish_date := data.get("publish_date"):
            if match := re.search(r"\b(19|20)\d{2}\b", str(publish_date)):
                year = int(match.group())

        # Build identifiers
        isbn10 = data.get("isbn")
        isbn13 = data.get("isbn13")

        identifiers = Identifiers(
            isbn_10=isbn10,
            isbn_13=isbn13,
        )

        # Get cover image
        cover_url = data.get("image")

        # Get description/synopsis
        synopsis = data.get("synopsis")

        # Get subjects
        subjects = data.get("subjects", [])
        if isinstance(subjects, str):
            subjects = [s.strip() for s in subjects.split(",")]

        return BookRecord(
            title=title,
            authors=authors,
            year=year,
            identifiers=identifiers,
            publisher=data.get("publisher"),
            pages=data.get("pages"),
            subjects=subjects[:10] if subjects else [],
            cover_image_url=cover_url,
            abstract=synopsis,
            edition=data.get("edition"),
            language=data.get("language"),
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=isbn13 or isbn10 or "",
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
                raw_data=data,
            ),
        )
