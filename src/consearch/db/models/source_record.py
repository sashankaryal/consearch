"""SourceRecord database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consearch.core.types import SourceName
from consearch.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from consearch.db.models.work import WorkModel


class SourceRecordModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Raw data record from an external source.

    Each SourceRecord preserves the original data from a single source,
    including source-specific identifiers (like different ISBNs for
    different editions). Multiple SourceRecords can be linked to the
    same canonical Work.
    """

    __tablename__ = "source_records"

    # Source identification
    source: Mapped[SourceName] = mapped_column(
        Enum(
            SourceName,
            name="source_name",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="ID within the source system",
    )

    # Raw data preservation
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Metadata
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this data was fetched from the source",
    )
    reliability_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
        comment="Source reliability (0-1), used in merging decisions",
    )

    # Foreign key to canonical work
    work_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    work: Mapped["WorkModel"] = relationship(
        "WorkModel",
        back_populates="source_records",
    )

    __table_args__ = (
        # Each source + source_id combination must be unique
        UniqueConstraint("source", "source_id", name="uq_source_record"),
        # Reliability must be between 0 and 1
        CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="valid_reliability",
        ),
        # GIN index on raw_data for flexible queries
        Index("ix_source_records_raw_data", "raw_data", postgresql_using="gin"),
        # Composite index for source lookups
        Index("ix_source_records_source_id", "source", "source_id"),
    )

    def __repr__(self) -> str:
        return f"<SourceRecordModel(id={self.id}, source={self.source}, source_id='{self.source_id}')>"
