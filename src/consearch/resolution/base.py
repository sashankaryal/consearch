"""Abstract base resolver with HTTP client management and rate limiting."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, ClassVar, Generic, TypeVar

import httpx
from pydantic import BaseModel, Field

from consearch.core.exceptions import RateLimitError, ResolverUnavailableError
from consearch.core.models import BaseRecord
from consearch.core.types import InputType, ResolutionStatus, SourceName

RecordT = TypeVar("RecordT", bound=BaseRecord)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 1.0
    requests_per_minute: float | None = None
    burst_size: int = 1
    retry_on_429: bool = True
    max_429_retries: int = 3
    backoff_factor: float = 2.0


@dataclass
class RateLimitState:
    """Tracks rate limit state for a resolver."""

    request_times: deque[float] = field(default_factory=deque)
    retry_after_until: float = 0.0
    consecutive_429s: int = 0


class ResolverConfig(BaseModel):
    """Configuration for a resolver."""

    api_key: str | None = None
    base_url: str | None = None
    timeout: float = 30.0
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    enabled: bool = True


class ResolutionResult(BaseModel, Generic[RecordT]):
    """Result of a resolution attempt."""

    status: ResolutionStatus
    records: list[Any] = Field(default_factory=list)
    error_message: str | None = None
    source: SourceName
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == ResolutionStatus.SUCCESS and len(self.records) > 0


class AsyncRateLimiter:
    """Async rate limiter with token bucket algorithm."""

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self._state = RateLimitState()
        self._lock = asyncio.Lock()
        self._semaphore: asyncio.Semaphore | None = None

    async def acquire(self) -> None:
        """Acquire a permit to make a request."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.burst_size)

        async with self._semaphore:
            async with self._lock:
                await self._wait_for_permit()
                self._record_request()

    async def _wait_for_permit(self) -> None:
        """Wait until a request is permitted."""
        now = time.monotonic()

        # Check if we're in a 429 backoff period
        if now < self._state.retry_after_until:
            wait_time = self._state.retry_after_until - now
            await asyncio.sleep(wait_time)
            now = time.monotonic()

        # Clean up old request times
        self._cleanup_old_requests(now)

        # Calculate wait time for rate limits
        wait_time = 0.0

        # Per-second limit
        if self.config.requests_per_second:
            window_start = now - 1.0
            recent = [t for t in self._state.request_times if t > window_start]
            if len(recent) >= self.config.requests_per_second:
                wait_time = max(wait_time, recent[0] + 1.0 - now)

        # Per-minute limit
        if self.config.requests_per_minute:
            window_start = now - 60.0
            recent = [t for t in self._state.request_times if t > window_start]
            if len(recent) >= self.config.requests_per_minute:
                wait_time = max(wait_time, recent[0] + 60.0 - now)

        if wait_time > 0:
            await asyncio.sleep(wait_time)

    def _record_request(self) -> None:
        """Record a request timestamp."""
        self._state.request_times.append(time.monotonic())

    def _cleanup_old_requests(self, now: float) -> None:
        """Remove request times older than 1 minute."""
        cutoff = now - 60.0
        while self._state.request_times and self._state.request_times[0] < cutoff:
            self._state.request_times.popleft()

    def handle_429(self, retry_after: float | None = None) -> float:
        """Handle a 429 response, returning the wait time."""
        self._state.consecutive_429s += 1

        if retry_after:
            wait_time = retry_after
        else:
            # Exponential backoff
            wait_time = min(
                60.0 * self.config.backoff_factor ** (self._state.consecutive_429s - 1),
                300.0,  # Max 5 minutes
            )

        self._state.retry_after_until = time.monotonic() + wait_time
        return wait_time

    def reset_429_state(self) -> None:
        """Reset 429 tracking after successful request."""
        self._state.consecutive_429s = 0

    @property
    def should_retry_429(self) -> bool:
        """Whether another 429 retry should be attempted."""
        return (
            self.config.retry_on_429
            and self._state.consecutive_429s < self.config.max_429_retries
        )


class AbstractResolver(ABC, Generic[RecordT]):
    """
    Abstract base class for all resolvers.

    Provides:
    - HTTP client management with connection pooling
    - Rate limiting with 429 handling
    - Reliability scoring
    - Consistent error handling
    """

    # Class-level configuration (to be overridden by subclasses)
    SOURCE_NAME: ClassVar[SourceName]
    BASE_URL: ClassVar[str]
    DEFAULT_RATE_LIMIT: ClassVar[RateLimitConfig] = RateLimitConfig(
        requests_per_second=1.0,
        burst_size=1,
    )
    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]]

    # Base reliability score for this source
    _BASE_RELIABILITY: ClassVar[float] = 0.8

    def __init__(self, config: ResolverConfig | None = None) -> None:
        self.config = config or ResolverConfig()
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = AsyncRateLimiter(
            self.config.rate_limit or self.DEFAULT_RATE_LIMIT
        )

        # Reliability tracking
        self._success_count: int = 0
        self._failure_count: int = 0
        self._total_latency_ms: float = 0.0

    @property
    def source_name(self) -> SourceName:
        """The source type for this resolver."""
        return self.SOURCE_NAME

    @property
    def supported_input_types(self) -> frozenset[InputType]:
        """Input types this resolver can handle."""
        return self.SUPPORTED_INPUT_TYPES

    @property
    def reliability_score(self) -> float:
        """Calculate reliability score based on success rate and latency."""
        total = self._success_count + self._failure_count
        if total == 0:
            return self._BASE_RELIABILITY

        success_rate = self._success_count / total

        # Penalize high latency (over 5 seconds avg)
        avg_latency = self._total_latency_ms / max(total, 1)
        latency_factor = min(1.0, 5000.0 / max(avg_latency, 100.0))

        # Weighted combination
        return self._BASE_RELIABILITY * 0.4 + success_rate * 0.4 + latency_factor * 0.2

    @property
    def is_enabled(self) -> bool:
        """Whether this resolver is enabled."""
        return self.config.enabled

    @property
    def priority(self) -> int:
        """Priority for fallback ordering (lower = higher priority)."""
        return 100  # Default, override in subclasses

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[httpx.AsyncClient]:
        """Get or create HTTP client with proper lifecycle."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url or self.BASE_URL,
                timeout=httpx.Timeout(self.config.timeout),
                headers=self._get_default_headers(),
                follow_redirects=True,
            )

        try:
            yield self._client
        except httpx.HTTPError as e:
            raise ResolverUnavailableError(
                message=f"HTTP error: {e}",
                source=self.source_name.value,
            ) from e

    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for requests. Override to add auth."""
        return {
            "User-Agent": "consearch/1.0",
            "Accept": "application/json",
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and 429 handling."""
        start = time.monotonic()

        await self._rate_limiter.acquire()

        async with self._get_client() as client:
            while True:
                response = await client.request(method, url, **kwargs)

                if response.status_code == 429:
                    if self._rate_limiter.should_retry_429:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = self._rate_limiter.handle_429(
                            float(retry_after) if retry_after else None
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        self._record_failure()
                        raise RateLimitError(
                            message="Rate limit exceeded",
                            source=self.source_name.value,
                            retry_after=wait_time,
                        )

                # Success or other error
                self._rate_limiter.reset_429_state()
                break

        # Track metrics
        duration_ms = (time.monotonic() - start) * 1000
        self._total_latency_ms += duration_ms

        if response.is_success:
            self._success_count += 1
        else:
            self._failure_count += 1

        return response

    def _record_failure(self) -> None:
        """Record a resolution failure."""
        self._failure_count += 1

    def supports(self, input_type: InputType) -> bool:
        """Check if this resolver supports the given input type."""
        return input_type in self.supported_input_types

    # Abstract methods
    @abstractmethod
    async def resolve(
        self,
        query: str,
        input_type: InputType,
    ) -> ResolutionResult[RecordT]:
        """
        Resolve a query to source records.

        Args:
            query: The search query (identifier or text)
            input_type: The detected input type

        Returns:
            ResolutionResult with found records or error status
        """
        ...

    @abstractmethod
    async def fetch_by_id(
        self,
        identifier: str,
    ) -> RecordT | None:
        """
        Fetch a single record by its source-specific identifier.

        Args:
            identifier: The source-specific identifier

        Returns:
            The record if found, None otherwise
        """
        ...

    async def __aenter__(self) -> "AbstractResolver[RecordT]":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
