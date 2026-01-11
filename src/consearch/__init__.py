"""Consearch - Unified consumable (books, papers) search and resolution library."""

from consearch.client import ConsearchClient, resolve_book, resolve_paper
from consearch.core.models import Author, BookRecord, Identifiers, PaperRecord
from consearch.core.types import ConsumableType, InputType, ResolutionStatus, SourceName
from consearch.resolution.chain import AggregatedResult, FallbackConfig

__version__ = "0.1.0"
__all__ = [
    # Client
    "ConsearchClient",
    "resolve_book",
    "resolve_paper",
    # Types
    "ConsumableType",
    "InputType",
    "ResolutionStatus",
    "SourceName",
    # Models
    "Author",
    "BookRecord",
    "Identifiers",
    "PaperRecord",
    # Results
    "AggregatedResult",
    "FallbackConfig",
    # Version
    "__version__",
]
