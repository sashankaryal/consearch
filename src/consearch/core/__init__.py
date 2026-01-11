"""Core types, models, and utilities."""

from .exceptions import (
    CacheError,
    ConsearchError,
    DatabaseError,
    DuplicateError,
    NotFoundError,
    RateLimitError,
    ResolutionError,
    ResolverUnavailableError,
    SearchError,
    ValidationError,
)
from .identifiers import DOI, ISBN, ArXivID, Identifier
from .models import (
    Author,
    BaseRecord,
    BookRecord,
    Identifiers,
    PaperRecord,
    SourceMetadata,
    SourceRecord,
)
from .normalization import (
    calculate_similarity,
    isbn_10_to_13,
    isbn_13_to_10,
    normalize_author_name,
    normalize_text,
    normalize_title,
)
from .types import (
    ConsumableType,
    InputType,
    ResolutionStatus,
    SourceName,
    WorkRelationType,
)

__all__ = [
    # Types
    "ConsumableType",
    "InputType",
    "ResolutionStatus",
    "SourceName",
    "WorkRelationType",
    # Identifiers
    "DOI",
    "ISBN",
    "ArXivID",
    "Identifier",
    # Models
    "Author",
    "BaseRecord",
    "BookRecord",
    "Identifiers",
    "PaperRecord",
    "SourceMetadata",
    "SourceRecord",
    # Normalization
    "calculate_similarity",
    "isbn_10_to_13",
    "isbn_13_to_10",
    "normalize_author_name",
    "normalize_text",
    "normalize_title",
    # Exceptions
    "CacheError",
    "ConsearchError",
    "DatabaseError",
    "DuplicateError",
    "NotFoundError",
    "RateLimitError",
    "ResolutionError",
    "ResolverUnavailableError",
    "SearchError",
    "ValidationError",
]
