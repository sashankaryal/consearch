"""Initial schema for consearch.

Revision ID: 001
Revises:
Create Date: 2024-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # Create enums
    op.execute("""
        CREATE TYPE consumable_type AS ENUM ('book', 'paper');
    """)
    op.execute("""
        CREATE TYPE source_name AS ENUM (
            'isbndb', 'google_books', 'open_library',
            'crossref', 'semantic_scholar', 'arxiv', 'pubmed'
        );
    """)

    # Create authors table
    op.create_table(
        "authors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("name_normalized", sa.String(500), nullable=False),
        sa.Column(
            "external_ids",
            postgresql.JSONB,
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_authors_name_normalized", "authors", ["name_normalized"])
    op.create_index(
        "ix_authors_external_ids", "authors", ["external_ids"], postgresql_using="gin"
    )

    # Create works table
    op.create_table(
        "works",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "work_type",
            sa.Enum("book", "paper", name="consumable_type", create_type=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(2000), nullable=False),
        sa.Column("title_normalized", sa.String(2000), nullable=False),
        sa.Column("subtitle", sa.String(1000), nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column(
            "identifiers",
            postgresql.JSONB,
            server_default="{}",
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, server_default="1.0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_works_valid_confidence"
        ),
    )

    # Works indexes
    op.create_index("ix_works_work_type", "works", ["work_type"])
    op.create_index("ix_works_year", "works", ["year"])
    op.create_index("ix_works_title_normalized", "works", ["title_normalized"])
    op.create_index("ix_works_title_year", "works", ["title_normalized", "year"])
    op.create_index(
        "ix_works_identifiers", "works", ["identifiers"], postgresql_using="gin"
    )
    op.create_index(
        "ix_works_title_fts",
        "works",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    # Create source_records table
    op.create_table(
        "source_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "isbndb",
                "google_books",
                "open_library",
                "crossref",
                "semantic_scholar",
                "arxiv",
                "pubmed",
                name="source_name",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(500), nullable=False),
        sa.Column("raw_data", postgresql.JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reliability_score", sa.Float, server_default="1.0", nullable=False),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_source_record"),
        sa.CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="ck_source_records_valid_reliability",
        ),
    )
    op.create_index("ix_source_records_work_id", "source_records", ["work_id"])
    op.create_index("ix_source_records_source", "source_records", ["source"])
    op.create_index(
        "ix_source_records_source_id", "source_records", ["source", "source_id"]
    )
    op.create_index(
        "ix_source_records_raw_data",
        "source_records",
        ["raw_data"],
        postgresql_using="gin",
    )

    # Create work_authors junction table
    op.create_table(
        "work_authors",
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("authors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer, nullable=False, default=0),
        sa.UniqueConstraint("work_id", "position", name="uq_work_author_position"),
    )
    op.create_index("ix_work_authors_work_id", "work_authors", ["work_id"])
    op.create_index("ix_work_authors_author_id", "work_authors", ["author_id"])

    # Create work_relations table
    op.create_table(
        "work_relations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "from_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0", nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.UniqueConstraint(
            "from_work_id", "to_work_id", "relation_type", name="uq_work_relation"
        ),
    )
    op.create_index("ix_work_relations_from", "work_relations", ["from_work_id"])
    op.create_index("ix_work_relations_to", "work_relations", ["to_work_id"])


def downgrade() -> None:
    op.drop_table("work_relations")
    op.drop_table("work_authors")
    op.drop_table("source_records")
    op.drop_table("works")
    op.drop_table("authors")
    op.execute("DROP TYPE source_name")
    op.execute("DROP TYPE consumable_type")
