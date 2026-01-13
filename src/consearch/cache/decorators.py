"""Caching decorators for async functions."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def cached(
    key_builder: Callable[..., str],
    ttl: int = 3600,
    cache_none: bool = False,
):
    """
    Decorator for caching async function results.

    Args:
        key_builder: Function that takes the same args as decorated function
                    and returns a cache key string.
        ttl: Time to live in seconds (default 1 hour).
        cache_none: Whether to cache None results (default False).

    Usage:
        @cached(lambda isbn: f"book:{isbn}", ttl=3600)
        async def get_book(isbn: str) -> Book | None:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            # Get cache from self._cache if available
            cache = getattr(self, "_cache", None)
            if cache is None:
                return await func(self, *args, **kwargs)

            # Build cache key
            key = key_builder(*args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Call the function
            result = await func(self, *args, **kwargs)

            # Cache the result
            if result is not None or cache_none:
                await cache.set(key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def cache_invalidate(
    key_builder: Callable[..., str],
):
    """
    Decorator that invalidates cache after function execution.

    Args:
        key_builder: Function that returns the cache key(s) to invalidate.

    Usage:
        @cache_invalidate(lambda work_id: f"work:{work_id}")
        async def update_work(work_id: str, data: dict) -> Work:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(self, *args, **kwargs)

            # Invalidate cache
            cache = getattr(self, "_cache", None)
            if cache is not None:
                key = key_builder(*args, **kwargs)
                if isinstance(key, list):
                    for k in key:
                        await cache.delete(k)
                else:
                    await cache.delete(key)

            return result

        return wrapper

    return decorator
