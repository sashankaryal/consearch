"""Author database model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consearch.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from consearch.db.models.associations import work_author_association

if TYPE_CHECKING:
    from consearch.db.models.work import WorkModel


class AuthorModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Deduplicated author entity.

    Authors are linked to works through the work_authors association table
    which preserves author ordering.
    """

    __tablename__ = "authors"

    # Core fields
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Lowercased, accent-folded name for matching",
    )

    # External identifiers stored as JSONB for flexibility
    # Keys: orcid, semantic_scholar_id, openlibrary_id, wikidata_id, isni
    external_ids: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Relationships
    works: Mapped[list["WorkModel"]] = relationship(
        "WorkModel",
        secondary=work_author_association,
        back_populates="authors",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        # GIN index on external_ids for fast JSON queries
        Index("ix_authors_external_ids", "external_ids", postgresql_using="gin"),
        # Index for ORCID lookups (common query)
        Index(
            "ix_authors_orcid",
            external_ids["orcid"].astext,
            postgresql_where=external_ids["orcid"].isnot(None),
        ),
    )

    def __repr__(self) -> str:
        return f"<AuthorModel(id={self.id}, name='{self.name}')>"
