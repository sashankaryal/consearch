"""Work repository with specialized queries."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from consearch.core.types import ConsumableType
from consearch.db.models.work import WorkModel
from consearch.db.repositories.base import BaseRepository


class WorkRepository(BaseRepository[WorkModel]):
    """Repository for Work entities with specialized queries."""

    model = WorkModel

    async def get_by_doi(self, doi: str) -> WorkModel | None:
        """Find a work by DOI."""
        stmt = select(WorkModel).where(WorkModel.identifiers["doi"].astext == doi.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_isbn(self, isbn: str) -> WorkModel | None:
        """Find a work by ISBN (checks both ISBN-10 and ISBN-13)."""
        # Normalize ISBN
        isbn = isbn.replace("-", "").replace(" ", "").upper()

        if len(isbn) == 13:
            stmt = select(WorkModel).where(WorkModel.identifiers["isbn_13"].astext == isbn)
        else:
            stmt = select(WorkModel).where(WorkModel.identifiers["isbn_10"].astext == isbn)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_arxiv_id(self, arxiv_id: str) -> WorkModel | None:
        """Find a work by arXiv ID."""
        stmt = select(WorkModel).where(WorkModel.identifiers["arxiv_id"].astext == arxiv_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(
        self, identifier_type: str, identifier_value: str
    ) -> WorkModel | None:
        """Find a work by any identifier type."""
        stmt = select(WorkModel).where(
            WorkModel.identifiers[identifier_type].astext == identifier_value
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_title(
        self,
        title: str,
        *,
        work_type: ConsumableType | None = None,
        limit: int = 10,
    ) -> Sequence[WorkModel]:
        """Find works by title (case-insensitive)."""
        stmt = select(WorkModel).where(WorkModel.title.ilike(f"%{title}%")).limit(limit)

        if work_type:
            stmt = stmt.where(WorkModel.work_type == work_type)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def find_by_title_and_year(
        self,
        title_normalized: str,
        year: int | None,
        *,
        work_type: ConsumableType | None = None,
    ) -> Sequence[WorkModel]:
        """Find works by normalized title and optional year."""
        stmt = select(WorkModel).where(WorkModel.title_normalized == title_normalized)

        if year is not None:
            stmt = stmt.where(WorkModel.year == year)

        if work_type:
            stmt = stmt.where(WorkModel.work_type == work_type)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_with_relations(self, id) -> WorkModel | None:
        """Get a work with all its relationships loaded."""
        stmt = (
            select(WorkModel)
            .where(WorkModel.id == id)
            .options(
                selectinload(WorkModel.authors),
                selectinload(WorkModel.source_records),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(
        self,
        work_type: ConsumableType,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[WorkModel]:
        """List works by type with pagination."""
        stmt = select(WorkModel).where(WorkModel.work_type == work_type).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()
