"""Author repository with specialized queries."""

from typing import Sequence

from sqlalchemy import select

from consearch.db.models.author import AuthorModel
from consearch.db.repositories.base import BaseRepository


class AuthorRepository(BaseRepository[AuthorModel]):
    """Repository for Author entities with specialized queries."""

    model = AuthorModel

    async def get_by_name_normalized(self, name_normalized: str) -> AuthorModel | None:
        """Find an author by normalized name."""
        stmt = select(AuthorModel).where(AuthorModel.name_normalized == name_normalized)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_orcid(self, orcid: str) -> AuthorModel | None:
        """Find an author by ORCID."""
        stmt = select(AuthorModel).where(AuthorModel.external_ids["orcid"].astext == orcid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str, *, limit: int = 10) -> Sequence[AuthorModel]:
        """Find authors by name (case-insensitive partial match)."""
        stmt = select(AuthorModel).where(AuthorModel.name.ilike(f"%{name}%")).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_or_create(
        self,
        name: str,
        name_normalized: str,
        external_ids: dict | None = None,
    ) -> tuple[AuthorModel, bool]:
        """
        Get an existing author or create a new one.

        Returns tuple of (author, created) where created is True if new.
        """
        # First try to find by normalized name
        existing = await self.get_by_name_normalized(name_normalized)
        if existing:
            return existing, False

        # Create new author
        author = AuthorModel(
            name=name,
            name_normalized=name_normalized,
            external_ids=external_ids or {},
        )
        await self.create(author)
        return author, True
