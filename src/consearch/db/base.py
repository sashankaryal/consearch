"""SQLAlchemy base configuration and mixins."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import MetaData, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for constraints (important for Alembic migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=convention)

    # Type annotation map for common types
    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class UUIDPrimaryKeyMixin:
    """Mixin providing UUID primary key."""

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Mixin providing created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    return create_async_engine(
        database_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Create an async session factory."""
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
