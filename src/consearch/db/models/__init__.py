"""Database models."""

from .associations import work_author_association, work_relations
from .author import AuthorModel
from .source_record import SourceRecordModel
from .work import WorkModel

__all__ = [
    "AuthorModel",
    "SourceRecordModel",
    "WorkModel",
    "work_author_association",
    "work_relations",
]
