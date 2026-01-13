"""Tests for chain resolver."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock

import pytest

from consearch.core.models import BookRecord, Identifiers
from consearch.core.types import InputType, ResolutionStatus, SourceName
from consearch.resolution.base import AbstractResolver, ResolutionResult, ResolverConfig
from consearch.resolution.chain import AggregatedResult, ChainResolver, FallbackConfig

# ============================================================================
# Mock Resolver for Testing
# ============================================================================


class MockBookResolver(AbstractResolver[BookRecord]):
    """Mock book resolver for testing chain resolver behavior."""

    SOURCE_NAME: ClassVar[SourceName] = SourceName.OPEN_LIBRARY
    BASE_URL: ClassVar[str] = "https://example.com"
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset(
        {
            InputType.ISBN_10,
            InputType.ISBN_13,
            InputType.TITLE,
        }
    )
    _BASE_RELIABILITY: ClassVar[float] = 0.8

    def __init__(
        self,
        source_name: SourceName,
        priority: int = 100,
        should_succeed: bool = True,
        config: ResolverConfig | None = None,
    ):
        super().__init__(config)
        self._source_name = source_name
        self._priority = priority
        self._should_succeed = should_succeed

    @property
    def source_name(self) -> SourceName:
        return self._source_name

    @property
    def priority(self) -> int:
        return self._priority

    async def resolve(
        self,
        query: str,
        input_type: InputType,
    ) -> ResolutionResult[BookRecord]:
        if self._should_succeed:
            record = BookRecord(
                title=f"Book from {self._source_name.value}",
                identifiers=Identifiers(isbn_13="9780134093413"),
            )
            return ResolutionResult(
                status=ResolutionStatus.SUCCESS,
                records=[record],
                source=self._source_name,
                duration_ms=100.0,
            )
        else:
            return ResolutionResult(
                status=ResolutionStatus.NOT_FOUND,
                source=self._source_name,
                duration_ms=50.0,
            )

    async def fetch_by_id(self, identifier: str) -> BookRecord | None:
        return None


# ============================================================================
# FallbackConfig Tests
# ============================================================================


class TestFallbackConfig:
    """Tests for FallbackConfig dataclass."""

    def test_default_values(self):
        """Default config should have sensible defaults."""
        config = FallbackConfig()
        assert config.stop_on_first_success is True
        assert config.min_reliability_score == 0.5
        assert config.parallel_execution is False
        assert config.total_timeout == 60.0

    def test_custom_values(self):
        """Custom values should be set correctly."""
        config = FallbackConfig(
            stop_on_first_success=False,
            min_reliability_score=0.7,
            parallel_execution=True,
            total_timeout=30.0,
        )
        assert config.stop_on_first_success is False
        assert config.min_reliability_score == 0.7
        assert config.parallel_execution is True
        assert config.total_timeout == 30.0


# ============================================================================
# AggregatedResult Tests
# ============================================================================


class TestAggregatedResult:
    """Tests for AggregatedResult dataclass."""

    def test_empty_result_not_success(self):
        """Empty result should not be success."""
        result = AggregatedResult()
        assert result.success is False
        assert result.best_result is None

    def test_success_with_primary(self):
        """Result with successful primary should be success."""
        result = AggregatedResult(
            primary_result=ResolutionResult(
                status=ResolutionStatus.SUCCESS,
                records=[BookRecord(title="Test")],
                source=SourceName.OPEN_LIBRARY,
            )
        )
        assert result.success is True

    def test_success_with_fallback(self):
        """Result with successful fallback should be success."""
        result = AggregatedResult(
            primary_result=ResolutionResult(
                status=ResolutionStatus.NOT_FOUND,
                source=SourceName.OPEN_LIBRARY,
            ),
            fallback_results=[
                ResolutionResult(
                    status=ResolutionStatus.SUCCESS,
                    records=[BookRecord(title="Test")],
                    source=SourceName.GOOGLE_BOOKS,
                )
            ],
        )
        assert result.success is True

    def test_best_result_returns_first_successful(self):
        """best_result should return first successful result."""
        fallback_result = ResolutionResult(
            status=ResolutionStatus.SUCCESS,
            records=[BookRecord(title="Fallback")],
            source=SourceName.GOOGLE_BOOKS,
        )
        result = AggregatedResult(
            primary_result=ResolutionResult(
                status=ResolutionStatus.NOT_FOUND,
                source=SourceName.OPEN_LIBRARY,
            ),
            fallback_results=[fallback_result],
        )
        assert result.best_result == fallback_result


# ============================================================================
# ChainResolver Tests
# ============================================================================


class TestChainResolver:
    """Tests for ChainResolver."""

    @pytest.fixture
    def successful_resolver(self) -> MockBookResolver:
        """Create a resolver that succeeds."""
        return MockBookResolver(
            source_name=SourceName.OPEN_LIBRARY,
            priority=100,
            should_succeed=True,
        )

    @pytest.fixture
    def failing_resolver(self) -> MockBookResolver:
        """Create a resolver that fails."""
        return MockBookResolver(
            source_name=SourceName.GOOGLE_BOOKS,
            priority=50,
            should_succeed=False,
        )

    async def test_single_successful_resolver(self, successful_resolver: MockBookResolver):
        """Single successful resolver should return success."""
        chain = ChainResolver([successful_resolver])
        result = await chain.resolve("test", InputType.TITLE)

        assert result.success is True
        assert len(result.all_records) == 1
        assert result.primary_result is not None
        assert result.primary_result.success is True

    async def test_single_failing_resolver(self, failing_resolver: MockBookResolver):
        """Single failing resolver should return not success."""
        chain = ChainResolver([failing_resolver])
        result = await chain.resolve("test", InputType.TITLE)

        assert result.success is False

    async def test_resolver_priority_ordering(self):
        """Resolvers should be tried in priority order."""
        resolver1 = MockBookResolver(SourceName.OPEN_LIBRARY, priority=100, should_succeed=False)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50, should_succeed=True)
        resolver3 = MockBookResolver(SourceName.ISBNDB, priority=10, should_succeed=True)

        chain = ChainResolver([resolver1, resolver2, resolver3])
        result = await chain.resolve("test", InputType.TITLE)

        # resolver3 (priority 10) should be tried first
        assert result.success is True
        assert result.primary_result.source == SourceName.ISBNDB

    async def test_stop_on_first_success(self):
        """With stop_on_first_success=True, should stop after first success."""
        resolver1 = MockBookResolver(SourceName.ISBNDB, priority=10, should_succeed=True)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50, should_succeed=True)

        config = FallbackConfig(stop_on_first_success=True)
        chain = ChainResolver([resolver1, resolver2], config)
        result = await chain.resolve("test", InputType.TITLE)

        # Only one source should be tried
        assert len(result.sources_tried) == 1

    async def test_continue_on_success(self):
        """With stop_on_first_success=False, should try all resolvers."""
        resolver1 = MockBookResolver(SourceName.ISBNDB, priority=10, should_succeed=True)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50, should_succeed=True)

        config = FallbackConfig(stop_on_first_success=False)
        chain = ChainResolver([resolver1, resolver2], config)
        result = await chain.resolve("test", InputType.TITLE)

        # Both sources should be tried
        assert len(result.sources_tried) == 2

    async def test_fallback_on_failure(self):
        """Failing primary should fall back to next resolver."""
        resolver1 = MockBookResolver(SourceName.ISBNDB, priority=10, should_succeed=False)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50, should_succeed=True)

        chain = ChainResolver([resolver1, resolver2])
        result = await chain.resolve("test", InputType.TITLE)

        assert result.success is True
        # First tried should fail, fallback should succeed
        assert result.primary_result.status == ResolutionStatus.NOT_FOUND
        assert len(result.fallback_results) == 1
        assert result.fallback_results[0].success is True

    async def test_no_supported_resolvers(self):
        """Should return empty result when no resolvers support input type."""
        resolver = MockBookResolver(SourceName.OPEN_LIBRARY, priority=100)
        # Override supported types to something else
        resolver.SUPPORTED_INPUT_TYPES = frozenset({InputType.DOI})

        chain = ChainResolver([resolver])
        result = await chain.resolve("test", InputType.TITLE)

        assert result.success is False
        assert len(result.sources_tried) == 0

    async def test_disabled_resolver_skipped(self):
        """Disabled resolvers should be skipped."""
        config = ResolverConfig(enabled=False)
        resolver = MockBookResolver(
            SourceName.OPEN_LIBRARY,
            priority=10,
            should_succeed=True,
            config=config,
        )

        chain = ChainResolver([resolver])
        result = await chain.resolve("test", InputType.TITLE)

        assert result.success is False
        assert len(result.sources_tried) == 0

    async def test_deduplication_by_identifier(self):
        """Records with same identifier should be deduplicated."""
        resolver1 = MockBookResolver(SourceName.ISBNDB, priority=10, should_succeed=True)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50, should_succeed=True)

        config = FallbackConfig(stop_on_first_success=False)
        chain = ChainResolver([resolver1, resolver2], config)
        result = await chain.resolve("test", InputType.TITLE)

        # Both return same ISBN, should be deduplicated
        assert len(result.all_records) == 1

    async def test_close_closes_all_resolvers(self):
        """close() should close all resolvers."""
        resolver1 = MockBookResolver(SourceName.OPEN_LIBRARY, priority=10)
        resolver2 = MockBookResolver(SourceName.GOOGLE_BOOKS, priority=50)

        resolver1.close = AsyncMock()
        resolver2.close = AsyncMock()

        chain = ChainResolver([resolver1, resolver2])
        await chain.close()

        resolver1.close.assert_called_once()
        resolver2.close.assert_called_once()

    async def test_async_context_manager(self):
        """ChainResolver should work as async context manager."""
        resolver = MockBookResolver(SourceName.OPEN_LIBRARY, priority=10)
        resolver.close = AsyncMock()

        async with ChainResolver([resolver]) as chain:
            result = await chain.resolve("test", InputType.TITLE)
            assert result.success is True

        resolver.close.assert_called_once()


# ============================================================================
# Record ID Generation Tests
# ============================================================================


class TestGetRecordId:
    """Tests for record ID generation for deduplication."""

    def test_doi_takes_priority(self):
        """DOI should be used as record ID when available."""
        record = BookRecord(
            title="Test",
            identifiers=Identifiers(
                doi="10.1234/test",
                isbn_13="9780134093413",
            ),
        )
        record_id = ChainResolver._get_record_id(record)
        assert record_id == "doi:10.1234/test"

    def test_isbn13_used_when_no_doi(self):
        """ISBN-13 should be used when DOI not available."""
        record = BookRecord(
            title="Test",
            identifiers=Identifiers(isbn_13="9780134093413"),
        )
        record_id = ChainResolver._get_record_id(record)
        assert record_id == "isbn:9780134093413"

    def test_isbn10_used_when_no_isbn13(self):
        """ISBN-10 should be used when ISBN-13 not available."""
        record = BookRecord(
            title="Test",
            identifiers=Identifiers(isbn_10="0134093410"),
        )
        record_id = ChainResolver._get_record_id(record)
        assert record_id == "isbn:0134093410"

    def test_title_fallback(self):
        """Title should be used when no identifiers available."""
        record = BookRecord(
            title="Test Book Title",
            identifiers=Identifiers(),
        )
        record_id = ChainResolver._get_record_id(record)
        assert record_id == "title:test book title"
