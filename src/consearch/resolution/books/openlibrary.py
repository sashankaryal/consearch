"""OpenLibrary resolver implementation."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, ClassVar

from consearch.core.identifiers import ISBN
from consearch.core.models import Author, BookRecord, Identifiers, SourceMetadata
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import RateLimitConfig, ResolutionResult, ResolverConfig
from consearch.resolution.books.base import AbstractBookResolver


class OpenLibraryResolver(AbstractBookResolver):
    """
    OpenLibrary API resolver (free, no API key required).

    API Documentation: https://openlibrary.org/dev/docs/api/books
    """

    SOURCE_NAME: ClassVar[SourceName] = SourceName.OPEN_LIBRARY
    BASE_URL: ClassVar[str] = "https://openlibrary.org"
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=1.0,  # Be polite
        burst_size=1,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset({
        InputType.ISBN_10,
        InputType.ISBN_13,
        InputType.TITLE,
    })
    _BASE_RELIABILITY: ClassVar[float] = 0.75  # Community-contributed data

    def __init__(self, config: ResolverConfig | None = None) -> None:
        super().__init__(config)

    @property
    def priority(self) -> int:
        return 100  # Fallback source (lower priority)

    async def search_by_isbn(
        self,
        isbn: ISBN,
    ) -> ResolutionResult[BookRecord]:
        """Search OpenLibrary by ISBN."""
        start = time.monotonic()

        try:
            # Try ISBN-13 first, then ISBN-10
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
                f"/isbn/{isbn_to_use}.json",
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

            # Fetch work data if available for more complete info
            work_key = None
            if works := data.get("works"):
                work_key = works[0].get("key")
                work_data = await self._fetch_work(work_key)
                if work_data:
                    data = self._merge_work_data(data, work_data)

            record = self._parse_book(data, isbn10, isbn13)

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
        """Search OpenLibrary by title."""
        start = time.monotonic()

        try:
            params: dict[str, Any] = {
                "title": title,
                "limit": 10,
            }
            if author:
                params["author"] = author

            response = await self._make_request(
                "GET",
                "/search.json",
                params=params,
            )

            duration_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()

            data = response.json()
            docs = data.get("docs", [])

            records = []
            for doc in docs[:10]:  # Limit results
                record = self._parse_search_result(doc)
                if record:
                    records.append(record)

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
        """Fetch a book by OpenLibrary ID."""
        try:
            response = await self._make_request(
                "GET",
                f"{identifier}.json",
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return self._parse_book(data, None, None)
        except Exception:
            return None

    async def _fetch_work(self, work_key: str) -> dict[str, Any] | None:
        """Fetch work data for more complete info."""
        try:
            response = await self._make_request(
                "GET",
                f"{work_key}.json",
            )
            if response.is_success:
                return response.json()
        except Exception:
            pass
        return None

    def _merge_work_data(
        self,
        edition_data: dict[str, Any],
        work_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge work data into edition data for completeness."""
        # Use work description if edition doesn't have one
        if not edition_data.get("description") and work_data.get("description"):
            edition_data["description"] = work_data["description"]

        # Use work subjects if edition doesn't have any
        if not edition_data.get("subjects") and work_data.get("subjects"):
            edition_data["subjects"] = work_data["subjects"]

        return edition_data

    def _parse_book(
        self,
        data: dict[str, Any],
        isbn10: str | None,
        isbn13: str | None,
    ) -> BookRecord | None:
        """Parse OpenLibrary edition response into BookRecord."""
        if not data:
            return None

        title = data.get("title", "Unknown")

        # Parse authors
        authors = []
        for author_ref in data.get("authors", []):
            author_key = author_ref.get("key")
            if author_key:
                # We could fetch author details, but keep it simple for now
                authors.append(Author(name=author_key.replace("/authors/", "")))

        # Extract publication year
        year = None
        if publish_date := data.get("publish_date"):
            # Try to extract 4-digit year
            import re
            if match := re.search(r"\b(19|20)\d{2}\b", publish_date):
                year = int(match.group())

        # Build identifiers
        identifiers = Identifiers(
            isbn_10=isbn10 or (data.get("isbn_10", [None])[0] if data.get("isbn_10") else None),
            isbn_13=isbn13 or (data.get("isbn_13", [None])[0] if data.get("isbn_13") else None),
            openlibrary_id=data.get("key", "").replace("/books/", ""),
        )

        # Get cover URL
        cover_id = data.get("covers", [None])[0] if data.get("covers") else None
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

        # Get description
        description = data.get("description")
        if isinstance(description, dict):
            description = description.get("value")

        return BookRecord(
            title=title,
            authors=authors,
            year=year,
            identifiers=identifiers,
            publisher=(data.get("publishers", [None])[0] if data.get("publishers") else None),
            pages=data.get("number_of_pages"),
            subjects=data.get("subjects", [])[:10],  # Limit subjects
            cover_image_url=cover_url,
            abstract=description,
            language=(data.get("languages", [{}])[0].get("key", "").replace("/languages/", "")
                      if data.get("languages") else None),
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=data.get("key", ""),
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
                raw_data=data,
            ),
        )

    def _parse_search_result(self, doc: dict[str, Any]) -> BookRecord | None:
        """Parse OpenLibrary search result into BookRecord."""
        if not doc:
            return None

        title = doc.get("title", "Unknown")

        # Parse authors
        authors = []
        for author_name in doc.get("author_name", []):
            authors.append(Author(name=author_name))

        # Get ISBN
        isbn_list = doc.get("isbn", [])
        isbn10 = None
        isbn13 = None
        for isbn in isbn_list:
            if len(isbn) == 10:
                isbn10 = isbn10 or isbn
            elif len(isbn) == 13:
                isbn13 = isbn13 or isbn

        identifiers = Identifiers(
            isbn_10=isbn10,
            isbn_13=isbn13,
            openlibrary_id=doc.get("key", "").replace("/works/", ""),
        )

        return BookRecord(
            title=title,
            authors=authors,
            year=doc.get("first_publish_year"),
            identifiers=identifiers,
            publisher=(doc.get("publisher", [None])[0] if doc.get("publisher") else None),
            subjects=doc.get("subject", [])[:10],
            source_metadata=SourceMetadata(
                source=self.source_name,
                source_id=doc.get("key", ""),
                retrieved_at=datetime.utcnow(),
                reliability_score=self.reliability_score,
            ),
        )
