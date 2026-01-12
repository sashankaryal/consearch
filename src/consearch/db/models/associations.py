"""Association/junction tables for many-to-many relationships."""

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import text

from consearch.db.base import Base

# Work-Author many-to-many with ordering
work_author_association = Table(
    "work_authors",
    Base.metadata,
    Column(
        "work_id",
        PG_UUID(as_uuid=True),
        ForeignKey("works.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "author_id",
        PG_UUID(as_uuid=True),
        ForeignKey("authors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("position", Integer, nullable=False, default=0),  # Author order
    UniqueConstraint("work_id", "position", name="uq_work_author_position"),
)

# Work-to-Work relationships (self-referential many-to-many)
work_relations = Table(
    "work_relations",
    Base.metadata,
    Column(
        "id",
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "from_work_id",
        PG_UUID(as_uuid=True),
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "to_work_id",
        PG_UUID(as_uuid=True),
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("relation_type", String(50), nullable=False),  # WorkRelationType enum value
    Column("confidence", Float, nullable=False, default=1.0),
    Column("metadata", JSONB, nullable=True),  # Extra info about the relationship
    UniqueConstraint("from_work_id", "to_work_id", "relation_type", name="uq_work_relation"),
)
