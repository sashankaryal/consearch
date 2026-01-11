"""Database layer."""

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin, create_engine, create_session_factory
from .models import AuthorModel, SourceRecordModel, WorkModel
from .repositories import AuthorRepository, BaseRepository, WorkRepository
from .session import DatabaseManager

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "create_engine",
    "create_session_factory",
    # Models
    "AuthorModel",
    "SourceRecordModel",
    "WorkModel",
    # Repositories
    "AuthorRepository",
    "BaseRepository",
    "WorkRepository",
    # Session
    "DatabaseManager",
]
