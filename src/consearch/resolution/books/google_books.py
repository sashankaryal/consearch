"""Google Books resolver implementation."""

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


class GoogleBooksResolver(AbstractBookResolver):
    """
    Google Books API resolver (fallback book source).

    API Documentation: https://developers.google.com/books/docs/v1/using

    Works without API key but rate limits apply.
    With API key, higher quotas are available.
    """

    SOURCE_NAME: ClassVar[SourceName] = SourceName.GOOGLE_BOOKS
    BASE_URL: ClassVar[str] = "https://www.googleapis.com/books/v1"
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=1.0,  # Be polite
        burst_size=2,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset(
        {
            InputType.ISBN_10,
            InputType.ISBN_13,
            InputType.TITLE,
        }
    )
    _BASE_RELIABILITY: ClassVar[float] = 0.85

    def __init__(self, config: ResolverConfig | None = None) -> None:
        super().__init__(config)
        # API key is optional for Google Books
        self._api_key = config.api_key if config else None

    @property
    def priority(self) -> int:
        return 50  # Fallback source (medium priority)

    async def search_by_isbn(
        self,
        isbn: ISBN,
    ) -> ResolutionResult[BookRecord]:
        """Search Google Books by ISBN."""
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

            params: dict[str, Any] = {
                "q": f"isbn:{isbn_to_use}",
                "maxResults": 1,
            }
            if self._api_key:
                params["key"] = self._api_key

            response = await self._make_request(
                "GET",
                "/volumes",
                params=params,
            )

            duration_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if not items:
                return ResolutionResult(
                    status=ResolutionStatus.NOT_FOUND,
                    source=self.source_name,
                    duration_ms=duration_ms,
                )

            record = self._parse_volume(items[0])

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
        """Search Google Books by title and optional author."""
        start = time.monotonic()

        try:
            # Build query with special keywords
            query_parts = [f"intitle:{title}"]
            if author:
                query_parts.append(f"inauthor:{author}")

            params: dict[str, Any] = {
                "q": "+".join(query_parts),
                "maxResults": 10,
                "printType": "books",
            }
            if self._api_key:
                params["key"] = self._api_key

            response = await self._make_request(
                "GET",
                "/volumes",
                params=params,
            )

            duration_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            records = [self._parse_volume(item) for item in items]
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
        """Fetch a book by Google Books volume ID."""
        try:
            params: dict[str, Any] = {}
            if self._api_key:
                params["key"] = self._api_key

            response = await self._make_request(
                "GET",
                f"/volumes/{identifier}",
                params=params,
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            return self._parse_volume(data)

        except Exception:
            return None

    def _parse_volume(self, data: dict[str, Any]) -> BookRecord | None:
        """Parse Google Books volume response into BookRecord."""
        if not data:
            return None

        volume_info = data.get("volumeInfo", {})
        if not volume_info:
            return None

        title = volume_info.get("title", "Unknown")

        # Parse authors
        authors = []
        for author_name in volume_info.get("authors", []):
            if author_name:
                authors.append(Author(name=author_name))

        # Extract publication year
        year = None
        if published_date := volume_info.get("publishedDate"):
            if match := re.search(r"\b(19|20)\d{2}\b", str(published_date)):
                year = int(match.group())

        # Parse identifiers from industryIdentifiers
        isbn10 = None
        isbn13 = None
        for ident in volume_info.get("industryIdentifiers", []):
            ident_type = ident.get("type", "")
            ident_value = ident.get("identifier", "")
            if ident_type == "ISBN_10":
                isbn10 = ident_value
            elif ident_type == "ISBN_13":
                isbn13 = ident_value

        identifiers = Identifiers(
            isbn_10=isbn10,
            isbn_13=isbn13,
            google_books_id=data.get("id"),
        )

        # Get cover image (prefer larger sizes)
        image_links = volume_info.get("imageLinks", {})
        cover_url = (
            image_links.get("large") or image_links.get("medium") or image_links.get("thumbnail")
        )

        # Get categories as subjects
        subjects = volume_info.get("categories", [])

        return BookRecord(
            title=title,
            authors=authors,
            year=year,
            identifiers=identifiers,
            publisher=volume_info.get("publisher"),
            pages=volume_info.get("pageCount"),
            subjects=subjects[:10] if subjects else [],
            cover_image_url=cover_url,
            abstract=volume_info.get("description"),
            language=volume_info.get("language"),
            url=volume_info.get("canonicalVolumeLink"),
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=data.get("id", ""),
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
                raw_data=data,
            ),
        )
