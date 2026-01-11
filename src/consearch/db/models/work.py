"""Work database model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Enum, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consearch.core.types import ConsumableType
from consearch.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from consearch.db.models.associations import work_author_association, work_relations

if TYPE_CHECKING:
    from consearch.db.models.author import AuthorModel
    from consearch.db.models.source_record import SourceRecordModel


class WorkModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Canonical representation of a consumable work.

    A Work represents a single logical work that may have multiple
    editions, formats, or source records. Different ISBNs for the
    same book would typically be stored as separate SourceRecords
    linked to the same Work.
    """

    __tablename__ = "works"

    # Core fields
    work_type: Mapped[ConsumableType] = mapped_column(
        Enum(ConsumableType, name="consumable_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(2000), nullable=False)
    title_normalized: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        index=True,
        comment="Lowercased, punctuation-removed title for matching",
    )
    subtitle: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # All identifiers stored in JSONB for flexible querying
    # This allows adding new identifier types without schema changes
    # Keys: doi, isbn_10, isbn_13, arxiv_id, pmid, openlibrary_id,
    #       semantic_scholar_id, isbndb_id, crossref_id, google_books_id
    identifiers: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Confidence score for merged/deduped records
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
    )

    # Relationships
    authors: Mapped[list["AuthorModel"]] = relationship(
        "AuthorModel",
        secondary=work_author_association,
        back_populates="works",
        lazy="selectin",
        order_by=work_author_association.c.position,
    )

    source_records: Mapped[list["SourceRecordModel"]] = relationship(
        "SourceRecordModel",
        back_populates="work",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # Self-referential relationships for work connections
    related_to: Mapped[list["WorkModel"]] = relationship(
        "WorkModel",
        secondary=work_relations,
        primaryjoin=lambda: WorkModel.id == work_relations.c.from_work_id,
        secondaryjoin=lambda: WorkModel.id == work_relations.c.to_work_id,
        lazy="select",
    )

    related_from: Mapped[list["WorkModel"]] = relationship(
        "WorkModel",
        secondary=work_relations,
        primaryjoin=lambda: WorkModel.id == work_relations.c.to_work_id,
        secondaryjoin=lambda: WorkModel.id == work_relations.c.from_work_id,
        lazy="select",
    )

    __table_args__ = (
        # Confidence must be between 0 and 1
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="valid_confidence"),
        # GIN index on identifiers JSONB for fast lookups
        Index("ix_works_identifiers", "identifiers", postgresql_using="gin"),
        # Specific identifier indexes for common lookups
        Index(
            "ix_works_doi",
            identifiers["doi"].astext,
            postgresql_where=identifiers["doi"].isnot(None),
        ),
        Index(
            "ix_works_isbn_13",
            identifiers["isbn_13"].astext,
            postgresql_where=identifiers["isbn_13"].isnot(None),
        ),
        Index(
            "ix_works_isbn_10",
            identifiers["isbn_10"].astext,
            postgresql_where=identifiers["isbn_10"].isnot(None),
        ),
        Index(
            "ix_works_arxiv_id",
            identifiers["arxiv_id"].astext,
            postgresql_where=identifiers["arxiv_id"].isnot(None),
        ),
        Index(
            "ix_works_semantic_scholar_id",
            identifiers["semantic_scholar_id"].astext,
            postgresql_where=identifiers["semantic_scholar_id"].isnot(None),
        ),
        Index(
            "ix_works_openlibrary_id",
            identifiers["openlibrary_id"].astext,
            postgresql_where=identifiers["openlibrary_id"].isnot(None),
        ),
        # Composite index for title + year searches
        Index("ix_works_title_year", "title_normalized", "year"),
        # Full-text search index (PostgreSQL specific) - requires pg_trgm
        Index(
            "ix_works_title_fts",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<WorkModel(id={self.id}, type={self.work_type}, title='{self.title[:50]}...')>"
