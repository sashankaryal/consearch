"""Search query service for Meilisearch."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from consearch.search.client import BOOKS_INDEX, PAPERS_INDEX, AsyncMeilisearchClient

if TYPE_CHECKING:
    from meilisearch_python_sdk.models.search import SearchResults

logger = logging.getLogger(__name__)


@dataclass
class SearchFilters:
    """Filters for search queries."""

    year_min: int | None = None
    year_max: int | None = None
    author: str | None = None
    language: str | None = None
    journal: str | None = None


@dataclass
class SearchHit:
    """A single search result hit."""

    id: UUID
    score: float
    data: dict[str, Any]


@dataclass
class SearchResponse:
    """Response from a search query."""

    hits: list[SearchHit]
    total: int
    query: str
    processing_time_ms: int
    page: int
    page_size: int

    @property
    def has_more(self) -> bool:
        """Whether there are more results available."""
        return self.page * self.page_size < self.total


class Searcher:
    """
    Service for searching works in Meilisearch.

    Provides filtered and paginated search across books and papers indexes.
    """

    def __init__(self, client: AsyncMeilisearchClient) -> None:
        """
        Initialize the searcher.

        Args:
            client: Meilisearch client for search operations
        """
        self._client = client

    async def search_books(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse:
        """
        Search for books.

        Args:
            query: Search query string
            filters: Optional filters (year range, author, language)
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Search response with hits and pagination info
        """
        filter_expr = self._build_filter_expression(filters, index_type="book")
        offset = (page - 1) * page_size

        results = await self._client.search(
            BOOKS_INDEX,
            query,
            filter=filter_expr,
            offset=offset,
            limit=page_size,
            sort=["year:desc"] if not query else None,  # Sort by year if no query
        )

        return self._parse_results(results, query, page, page_size)

    async def search_papers(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse:
        """
        Search for papers.

        Args:
            query: Search query string
            filters: Optional filters (year range, author, journal)
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Search response with hits and pagination info
        """
        filter_expr = self._build_filter_expression(filters, index_type="paper")
        offset = (page - 1) * page_size

        results = await self._client.search(
            PAPERS_INDEX,
            query,
            filter=filter_expr,
            offset=offset,
            limit=page_size,
            sort=["citation_count:desc", "year:desc"] if not query else None,
        )

        return self._parse_results(results, query, page, page_size)

    def _build_filter_expression(
        self,
        filters: SearchFilters | None,
        index_type: str,
    ) -> list[str] | None:
        """Build Meilisearch filter expression from filters."""
        if not filters:
            return None

        expressions = []

        # Year range filters
        if filters.year_min is not None:
            expressions.append(f"year >= {filters.year_min}")
        if filters.year_max is not None:
            expressions.append(f"year <= {filters.year_max}")

        # Language filter (books only)
        if filters.language and index_type == "book":
            expressions.append(f'language = "{filters.language}"')

        # Journal filter (papers only)
        if filters.journal and index_type == "paper":
            # Escape quotes in journal name
            escaped_journal = filters.journal.replace('"', '\\"')
            expressions.append(f'journal = "{escaped_journal}"')

        return expressions if expressions else None

    def _parse_results(
        self,
        results: SearchResults,
        query: str,
        page: int,
        page_size: int,
    ) -> SearchResponse:
        """Parse Meilisearch results into SearchResponse."""
        hits = []
        for hit in results.hits:
            try:
                hit_id = UUID(hit["id"])
                # Meilisearch provides _rankingScore when available
                score = getattr(hit, "_rankingScore", None) or 1.0
                hits.append(
                    SearchHit(
                        id=hit_id,
                        score=score,
                        data=dict(hit),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Invalid hit in search results: {e}")
                continue

        return SearchResponse(
            hits=hits,
            total=results.estimated_total_hits or len(hits),
            query=query,
            processing_time_ms=results.processing_time_ms,
            page=page,
            page_size=page_size,
        )
