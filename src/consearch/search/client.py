"""Async Meilisearch client wrapper."""

from __future__ import annotations

import logging
from typing import Any

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.search import SearchResults
from meilisearch_python_sdk.models.settings import MeilisearchSettings
from meilisearch_python_sdk.models.task import TaskInfo

logger = logging.getLogger(__name__)


# Index configuration
BOOKS_INDEX = "consearch_books"
PAPERS_INDEX = "consearch_papers"

BOOKS_SETTINGS = MeilisearchSettings(
    searchable_attributes=["title", "authors", "publisher", "subjects"],
    filterable_attributes=["year", "language"],
    sortable_attributes=["year", "created_at"],
    displayed_attributes=["id", "title", "authors", "year", "publisher", "identifiers"],
)

PAPERS_SETTINGS = MeilisearchSettings(
    searchable_attributes=["title", "authors", "abstract", "journal"],
    filterable_attributes=["year", "journal"],
    sortable_attributes=["year", "citation_count", "created_at"],
    displayed_attributes=[
        "id",
        "title",
        "authors",
        "year",
        "journal",
        "identifiers",
        "citation_count",
    ],
)


class AsyncMeilisearchClient:
    """
    Async wrapper for Meilisearch operations.

    Provides methods for index management, document indexing, and search.
    """

    def __init__(self, url: str, api_key: str | None = None) -> None:
        """
        Initialize the Meilisearch client.

        Args:
            url: Meilisearch server URL
            api_key: Optional API key for authentication
        """
        self._url = url
        self._api_key = api_key
        self._client: AsyncClient | None = None

    async def _get_client(self) -> AsyncClient:
        """Get or create the async client."""
        if self._client is None:
            self._client = AsyncClient(self._url, self._api_key)
        return self._client

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health(self) -> bool:
        """Check if Meilisearch is healthy."""
        try:
            client = await self._get_client()
            health = await client.health()
            return health.status == "available"
        except Exception as e:
            logger.warning(f"Meilisearch health check failed: {e}")
            return False

    async def setup_indexes(self) -> None:
        """Create and configure indexes if they don't exist."""
        client = await self._get_client()

        # Create books index
        try:
            books_index = await client.get_index(BOOKS_INDEX)
        except Exception:
            logger.info(f"Creating index: {BOOKS_INDEX}")
            books_index = await client.create_index(BOOKS_INDEX, primary_key="id")

        await books_index.update_settings(BOOKS_SETTINGS)
        logger.info(f"Configured index: {BOOKS_INDEX}")

        # Create papers index
        try:
            papers_index = await client.get_index(PAPERS_INDEX)
        except Exception:
            logger.info(f"Creating index: {PAPERS_INDEX}")
            papers_index = await client.create_index(PAPERS_INDEX, primary_key="id")

        await papers_index.update_settings(PAPERS_SETTINGS)
        logger.info(f"Configured index: {PAPERS_INDEX}")

    async def add_documents(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
    ) -> TaskInfo:
        """
        Add or update documents in an index.

        Args:
            index_name: Name of the index
            documents: List of documents to add/update

        Returns:
            Task info for tracking the operation
        """
        client = await self._get_client()
        index = await client.get_index(index_name)
        return await index.add_documents(documents)

    async def delete_documents(
        self,
        index_name: str,
        document_ids: list[str],
    ) -> TaskInfo:
        """
        Delete documents from an index.

        Args:
            index_name: Name of the index
            document_ids: List of document IDs to delete

        Returns:
            Task info for tracking the operation
        """
        client = await self._get_client()
        index = await client.get_index(index_name)
        return await index.delete_documents(document_ids)

    async def search(
        self,
        index_name: str,
        query: str,
        *,
        filter: str | list[str] | None = None,
        sort: list[str] | None = None,
        offset: int = 0,
        limit: int = 20,
        attributes_to_retrieve: list[str] | None = None,
    ) -> SearchResults:
        """
        Search documents in an index.

        Args:
            index_name: Name of the index to search
            query: Search query string
            filter: Filter expression (e.g., "year > 2020")
            sort: Sort criteria (e.g., ["year:desc"])
            offset: Number of results to skip
            limit: Maximum number of results
            attributes_to_retrieve: Specific attributes to return

        Returns:
            Search results with hits and metadata
        """
        client = await self._get_client()
        index = await client.get_index(index_name)

        return await index.search(
            query,
            filter=filter,
            sort=sort,
            offset=offset,
            limit=limit,
            attributes_to_retrieve=attributes_to_retrieve,
        )

    async def get_document(
        self,
        index_name: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a single document by ID.

        Args:
            index_name: Name of the index
            document_id: Document ID

        Returns:
            Document data or None if not found
        """
        try:
            client = await self._get_client()
            index = await client.get_index(index_name)
            return await index.get_document(document_id)
        except Exception:
            return None

    async def delete_all_documents(self, index_name: str) -> TaskInfo:
        """Delete all documents from an index."""
        client = await self._get_client()
        index = await client.get_index(index_name)
        return await index.delete_all_documents()

    async def wait_for_task(self, task_info: TaskInfo, timeout_ms: int = 30000) -> None:
        """Wait for a task to complete."""
        client = await self._get_client()
        await client.wait_for_task(task_info.task_uid, timeout_in_ms=timeout_ms)

    async def __aenter__(self) -> AsyncMeilisearchClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
