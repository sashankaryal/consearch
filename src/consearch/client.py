"""Main library client for standalone usage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from consearch.config import ConsearchSettings
from consearch.core.models import BookRecord, PaperRecord
from consearch.core.types import ConsumableType, InputType
from consearch.detection.identifier import IdentifierDetector
from consearch.resolution.chain import AggregatedResult, FallbackConfig
from consearch.resolution.registry import ResolverRegistry

if TYPE_CHECKING:
    from consearch.cache.client import AsyncRedisClient

logger = logging.getLogger(__name__)


class ConsearchClient:
    """
    Main client for the consearch library.

    Provides a unified interface for resolving and searching consumables
    (books and papers) without requiring the web server.

    Usage:
        async with ConsearchClient() as client:
            # Resolve a book by ISBN
            result = await client.resolve_book("978-0-13-468599-1")

            # Resolve a paper by DOI
            result = await client.resolve_paper("10.1038/nature12373")

            # Auto-detect input type
            result = await client.resolve("978-0-13-468599-1")

    Settings are loaded from environment variables or can be passed explicitly.
    """

    def __init__(
        self,
        settings: ConsearchSettings | None = None,
        *,
        use_cache: bool = True,
    ) -> None:
        """
        Initialize the client.

        Args:
            settings: Application settings. If not provided, loaded from environment.
            use_cache: Whether to use Redis caching if available.
        """
        self._settings = settings or ConsearchSettings()
        self._use_cache = use_cache
        self._registry: ResolverRegistry | None = None
        self._cache: AsyncRedisClient | None = None
        self._detector = IdentifierDetector()

    async def __aenter__(self) -> ConsearchClient:
        """Initialize resources on context entry."""
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up resources on context exit."""
        await self.close()

    async def _initialize(self) -> None:
        """Initialize client resources."""
        # Initialize resolver registry
        self._registry = ResolverRegistry.from_settings(self._settings)

        # Initialize cache if available
        if self._use_cache and self._settings.redis_url:
            try:
                from consearch.cache.client import AsyncRedisClient

                self._cache = AsyncRedisClient(str(self._settings.redis_url))
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize cache: {e}")
                self._cache = None

    async def close(self) -> None:
        """Close all resources."""
        if self._registry:
            await self._registry.close_all()
            self._registry = None

        if self._cache:
            await self._cache.close()
            self._cache = None

    def _ensure_initialized(self) -> None:
        """Ensure client is initialized."""
        if self._registry is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with ConsearchClient() as client:'"
            )

    async def resolve_book(
        self,
        query: str,
        input_type: InputType | None = None,
        *,
        fallback_config: FallbackConfig | None = None,
    ) -> AggregatedResult[BookRecord]:
        """
        Resolve a book by identifier or title.

        Args:
            query: ISBN, title, or other identifier
            input_type: Explicit input type (auto-detected if not provided)
            fallback_config: Configuration for fallback resolution

        Returns:
            Aggregated result with records from all sources
        """
        self._ensure_initialized()

        # Detect input type if not provided
        if input_type is None:
            detection = self._detector.detect(query)
            input_type = detection.input_type

        # Get chain resolver
        chain = self._registry.get_book_chain(fallback_config)

        # Resolve
        return await chain.resolve(query, input_type)

    async def resolve_paper(
        self,
        query: str,
        input_type: InputType | None = None,
        *,
        fallback_config: FallbackConfig | None = None,
    ) -> AggregatedResult[PaperRecord]:
        """
        Resolve an academic paper by identifier or title.

        Args:
            query: DOI, arXiv ID, title, or citation string
            input_type: Explicit input type (auto-detected if not provided)
            fallback_config: Configuration for fallback resolution

        Returns:
            Aggregated result with records from all sources
        """
        self._ensure_initialized()

        # Detect input type if not provided
        if input_type is None:
            detection = self._detector.detect(query)
            input_type = detection.input_type

        # Get chain resolver
        chain = self._registry.get_paper_chain(fallback_config)

        # Resolve
        return await chain.resolve(query, input_type)

    async def resolve(
        self,
        query: str,
        consumable_type: ConsumableType | None = None,
        input_type: InputType | None = None,
        *,
        fallback_config: FallbackConfig | None = None,
    ) -> AggregatedResult[BookRecord] | AggregatedResult[PaperRecord]:
        """
        Resolve a consumable with automatic type detection.

        Args:
            query: Identifier or title
            consumable_type: Type of consumable (auto-detected if not provided)
            input_type: Input type (auto-detected if not provided)
            fallback_config: Configuration for fallback resolution

        Returns:
            Aggregated result (type depends on consumable_type)
        """
        self._ensure_initialized()

        # Detect types if not provided
        if consumable_type is None or input_type is None:
            detection = self._detector.detect(query)
            if input_type is None:
                input_type = detection.input_type
            if consumable_type is None:
                consumable_type = detection.consumable_type

        # Resolve based on consumable type
        if consumable_type == ConsumableType.BOOK:
            return await self.resolve_book(query, input_type, fallback_config=fallback_config)
        elif consumable_type == ConsumableType.PAPER:
            return await self.resolve_paper(query, input_type, fallback_config=fallback_config)
        else:
            # Default to paper for DOI/arXiv, book for ISBN
            if input_type in (InputType.DOI, InputType.ARXIV, InputType.PMID, InputType.CITATION):
                return await self.resolve_paper(query, input_type, fallback_config=fallback_config)
            elif input_type in (InputType.ISBN_10, InputType.ISBN_13):
                return await self.resolve_book(query, input_type, fallback_config=fallback_config)
            else:
                # For titles and unknown types, try paper first
                return await self.resolve_paper(query, input_type, fallback_config=fallback_config)

    def detect_input_type(self, query: str) -> tuple[InputType, float, ConsumableType | None]:
        """
        Detect the input type of a query string.

        Args:
            query: The input string to analyze

        Returns:
            Tuple of (input_type, confidence, consumable_type)
        """
        detection = self._detector.detect(query)
        return detection.input_type, detection.confidence, detection.consumable_type


# Convenience functions for one-off resolutions
async def resolve_book(
    query: str,
    input_type: InputType | None = None,
    *,
    settings: ConsearchSettings | None = None,
) -> AggregatedResult[BookRecord]:
    """
    Resolve a book (convenience function).

    For multiple resolutions, use ConsearchClient for better performance.
    """
    async with ConsearchClient(settings) as client:
        return await client.resolve_book(query, input_type)


async def resolve_paper(
    query: str,
    input_type: InputType | None = None,
    *,
    settings: ConsearchSettings | None = None,
) -> AggregatedResult[PaperRecord]:
    """
    Resolve a paper (convenience function).

    For multiple resolutions, use ConsearchClient for better performance.
    """
    async with ConsearchClient(settings) as client:
        return await client.resolve_paper(query, input_type)
