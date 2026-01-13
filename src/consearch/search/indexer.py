"""Search indexing service for Meilisearch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from consearch.core.types import ConsumableType
from consearch.search.client import BOOKS_INDEX, PAPERS_INDEX, AsyncMeilisearchClient

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from consearch.db.models.work import WorkModel

logger = logging.getLogger(__name__)


class SearchIndexer:
    """
    Service for indexing works into Meilisearch.

    Converts database models to search documents and manages index operations.
    """

    def __init__(self, client: AsyncMeilisearchClient) -> None:
        """
        Initialize the indexer.

        Args:
            client: Meilisearch client for index operations
        """
        self._client = client

    async def index_work(self, work: WorkModel) -> None:
        """
        Index a single work into the appropriate index.

        Args:
            work: Work model to index
        """
        if work.work_type == ConsumableType.BOOK:
            await self.index_book(work)
        elif work.work_type == ConsumableType.PAPER:
            await self.index_paper(work)
        else:
            logger.warning(f"Unknown work type: {work.work_type}")

    async def index_book(self, work: WorkModel) -> None:
        """
        Index a book work into the books index.

        Args:
            work: Book work model to index
        """
        doc = self._work_to_book_document(work)
        task = await self._client.add_documents(BOOKS_INDEX, [doc])
        logger.debug(f"Indexed book {work.id}, task: {task.task_uid}")

    async def index_paper(self, work: WorkModel) -> None:
        """
        Index a paper work into the papers index.

        Args:
            work: Paper work model to index
        """
        doc = self._work_to_paper_document(work)
        task = await self._client.add_documents(PAPERS_INDEX, [doc])
        logger.debug(f"Indexed paper {work.id}, task: {task.task_uid}")

    async def index_books_batch(self, works: list[WorkModel]) -> None:
        """Index multiple books in a batch."""
        docs = [self._work_to_book_document(w) for w in works]
        if docs:
            task = await self._client.add_documents(BOOKS_INDEX, docs)
            logger.info(f"Indexed {len(docs)} books, task: {task.task_uid}")

    async def index_papers_batch(self, works: list[WorkModel]) -> None:
        """Index multiple papers in a batch."""
        docs = [self._work_to_paper_document(w) for w in works]
        if docs:
            task = await self._client.add_documents(PAPERS_INDEX, docs)
            logger.info(f"Indexed {len(docs)} papers, task: {task.task_uid}")

    async def remove_from_index(self, work_id: UUID, work_type: ConsumableType) -> None:
        """
        Remove a work from its index.

        Args:
            work_id: ID of the work to remove
            work_type: Type of the work (determines which index)
        """
        index_name = BOOKS_INDEX if work_type == ConsumableType.BOOK else PAPERS_INDEX
        task = await self._client.delete_documents(index_name, [str(work_id)])
        logger.debug(f"Removed {work_id} from {index_name}, task: {task.task_uid}")

    async def reindex_all(self, session: AsyncSession) -> None:
        """
        Reindex all works from the database.

        Args:
            session: Database session for querying works
        """
        from consearch.db.repositories.work import WorkRepository

        repo = WorkRepository(session)

        # Clear existing indexes
        logger.info("Clearing existing indexes...")
        await self._client.delete_all_documents(BOOKS_INDEX)
        await self._client.delete_all_documents(PAPERS_INDEX)

        # Reindex books
        logger.info("Reindexing books...")
        books = await repo.list_by_type(ConsumableType.BOOK, limit=10000)
        if books:
            await self.index_books_batch(books)

        # Reindex papers
        logger.info("Reindexing papers...")
        papers = await repo.list_by_type(ConsumableType.PAPER, limit=10000)
        if papers:
            await self.index_papers_batch(papers)

        logger.info(f"Reindexing complete: {len(books)} books, {len(papers)} papers")

    def _work_to_book_document(self, work: WorkModel) -> dict[str, Any]:
        """Convert a book work to a Meilisearch document."""
        # Extract author names from relationships
        authors = [author.name for author in work.authors] if work.authors else []

        identifiers = work.identifiers or {}

        return {
            "id": str(work.id),
            "title": work.title,
            "title_normalized": work.title_normalized,
            "authors": authors,
            "year": work.year,
            "publisher": identifiers.get("publisher"),
            "subjects": identifiers.get("subjects", []),
            "language": identifiers.get("language"),
            "identifiers": {
                "isbn_10": identifiers.get("isbn_10"),
                "isbn_13": identifiers.get("isbn_13"),
            },
            "created_at": work.created_at.isoformat() if work.created_at else None,
        }

    def _work_to_paper_document(self, work: WorkModel) -> dict[str, Any]:
        """Convert a paper work to a Meilisearch document."""
        # Extract author names from relationships
        authors = [author.name for author in work.authors] if work.authors else []

        identifiers = work.identifiers or {}

        return {
            "id": str(work.id),
            "title": work.title,
            "title_normalized": work.title_normalized,
            "authors": authors,
            "year": work.year,
            "abstract": identifiers.get("abstract"),
            "journal": identifiers.get("journal"),
            "citation_count": identifiers.get("citation_count"),
            "identifiers": {
                "doi": identifiers.get("doi"),
                "arxiv_id": identifiers.get("arxiv_id"),
            },
            "created_at": work.created_at.isoformat() if work.created_at else None,
        }
