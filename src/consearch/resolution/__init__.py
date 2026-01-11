"""Resolution layer for fetching metadata from external sources."""

from consearch.resolution.base import (
    AbstractResolver,
    RateLimitConfig,
    ResolutionResult,
    ResolverConfig,
)
from consearch.resolution.chain import (
    AggregatedResult,
    ChainResolver,
    FallbackConfig,
)
from consearch.resolution.registry import ResolverRegistry

__all__ = [
    # Base
    "AbstractResolver",
    "RateLimitConfig",
    "ResolutionResult",
    "ResolverConfig",
    # Chain
    "AggregatedResult",
    "ChainResolver",
    "FallbackConfig",
    # Registry
    "ResolverRegistry",
]
