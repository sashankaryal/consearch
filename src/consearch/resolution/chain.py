"""Chain resolver for fallback resolution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from consearch.core.models import BaseRecord
from consearch.core.types import InputType, ResolutionStatus
from consearch.resolution.base import AbstractResolver, ResolutionResult

logger = logging.getLogger(__name__)

RecordT = TypeVar("RecordT", bound=BaseRecord)


@dataclass
class FallbackConfig:
    """Configuration for fallback resolution."""

    # Stop on first success or try all sources
    stop_on_first_success: bool = True

    # Minimum reliability score to use a resolver
    min_reliability_score: float = 0.5

    # Whether to run resolvers in parallel (when not stopping on first)
    parallel_execution: bool = False

    # Timeout for the entire fallback chain (seconds)
    total_timeout: float = 60.0


@dataclass
class AggregatedResult(Generic[RecordT]):
    """Result from fallback resolution with results from multiple sources."""

    primary_result: ResolutionResult | None = None
    fallback_results: list[ResolutionResult] = field(default_factory=list)
    all_records: list[RecordT] = field(default_factory=list)
    sources_tried: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Whether any resolver succeeded."""
        if self.primary_result and self.primary_result.success:
            return True
        return any(r.success for r in self.fallback_results)

    @property
    def best_result(self) -> ResolutionResult | None:
        """Return the best result (first successful)."""
        all_results = []
        if self.primary_result:
            all_results.append(self.primary_result)
        all_results.extend(self.fallback_results)

        successful = [r for r in all_results if r.success]
        if not successful:
            # Return first result as fallback
            return self.primary_result or (self.fallback_results[0] if self.fallback_results else None)

        # Return first successful (already sorted by priority)
        return successful[0]


class ChainResolver(Generic[RecordT]):
    """
    Orchestrates resolution across multiple resolvers with fallback support.

    Features:
    - Primary + fallback resolver chain
    - Configurable stop conditions
    - Parallel execution option
    - Result aggregation from multiple sources
    """

    def __init__(
        self,
        resolvers: list[AbstractResolver[RecordT]],
        config: FallbackConfig | None = None,
    ) -> None:
        # Sort by priority (lower = higher priority)
        self._resolvers = sorted(resolvers, key=lambda r: r.priority)
        self.config = config or FallbackConfig()

    async def resolve(
        self,
        query: str,
        input_type: InputType,
    ) -> AggregatedResult[RecordT]:
        """Resolve using resolvers in priority order with fallback."""
        result = AggregatedResult[RecordT]()

        # Filter resolvers by input type support and reliability
        active_resolvers = self._filter_resolvers(input_type)

        if not active_resolvers:
            logger.warning(f"No resolvers support input type: {input_type}")
            return result

        try:
            async with asyncio.timeout(self.config.total_timeout):
                if self.config.parallel_execution and not self.config.stop_on_first_success:
                    # Run all resolvers in parallel
                    results = await self._run_parallel(active_resolvers, query, input_type)
                    if results:
                        result.primary_result = results[0]
                        result.fallback_results = results[1:]
                else:
                    # Run resolvers sequentially
                    results = await self._run_sequential(active_resolvers, query, input_type)
                    if results:
                        result.primary_result = results[0]
                        result.fallback_results = results[1:]

                result.sources_tried = [r.source.value for r in (results or [])]

        except asyncio.TimeoutError:
            logger.warning("Fallback resolution timed out")

        # Aggregate all records
        result.all_records = self._aggregate_records(result)

        return result

    def _filter_resolvers(
        self,
        input_type: InputType,
    ) -> list[AbstractResolver[RecordT]]:
        """Filter resolvers by support and reliability."""
        return [
            r
            for r in self._resolvers
            if (
                r.is_enabled
                and r.supports(input_type)
                and r.reliability_score >= self.config.min_reliability_score
            )
        ]

    async def _try_resolver(
        self,
        resolver: AbstractResolver[RecordT],
        query: str,
        input_type: InputType,
    ) -> ResolutionResult:
        """Try a single resolver with error handling."""
        try:
            return await resolver.resolve(query, input_type)
        except Exception as e:
            logger.exception(f"Resolver {resolver.source_name} failed: {e}")
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=resolver.source_name,
                error_message=str(e),
            )

    async def _run_sequential(
        self,
        resolvers: list[AbstractResolver[RecordT]],
        query: str,
        input_type: InputType,
    ) -> list[ResolutionResult]:
        """Run resolvers sequentially, stopping on first success if configured."""
        results = []

        for resolver in resolvers:
            result = await self._try_resolver(resolver, query, input_type)
            results.append(result)

            if self.config.stop_on_first_success and result.success:
                break

        return results

    async def _run_parallel(
        self,
        resolvers: list[AbstractResolver[RecordT]],
        query: str,
        input_type: InputType,
    ) -> list[ResolutionResult]:
        """Run all resolvers in parallel."""
        tasks = [self._try_resolver(resolver, query, input_type) for resolver in resolvers]
        return await asyncio.gather(*tasks)

    def _aggregate_records(
        self,
        result: AggregatedResult[RecordT],
    ) -> list[RecordT]:
        """Aggregate records from all sources, deduplicating by identifier."""
        seen_ids: set[str] = set()
        aggregated: list[RecordT] = []

        all_results = []
        if result.primary_result:
            all_results.append(result.primary_result)
        all_results.extend(result.fallback_results)

        for res in all_results:
            for record in res.records:
                record_id = self._get_record_id(record)

                if record_id and record_id in seen_ids:
                    # Record already seen - could merge source metadata here
                    continue

                if record_id:
                    seen_ids.add(record_id)
                aggregated.append(record)

        return aggregated

    @staticmethod
    def _get_record_id(record: RecordT) -> str | None:
        """Get a unique identifier for deduplication."""
        identifiers = record.identifiers

        # Try DOI first (most authoritative)
        if identifiers.doi:
            return f"doi:{identifiers.doi}"

        # Try ISBN
        if identifiers.isbn_13:
            return f"isbn:{identifiers.isbn_13}"
        if identifiers.isbn_10:
            return f"isbn:{identifiers.isbn_10}"

        # Try arXiv
        if identifiers.arxiv_id:
            return f"arxiv:{identifiers.arxiv_id}"

        # Fall back to normalized title
        return f"title:{record.title.lower()}"

    async def close(self) -> None:
        """Close all resolvers."""
        for resolver in self._resolvers:
            await resolver.close()

    async def __aenter__(self) -> "ChainResolver[RecordT]":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
