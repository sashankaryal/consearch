"""Async Redis client wrapper."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis


class AsyncRedisClient:
    """Async Redis client wrapper with JSON serialization."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: aioredis.ConnectionPool | None = None
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self._pool = aioredis.ConnectionPool.from_url(
            self._redis_url,
            max_connections=20,
            decode_responses=True,
        )
        self._redis = aioredis.Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()
        if self._pool:
            await self._pool.disconnect()
        self._redis = None
        self._pool = None

    async def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        if not self._redis:
            return None
        value = await self._redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
    ) -> None:
        """Set a value in cache with TTL."""
        if not self._redis:
            return
        serialized = json.dumps(value, default=str)
        await self._redis.set(key, serialized, ex=ttl)

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self._redis:
            return False
        result = await self._redis.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._redis:
            return False
        return await self._redis.exists(key) > 0

    async def set_many(
        self,
        mapping: dict[str, Any],
        ttl: int = 3600,
    ) -> None:
        """Set multiple values at once."""
        if not self._redis:
            return
        pipe = self._redis.pipeline()
        for key, value in mapping.items():
            serialized = json.dumps(value, default=str)
            pipe.set(key, serialized, ex=ttl)
        await pipe.execute()

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values at once."""
        if not self._redis or not keys:
            return {}
        values = await self._redis.mget(keys)
        result = {}
        for key, value in zip(keys, values):
            if value is not None:
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
        return result

    async def __aenter__(self) -> "AsyncRedisClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
