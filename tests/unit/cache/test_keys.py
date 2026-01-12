"""Tests for cache key builders."""

from __future__ import annotations

import pytest

from consearch.cache.keys import CacheKeys
from consearch.core.types import ConsumableType, SourceName


# ============================================================================
# Resolution Key Tests
# ============================================================================


class TestResolutionKeys:
    """Tests for resolution cache keys."""

    @pytest.mark.parametrize(
        "consumable_type,identifier,expected",
        [
            (ConsumableType.BOOK, "9780134093413", "consearch:resolve:book:9780134093413"),
            (ConsumableType.PAPER, "10.1038/nature12373", "consearch:resolve:paper:10.1038/nature12373"),
            ("book", "test-id", "consearch:resolve:book:test-id"),
            ("paper", "test-id", "consearch:resolve:paper:test-id"),
        ],
    )
    def test_resolution_key_format(
        self,
        consumable_type: ConsumableType | str,
        identifier: str,
        expected: str,
    ):
        """Resolution keys should have correct format."""
        key = CacheKeys.resolution(consumable_type, identifier)
        assert key == expected

    def test_resolution_key_uniqueness(self):
        """Different identifiers should produce different keys."""
        key1 = CacheKeys.resolution(ConsumableType.BOOK, "isbn1")
        key2 = CacheKeys.resolution(ConsumableType.BOOK, "isbn2")
        assert key1 != key2

    def test_resolution_key_type_uniqueness(self):
        """Same identifier with different types should produce different keys."""
        key1 = CacheKeys.resolution(ConsumableType.BOOK, "test")
        key2 = CacheKeys.resolution(ConsumableType.PAPER, "test")
        assert key1 != key2


# ============================================================================
# Search Key Tests
# ============================================================================


class TestSearchKeys:
    """Tests for search cache keys."""

    def test_search_key_basic(self):
        """Basic search key should have correct prefix."""
        key = CacheKeys.search("machine learning", ConsumableType.PAPER)
        assert key.startswith("consearch:search:paper:")

    def test_search_key_with_filters(self):
        """Search key with filters should be deterministic."""
        filters = {"year_min": 2020, "language": "en"}
        key1 = CacheKeys.search("test", ConsumableType.BOOK, filters)
        key2 = CacheKeys.search("test", ConsumableType.BOOK, filters)
        assert key1 == key2

    def test_search_key_different_filters(self):
        """Different filters should produce different keys."""
        key1 = CacheKeys.search("test", ConsumableType.BOOK, {"year_min": 2020})
        key2 = CacheKeys.search("test", ConsumableType.BOOK, {"year_min": 2021})
        assert key1 != key2

    def test_search_key_filter_order_independent(self):
        """Filter order should not affect key."""
        filters1 = {"a": 1, "b": 2}
        filters2 = {"b": 2, "a": 1}
        key1 = CacheKeys.search("test", ConsumableType.BOOK, filters1)
        key2 = CacheKeys.search("test", ConsumableType.BOOK, filters2)
        assert key1 == key2

    def test_search_key_none_filters(self):
        """None filters should work like empty filters."""
        key1 = CacheKeys.search("test", ConsumableType.BOOK, None)
        key2 = CacheKeys.search("test", ConsumableType.BOOK)
        assert key1 == key2

    def test_search_key_hash_length(self):
        """Search key hash should be truncated."""
        key = CacheKeys.search("test", ConsumableType.BOOK)
        # Format is consearch:search:book:{hash}
        parts = key.split(":")
        assert len(parts) == 4
        # Hash should be 12 characters
        assert len(parts[3]) == 12


# ============================================================================
# Source Record Key Tests
# ============================================================================


class TestSourceRecordKeys:
    """Tests for source record cache keys."""

    @pytest.mark.parametrize(
        "source,source_id,expected",
        [
            (SourceName.OPEN_LIBRARY, "OL12345W", "consearch:source:open_library:OL12345W"),
            (SourceName.CROSSREF, "10.1038/nature", "consearch:source:crossref:10.1038/nature"),
            (SourceName.ISBNDB, "book123", "consearch:source:isbndb:book123"),
            ("google_books", "abc123", "consearch:source:google_books:abc123"),
        ],
    )
    def test_source_record_key_format(
        self,
        source: SourceName | str,
        source_id: str,
        expected: str,
    ):
        """Source record keys should have correct format."""
        key = CacheKeys.source_record(source, source_id)
        assert key == expected


# ============================================================================
# Work Key Tests
# ============================================================================


class TestWorkKeys:
    """Tests for work cache keys."""

    def test_work_key_format(self):
        """Work key should have correct format."""
        work_id = "550e8400-e29b-41d4-a716-446655440000"
        key = CacheKeys.work(work_id)
        assert key == f"consearch:work:{work_id}"

    def test_work_key_uniqueness(self):
        """Different work IDs should produce different keys."""
        key1 = CacheKeys.work("id1")
        key2 = CacheKeys.work("id2")
        assert key1 != key2


# ============================================================================
# Author Key Tests
# ============================================================================


class TestAuthorKeys:
    """Tests for author cache keys."""

    def test_author_key_format(self):
        """Author key should have correct format."""
        author_id = "550e8400-e29b-41d4-a716-446655440000"
        key = CacheKeys.author(author_id)
        assert key == f"consearch:author:{author_id}"

    def test_author_key_uniqueness(self):
        """Different author IDs should produce different keys."""
        key1 = CacheKeys.author("id1")
        key2 = CacheKeys.author("id2")
        assert key1 != key2


# ============================================================================
# General Key Properties
# ============================================================================


class TestKeyProperties:
    """Tests for general cache key properties."""

    def test_prefix_consistency(self):
        """All keys should start with the same prefix."""
        keys = [
            CacheKeys.resolution(ConsumableType.BOOK, "test"),
            CacheKeys.search("test", ConsumableType.BOOK),
            CacheKeys.source_record(SourceName.CROSSREF, "test"),
            CacheKeys.work("test"),
            CacheKeys.author("test"),
        ]
        for key in keys:
            assert key.startswith(CacheKeys.PREFIX)

    def test_keys_are_strings(self):
        """All keys should be strings."""
        keys = [
            CacheKeys.resolution(ConsumableType.BOOK, "test"),
            CacheKeys.search("test", ConsumableType.BOOK),
            CacheKeys.source_record(SourceName.CROSSREF, "test"),
            CacheKeys.work("test"),
            CacheKeys.author("test"),
        ]
        for key in keys:
            assert isinstance(key, str)

    def test_keys_no_spaces(self):
        """Keys should not contain spaces."""
        keys = [
            CacheKeys.resolution(ConsumableType.BOOK, "test"),
            CacheKeys.search("test query", ConsumableType.BOOK),
            CacheKeys.source_record(SourceName.CROSSREF, "test"),
        ]
        for key in keys:
            assert " " not in key
