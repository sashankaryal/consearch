"""Domain models for consumable records."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .types import SourceName


class Author(BaseModel):
    """Author information."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Full name")
    given_name: str | None = Field(default=None, description="First/given name")
    family_name: str | None = Field(default=None, description="Last/family name")
    orcid: str | None = Field(default=None, description="ORCID identifier")
    affiliations: list[str] = Field(default_factory=list, description="Author affiliations")


class SourceMetadata(BaseModel):
    """Metadata about the source that provided the record."""

    model_config = ConfigDict(frozen=True)

    source: SourceName = Field(..., description="Data source name")
    source_id: str = Field(..., description="ID within the source system")
    retrieved_at: datetime = Field(
        default_factory=datetime.utcnow, description="When data was fetched"
    )
    reliability_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Source reliability (0-1)"
    )
    raw_data: dict[str, Any] | None = Field(
        default=None, exclude=True, description="Original response data"
    )


class Identifiers(BaseModel):
    """All possible identifiers for a consumable work."""

    model_config = ConfigDict(populate_by_name=True)

    # Universal identifiers
    doi: str | None = Field(default=None, description="Digital Object Identifier")

    # Book identifiers
    isbn_10: str | None = Field(default=None, description="10-digit ISBN")
    isbn_13: str | None = Field(default=None, description="13-digit ISBN")

    # Academic paper identifiers
    arxiv_id: str | None = Field(default=None, description="arXiv identifier")
    pmid: str | None = Field(default=None, description="PubMed ID")
    pmcid: str | None = Field(default=None, description="PubMed Central ID")

    # Source-specific identifiers
    openlibrary_id: str | None = Field(default=None, description="Open Library work ID")
    semantic_scholar_id: str | None = Field(default=None, description="Semantic Scholar paper ID")
    isbndb_id: str | None = Field(default=None, description="ISBNdb book ID")
    crossref_id: str | None = Field(default=None, description="Crossref work ID")
    google_books_id: str | None = Field(default=None, description="Google Books volume ID")

    def has_any(self) -> bool:
        """Check if at least one identifier is present."""
        return any(getattr(self, field) is not None for field in self.model_fields)

    def to_dict(self) -> dict[str, str]:
        """Return non-None identifiers as a dictionary."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class BaseRecord(BaseModel):
    """Base class for all source records."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID | None = Field(default=None, description="Internal ID")
    title: str = Field(..., description="Title of the work")
    authors: list[Author] = Field(default_factory=list, description="List of authors")
    publication_date: date | None = Field(default=None, description="Publication date")
    year: int | None = Field(default=None, description="Publication year")
    abstract: str | None = Field(default=None, description="Abstract or description")
    url: HttpUrl | str | None = Field(default=None, description="URL to the work")
    language: str | None = Field(default=None, description="ISO 639-1 language code")

    identifiers: Identifiers = Field(default_factory=Identifiers, description="All identifiers")
    source_metadata: SourceMetadata | None = Field(default=None, description="Source information")

    # For aggregated results
    additional_sources: list[SourceMetadata] = Field(
        default_factory=list, description="Other sources that have this record"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score for merged records"
    )


class BookRecord(BaseRecord):
    """Record for a book."""

    consumable_type: Literal["book"] = "book"

    # Book-specific fields
    publisher: str | None = Field(default=None, description="Publisher name")
    edition: str | None = Field(default=None, description="Edition information")
    pages: int | None = Field(default=None, description="Number of pages")
    subjects: list[str] = Field(default_factory=list, description="Subject categories")
    cover_image_url: HttpUrl | str | None = Field(default=None, description="Cover image URL")

    @property
    def primary_isbn(self) -> str | None:
        """Return ISBN-13 if available, otherwise ISBN-10."""
        return self.identifiers.isbn_13 or self.identifiers.isbn_10


class PaperRecord(BaseRecord):
    """Record for an academic paper."""

    consumable_type: Literal["paper"] = "paper"

    # Paper-specific fields
    journal: str | None = Field(default=None, description="Journal name")
    volume: str | None = Field(default=None, description="Volume number")
    issue: str | None = Field(default=None, description="Issue number")
    pages_range: str | None = Field(default=None, description="Page range (e.g., '123-145')")
    citation_count: int | None = Field(default=None, description="Number of citations")
    reference_count: int | None = Field(default=None, description="Number of references")
    references: list[str] = Field(default_factory=list, description="DOIs of referenced papers")
    fields_of_study: list[str] = Field(default_factory=list, description="Academic fields")
    pdf_url: HttpUrl | str | None = Field(default=None, description="Direct PDF URL")


# Union type for any record
SourceRecord = BookRecord | PaperRecord
