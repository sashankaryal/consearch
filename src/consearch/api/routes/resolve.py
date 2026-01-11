"""Resolution endpoints."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from consearch.api.dependencies import ResolveService, Settings
from consearch.api.schemas import (
    AuthorResponse,
    BookResponse,
    IdentifiersResponse,
    PaperResponse,
    ResolveBookRequest,
    ResolveBookResponse,
    ResolvePaperRequest,
    ResolvePaperResponse,
    ResolutionSourceResult,
    SourceMetadataResponse,
)
from consearch.core.models import BookRecord, PaperRecord
from consearch.core.types import ConsumableType, InputType, ResolutionStatus
from consearch.detection.identifier import IdentifierDetector

if TYPE_CHECKING:
    from consearch.resolution.chain import AggregatedResult

router = APIRouter(prefix="/resolve", tags=["resolve"])


def _convert_book_to_response(record: BookRecord, include_raw: bool = False) -> BookResponse:
    """Convert domain BookRecord to API response."""
    source_meta = None
    if record.source_metadata:
        source_meta = SourceMetadataResponse(
            source=record.source_metadata.source,
            source_id=record.source_metadata.source_id,
            retrieved_at=record.source_metadata.retrieved_at,
            reliability_score=record.source_metadata.reliability_score,
            raw_data=record.source_metadata.raw_data if include_raw else None,
        )

    return BookResponse(
        title=record.title,
        authors=[
            AuthorResponse(
                name=a.name,
                given_name=a.given_name,
                family_name=a.family_name,
                orcid=a.orcid,
                affiliations=a.affiliations,
            )
            for a in record.authors
        ],
        year=record.year,
        identifiers=IdentifiersResponse(
            isbn_10=record.identifiers.isbn_10,
            isbn_13=record.identifiers.isbn_13,
            doi=record.identifiers.doi,
            openlibrary_id=record.identifiers.openlibrary_id,
            google_books_id=record.identifiers.google_books_id,
        ),
        publisher=record.publisher,
        pages=record.pages,
        subjects=record.subjects,
        cover_image_url=record.cover_image_url,
        abstract=record.abstract,
        edition=record.edition,
        language=record.language,
        url=record.url,
        source_metadata=source_meta,
    )


def _convert_paper_to_response(record: PaperRecord, include_raw: bool = False) -> PaperResponse:
    """Convert domain PaperRecord to API response."""
    source_meta = None
    if record.source_metadata:
        source_meta = SourceMetadataResponse(
            source=record.source_metadata.source,
            source_id=record.source_metadata.source_id,
            retrieved_at=record.source_metadata.retrieved_at,
            reliability_score=record.source_metadata.reliability_score,
            raw_data=record.source_metadata.raw_data if include_raw else None,
        )

    return PaperResponse(
        title=record.title,
        authors=[
            AuthorResponse(
                name=a.name,
                given_name=a.given_name,
                family_name=a.family_name,
                orcid=a.orcid,
                affiliations=a.affiliations,
            )
            for a in record.authors
        ],
        year=record.year,
        publication_date=record.publication_date,
        identifiers=IdentifiersResponse(
            doi=record.identifiers.doi,
            arxiv_id=record.identifiers.arxiv_id,
            pmid=record.identifiers.pmid,
            crossref_id=record.identifiers.crossref_id,
            semantic_scholar_id=record.identifiers.semantic_scholar_id,
        ),
        abstract=record.abstract,
        journal=record.journal,
        volume=record.volume,
        issue=record.issue,
        pages_range=record.pages_range,
        citation_count=record.citation_count,
        reference_count=record.reference_count,
        url=record.url,
        pdf_url=record.pdf_url,
        source_metadata=source_meta,
    )


@router.post(
    "/book",
    response_model=ResolveBookResponse,
    operation_id="resolveBook",
    summary="Resolve book metadata",
    description="Resolve book metadata by ISBN, title, or other identifiers.",
)
async def resolve_book(
    request: ResolveBookRequest,
    resolution_service: ResolveService,
    settings: Settings,
) -> ResolveBookResponse:
    """Resolve book metadata from external sources with caching and persistence."""
    start_time = time.monotonic()

    # Detect input type if not provided
    detector = IdentifierDetector()
    if request.input_type:
        input_type = request.input_type
    else:
        detection = detector.detect(request.query)
        input_type = detection.input_type

        # Validate it's a book-compatible input type
        if detection.consumable_type and detection.consumable_type != ConsumableType.BOOK:
            raise HTTPException(
                status_code=400,
                detail=f"Input type {input_type} is not valid for book resolution",
            )

    # Use resolution service (handles cache, DB, resolve, persist, index)
    result = await resolution_service.resolve_book(request.query, input_type)

    total_duration = (time.monotonic() - start_time) * 1000

    # Build response
    return ResolveBookResponse(
        detected_input_type=input_type,
        status=ResolutionStatus.SUCCESS if result.success else ResolutionStatus.NOT_FOUND,
        records=[
            _convert_book_to_response(r, request.include_raw_data)
            for r in result.all_records
        ],
        sources_tried=[
            ResolutionSourceResult(
                source=res.source,
                status=res.status,
                duration_ms=res.duration_ms,
                error_message=res.error_message,
            )
            for res in ([result.primary_result] if result.primary_result else [])
            + result.fallback_results
        ],
        total_duration_ms=total_duration,
    )


@router.post(
    "/paper",
    response_model=ResolvePaperResponse,
    operation_id="resolvePaper",
    summary="Resolve paper metadata",
    description="Resolve academic paper metadata by DOI, arXiv ID, title, or citation.",
)
async def resolve_paper(
    request: ResolvePaperRequest,
    resolution_service: ResolveService,
    settings: Settings,
) -> ResolvePaperResponse:
    """Resolve paper metadata from external sources with caching and persistence."""
    start_time = time.monotonic()

    # Detect input type if not provided
    detector = IdentifierDetector()
    if request.input_type:
        input_type = request.input_type
    else:
        detection = detector.detect(request.query)
        input_type = detection.input_type

        # Validate it's a paper-compatible input type
        if detection.consumable_type and detection.consumable_type != ConsumableType.PAPER:
            raise HTTPException(
                status_code=400,
                detail=f"Input type {input_type} is not valid for paper resolution",
            )

    # Use resolution service (handles cache, DB, resolve, persist, index)
    result = await resolution_service.resolve_paper(request.query, input_type)

    total_duration = (time.monotonic() - start_time) * 1000

    # Build response
    return ResolvePaperResponse(
        detected_input_type=input_type,
        status=ResolutionStatus.SUCCESS if result.success else ResolutionStatus.NOT_FOUND,
        records=[
            _convert_paper_to_response(r, request.include_raw_data)
            for r in result.all_records
        ],
        sources_tried=[
            ResolutionSourceResult(
                source=res.source,
                status=res.status,
                duration_ms=res.duration_ms,
                error_message=res.error_message,
            )
            for res in ([result.primary_result] if result.primary_result else [])
            + result.fallback_results
        ],
        total_duration_ms=total_duration,
    )


@router.post(
    "/detect",
    response_model=dict,
    operation_id="detectInputType",
    summary="Detect input type",
    description="Detect the type of a query string (ISBN, DOI, title, etc.).",
)
async def detect_input_type(query: str) -> dict:
    """Detect the input type of a query string."""
    detector = IdentifierDetector()
    result = detector.detect(query)

    return {
        "detectedType": result.input_type.value,
        "confidence": result.confidence,
        "normalizedValue": result.normalized_value,
        "consumableType": result.consumable_type.value if result.consumable_type else None,
    }
