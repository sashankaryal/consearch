"""Search layer for Meilisearch integration."""

from consearch.search.client import (
    BOOKS_INDEX,
    PAPERS_INDEX,
    AsyncMeilisearchClient,
)
from consearch.search.indexer import SearchIndexer
from consearch.search.searcher import SearchFilters, SearchHit, SearchResponse, Searcher

__all__ = [
    # Client
    "AsyncMeilisearchClient",
    "BOOKS_INDEX",
    "PAPERS_INDEX",
    # Indexer
    "SearchIndexer",
    # Searcher
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
    "Searcher",
]
