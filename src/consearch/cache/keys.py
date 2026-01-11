"""Cache key builders for consistent key formatting."""

import hashlib
from typing import Any

from consearch.core.types import ConsumableType, SourceName


class CacheKeys:
    """Cache key builders for consistent key formatting."""

    PREFIX = "consearch"

    @classmethod
    def resolution(
        cls,
        consumable_type: ConsumableType | str,
        identifier: str,
    ) -> str:
        """Key for resolved consumable by identifier."""
        return f"{cls.PREFIX}:resolve:{consumable_type}:{identifier}"

    @classmethod
    def search(
        cls,
        query: str,
        consumable_type: ConsumableType | str,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Key for search results."""
        # Hash the query and filters for consistent key length
        filters_str = str(sorted(filters.items())) if filters else ""
        hash_input = f"{query}:{filters_str}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"{cls.PREFIX}:search:{consumable_type}:{hash_value}"

    @classmethod
    def source_record(
        cls,
        source: SourceName | str,
        source_id: str,
    ) -> str:
        """Key for source record by source-specific ID."""
        return f"{cls.PREFIX}:source:{source}:{source_id}"

    @classmethod
    def work(cls, work_id: str) -> str:
        """Key for work by internal ID."""
        return f"{cls.PREFIX}:work:{work_id}"

    @classmethod
    def author(cls, author_id: str) -> str:
        """Key for author by internal ID."""
        return f"{cls.PREFIX}:author:{author_id}"
