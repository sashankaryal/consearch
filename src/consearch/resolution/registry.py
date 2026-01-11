"""Resolver registry for managing and creating resolver instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consearch.core.models import BookRecord, PaperRecord
from consearch.core.types import ConsumableType
from consearch.resolution.base import AbstractResolver, ResolverConfig
from consearch.resolution.chain import ChainResolver, FallbackConfig

if TYPE_CHECKING:
    from consearch.config import ConsearchSettings


class ResolverRegistry:
    """
    Factory for creating and managing resolver instances.

    Handles resolver configuration based on available API keys
    and creates appropriate chain resolvers for each consumable type.
    """

    def __init__(self) -> None:
        self._book_resolvers: list[AbstractResolver[BookRecord]] = []
        self._paper_resolvers: list[AbstractResolver[PaperRecord]] = []

    def register_book_resolver(self, resolver: AbstractResolver[BookRecord]) -> None:
        """Register a book resolver."""
        self._book_resolvers.append(resolver)

    def register_paper_resolver(self, resolver: AbstractResolver[PaperRecord]) -> None:
        """Register a paper resolver."""
        self._paper_resolvers.append(resolver)

    def get_book_chain(
        self,
        config: FallbackConfig | None = None,
    ) -> ChainResolver[BookRecord]:
        """Get a chain resolver for books."""
        return ChainResolver(self._book_resolvers, config)

    def get_paper_chain(
        self,
        config: FallbackConfig | None = None,
    ) -> ChainResolver[PaperRecord]:
        """Get a chain resolver for papers."""
        return ChainResolver(self._paper_resolvers, config)

    def get_chain(
        self,
        consumable_type: ConsumableType,
        config: FallbackConfig | None = None,
    ) -> ChainResolver:
        """Get a chain resolver for the given consumable type."""
        if consumable_type == ConsumableType.BOOK:
            return self.get_book_chain(config)
        elif consumable_type == ConsumableType.PAPER:
            return self.get_paper_chain(config)
        else:
            raise ValueError(f"Unsupported consumable type: {consumable_type}")

    @classmethod
    def from_settings(cls, settings: "ConsearchSettings") -> "ResolverRegistry":
        """
        Create a registry with resolvers configured from settings.

        Automatically registers available resolvers based on API keys.
        """
        registry = cls()

        # Register book resolvers
        registry._register_book_resolvers(settings)

        # Register paper resolvers
        registry._register_paper_resolvers(settings)

        return registry

    def _register_book_resolvers(self, settings: "ConsearchSettings") -> None:
        """Register book resolvers based on available API keys."""
        from consearch.resolution.books.openlibrary import OpenLibraryResolver

        # ISBNDb (primary, requires API key)
        if settings.isbndb_api_key:
            # Import here to avoid circular imports
            try:
                from consearch.resolution.books.isbndb import ISBNDbResolver

                self.register_book_resolver(
                    ISBNDbResolver(
                        ResolverConfig(api_key=settings.isbndb_api_key)
                    )
                )
            except ImportError:
                pass

        # Google Books (fallback, optional API key)
        try:
            from consearch.resolution.books.google_books import GoogleBooksResolver

            self.register_book_resolver(
                GoogleBooksResolver(
                    ResolverConfig(api_key=settings.google_books_api_key)
                )
            )
        except ImportError:
            pass

        # OpenLibrary (fallback, no API key needed)
        self.register_book_resolver(OpenLibraryResolver())

    def _register_paper_resolvers(self, settings: "ConsearchSettings") -> None:
        """Register paper resolvers based on available API keys."""
        from consearch.resolution.papers.crossref import CrossrefResolver

        # Crossref (primary, email for polite pool)
        self.register_paper_resolver(
            CrossrefResolver(
                ResolverConfig(api_key=settings.crossref_email)
            )
        )

        # Semantic Scholar (fallback, optional API key)
        if settings.semantic_scholar_api_key:
            try:
                from consearch.resolution.papers.semantic_scholar import (
                    SemanticScholarResolver,
                )

                self.register_paper_resolver(
                    SemanticScholarResolver(
                        ResolverConfig(api_key=settings.semantic_scholar_api_key)
                    )
                )
            except ImportError:
                pass

    async def close_all(self) -> None:
        """Close all registered resolvers."""
        for resolver in self._book_resolvers:
            await resolver.close()
        for resolver in self._paper_resolvers:
            await resolver.close()
