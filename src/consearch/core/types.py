"""Core enums and type definitions."""

from enum import StrEnum


class ConsumableType(StrEnum):
    """Types of consumable content that can be searched."""

    BOOK = "book"
    PAPER = "paper"
    # Future extensions:
    # MOVIE = "movie"
    # TV_SHOW = "tv_show"
    # PODCAST = "podcast"
    # ARTICLE = "article"


class SourceName(StrEnum):
    """Known data sources for consumable records."""

    # Book sources
    ISBNDB = "isbndb"
    GOOGLE_BOOKS = "google_books"
    OPEN_LIBRARY = "open_library"

    # Paper sources
    CROSSREF = "crossref"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    PUBMED = "pubmed"


class InputType(StrEnum):
    """Types of input that can be provided for resolution."""

    # Exact identifiers
    DOI = "doi"
    ISBN_10 = "isbn_10"
    ISBN_13 = "isbn_13"
    ARXIV = "arxiv"
    PMID = "pmid"

    # URL (may contain identifiers)
    URL = "url"

    # Fuzzy searches
    TITLE = "title"
    CITATION = "citation"

    # Unknown
    UNKNOWN = "unknown"


class ResolutionStatus(StrEnum):
    """Status of a resolution attempt."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    TIMEOUT = "timeout"


class WorkRelationType(StrEnum):
    """Types of relationships between works."""

    EDITION_OF = "edition_of"  # Different edition of same work
    TRANSLATION_OF = "translation_of"  # Translation
    DERIVED_FROM = "derived_from"  # Paper -> Book adaptation
    PREPRINT_OF = "preprint_of"  # arXiv preprint -> published paper
    REPUBLISHED_AS = "republished_as"  # Same content, different publisher
    CONTAINS = "contains"  # Anthology contains chapter
    PART_OF = "part_of"  # Chapter is part of anthology
