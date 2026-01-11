"""Base repository with generic CRUD operations."""

from typing import Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from consearch.db.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic async repository with CRUD operations."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> T | None:
        """Get a single entity by ID."""
        return await self._session.get(self.model, id)

    async def get_many(self, ids: list[UUID]) -> Sequence[T]:
        """Get multiple entities by IDs."""
        if not ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[T]:
        """List entities with pagination."""
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def create_many(self, entities: list[T]) -> list[T]:
        """Create multiple entities."""
        self._session.add_all(entities)
        await self._session.flush()
        for entity in entities:
            await self._session.refresh(entity)
        return entities

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID."""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """Check if an entity exists."""
        stmt = select(self.model.id).where(self.model.id == id)
        result = await self._session.execute(stmt)
        return result.scalar() is not None
