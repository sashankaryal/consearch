"""Response schemas for API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from consearch.api.schemas.base import APIBaseSchema, PaginatedResponse
from consearch.core.types import ConsumableType, InputType, ResolutionStatus, SourceName


# Author schemas
class AuthorResponse(APIBaseSchema):
    """Author information."""

    name: str
    given_name: str | None = None
    family_name: str | None = None
    orcid: str | None = None
    affiliations: list[str] = Field(default_factory=list)


# Identifier schemas
class IdentifiersResponse(APIBaseSchema):
    """Standard identifiers for a work."""

    isbn_10: str | None = None
    isbn_13: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    openlibrary_id: str | None = None
    google_books_id: str | None = None
    crossref_id: str | None = None
    semantic_scholar_id: str | None = None


# Source metadata
class SourceMetadataResponse(APIBaseSchema):
    """Metadata about the data source."""

    source: SourceName
    source_id: str
    retrieved_at: datetime
    reliability_score: float
    raw_data: dict | None = None


# Detection response
class DetectionResponse(APIBaseSchema):
    """Response for input type detection."""

    detected_type: InputType
    confidence: float
    normalized_value: str | None = None
    consumable_type: ConsumableType | None = None


# Book response
class BookResponse(APIBaseSchema):
    """Book record response."""

    type: Literal["book"] = "book"
    title: str
    authors: list[AuthorResponse]
    year: int | None = None
    identifiers: IdentifiersResponse
    publisher: str | None = None
    pages: int | None = None
    subjects: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    abstract: str | None = None
    edition: str | None = None
    language: str | None = None
    url: str | None = None
    source_metadata: SourceMetadataResponse | None = None


# Paper response
class PaperResponse(APIBaseSchema):
    """Academic paper record response."""

    type: Literal["paper"] = "paper"
    title: str
    authors: list[AuthorResponse]
    year: int | None = None
    publication_date: date | None = None
    identifiers: IdentifiersResponse
    abstract: str | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages_range: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    source_metadata: SourceMetadataResponse | None = None


# Discriminated union for polymorphic responses
ConsumableResponse = Annotated[
    BookResponse | PaperResponse,
    Field(discriminator="type"),
]


# Resolution result
class ResolutionSourceResult(APIBaseSchema):
    """Result from a single source."""

    source: SourceName
    status: ResolutionStatus
    duration_ms: float | None = None
    error_message: str | None = None


class ResolveBookResponse(APIBaseSchema):
    """Response for book resolution."""

    detected_input_type: InputType
    status: ResolutionStatus
    records: list[BookResponse]
    sources_tried: list[ResolutionSourceResult]
    total_duration_ms: float


class ResolvePaperResponse(APIBaseSchema):
    """Response for paper resolution."""

    detected_input_type: InputType
    status: ResolutionStatus
    records: list[PaperResponse]
    sources_tried: list[ResolutionSourceResult]
    total_duration_ms: float


# Search responses
class SearchBookResult(APIBaseSchema):
    """Book search result with relevance score."""

    id: UUID
    score: float
    book: BookResponse


class SearchPaperResult(APIBaseSchema):
    """Paper search result with relevance score."""

    id: UUID
    score: float
    paper: PaperResponse


class SearchBooksResponse(PaginatedResponse):
    """Paginated book search results."""

    results: list[SearchBookResult]


class SearchPapersResponse(PaginatedResponse):
    """Paginated paper search results."""

    results: list[SearchPaperResult]


# Health check
class HealthResponse(APIBaseSchema):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    services: dict[str, Literal["up", "down", "unknown"]]


# Work response (for stored works)
class WorkResponse(APIBaseSchema):
    """Stored work response."""

    id: UUID
    work_type: ConsumableType
    title: str
    authors: list[AuthorResponse]
    year: int | None = None
    identifiers: IdentifiersResponse
    created_at: datetime
    updated_at: datetime
