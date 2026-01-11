"""API schema definitions."""

from consearch.api.schemas.base import (
    APIBaseSchema,
    APIError,
    ErrorDetail,
    PaginatedResponse,
)
from consearch.api.schemas.requests import (
    ResolveBookRequest,
    ResolvePaperRequest,
    ResolveRequest,
    SearchBooksRequest,
    SearchPapersRequest,
    SearchRequest,
)
from consearch.api.schemas.responses import (
    AuthorResponse,
    BookResponse,
    ConsumableResponse,
    DetectionResponse,
    HealthResponse,
    IdentifiersResponse,
    PaperResponse,
    ResolveBookResponse,
    ResolvePaperResponse,
    ResolutionSourceResult,
    SearchBookResult,
    SearchBooksResponse,
    SearchPaperResult,
    SearchPapersResponse,
    SourceMetadataResponse,
    WorkResponse,
)

__all__ = [
    # Base
    "APIBaseSchema",
    "APIError",
    "ErrorDetail",
    "PaginatedResponse",
    # Requests
    "ResolveBookRequest",
    "ResolvePaperRequest",
    "ResolveRequest",
    "SearchBooksRequest",
    "SearchPapersRequest",
    "SearchRequest",
    # Responses
    "AuthorResponse",
    "BookResponse",
    "ConsumableResponse",
    "DetectionResponse",
    "HealthResponse",
    "IdentifiersResponse",
    "PaperResponse",
    "ResolveBookResponse",
    "ResolvePaperResponse",
    "ResolutionSourceResult",
    "SearchBookResult",
    "SearchBooksResponse",
    "SearchPaperResult",
    "SearchPapersResponse",
    "SourceMetadataResponse",
    "WorkResponse",
]
