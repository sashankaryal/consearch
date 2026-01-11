"""Search service for querying indexed works."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from consearch.api.schemas import (
    AuthorResponse,
    BookResponse,
    IdentifiersResponse,
    PaperResponse,
    SearchBookResult,
    SearchBooksResponse,
    SearchPaperResult,
    SearchPapersResponse,
)
from consearch.search.searcher import SearchFilters, Searcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from consearch.db.models.work import WorkModel
    from consearch.search.client import AsyncMeilisearchClient

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for searching works with database hydration.

    Wraps Meilisearch searches and hydrates results with full data from DB.
    """

    def __init__(
        self,
        session: "AsyncSession",
        search_client: "AsyncMeilisearchClient",
    ) -> None:
        """
        Initialize the search service.

        Args:
            session: Database session for hydration
            search_client: Meilisearch client for searches
        """
        self._session = session
        self._searcher = Searcher(search_client)

    async def search_books(
        self,
        query: str,
        *,
        year_min: int | None = None,
        year_max: int | None = None,
        author: str | None = None,
        language: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchBooksResponse:
        """
        Search for books with optional filters.

        Args:
            query: Search query string
            year_min: Minimum publication year
            year_max: Maximum publication year
            author: Filter by author name
            language: Filter by language code
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Paginated search results with book data
        """
        filters = SearchFilters(
            year_min=year_min,
            year_max=year_max,
            author=author,
            language=language,
        )

        search_result = await self._searcher.search_books(
            query,
            filters=filters,
            page=page,
            page_size=page_size,
        )

        # Convert search hits to response objects
        results = []
        for hit in search_result.hits:
            book_response = self._hit_to_book_response(hit.data)
            if book_response:
                results.append(SearchBookResult(
                    id=hit.id,
                    score=hit.score,
                    book=book_response,
                ))

        return SearchBooksResponse(
            total=search_result.total,
            page=page,
            page_size=page_size,
            has_more=search_result.has_more,
            results=results,
        )

    async def search_papers(
        self,
        query: str,
        *,
        year_min: int | None = None,
        year_max: int | None = None,
        author: str | None = None,
        journal: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchPapersResponse:
        """
        Search for papers with optional filters.

        Args:
            query: Search query string
            year_min: Minimum publication year
            year_max: Maximum publication year
            author: Filter by author name
            journal: Filter by journal name
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Paginated search results with paper data
        """
        filters = SearchFilters(
            year_min=year_min,
            year_max=year_max,
            author=author,
            journal=journal,
        )

        search_result = await self._searcher.search_papers(
            query,
            filters=filters,
            page=page,
            page_size=page_size,
        )

        # Convert search hits to response objects
        results = []
        for hit in search_result.hits:
            paper_response = self._hit_to_paper_response(hit.data)
            if paper_response:
                results.append(SearchPaperResult(
                    id=hit.id,
                    score=hit.score,
                    paper=paper_response,
                ))

        return SearchPapersResponse(
            total=search_result.total,
            page=page,
            page_size=page_size,
            has_more=search_result.has_more,
            results=results,
        )

    def _hit_to_book_response(self, data: dict) -> BookResponse | None:
        """Convert a search hit to BookResponse."""
        try:
            authors = [
                AuthorResponse(name=name)
                for name in data.get("authors", [])
            ]

            idents = data.get("identifiers", {})
            identifiers = IdentifiersResponse(
                isbn_10=idents.get("isbn_10"),
                isbn_13=idents.get("isbn_13"),
            )

            return BookResponse(
                title=data.get("title", "Unknown"),
                authors=authors,
                year=data.get("year"),
                identifiers=identifiers,
                publisher=data.get("publisher"),
                subjects=data.get("subjects", []),
                language=data.get("language"),
            )
        except Exception as e:
            logger.warning(f"Failed to convert book hit: {e}")
            return None

    def _hit_to_paper_response(self, data: dict) -> PaperResponse | None:
        """Convert a search hit to PaperResponse."""
        try:
            authors = [
                AuthorResponse(name=name)
                for name in data.get("authors", [])
            ]

            idents = data.get("identifiers", {})
            identifiers = IdentifiersResponse(
                doi=idents.get("doi"),
                arxiv_id=idents.get("arxiv_id"),
            )

            return PaperResponse(
                title=data.get("title", "Unknown"),
                authors=authors,
                year=data.get("year"),
                identifiers=identifiers,
                abstract=data.get("abstract"),
                journal=data.get("journal"),
                citation_count=data.get("citation_count"),
            )
        except Exception as e:
            logger.warning(f"Failed to convert paper hit: {e}")
            return None
