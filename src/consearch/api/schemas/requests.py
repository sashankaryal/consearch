"""Request schemas for API endpoints."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from consearch.api.schemas.base import APIBaseSchema
from consearch.core.types import ConsumableType, InputType


class ResolveRequest(APIBaseSchema):
    """Request to resolve a consumable by identifier or query."""

    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1000,
            description="The identifier or search query (ISBN, DOI, arXiv ID, title, etc.)",
        ),
    ]

    input_type: Annotated[
        InputType | None,
        Field(
            default=None,
            description="Explicit input type. If not provided, will be auto-detected.",
        ),
    ]

    include_raw_data: Annotated[
        bool,
        Field(
            default=False,
            description="Include raw API response data from sources.",
        ),
    ]


class ResolveBookRequest(ResolveRequest):
    """Request to resolve a book."""

    pass


class ResolvePaperRequest(ResolveRequest):
    """Request to resolve an academic paper."""

    pass


class SearchRequest(APIBaseSchema):
    """Request for full-text search."""

    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Search query string.",
        ),
    ]

    page: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            le=1000,
            description="Page number (1-indexed).",
        ),
    ]

    page_size: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Number of results per page.",
        ),
    ]


class SearchBooksRequest(SearchRequest):
    """Request to search for books."""

    year_min: Annotated[
        int | None,
        Field(
            default=None,
            ge=1000,
            le=2100,
            description="Minimum publication year filter.",
        ),
    ]

    year_max: Annotated[
        int | None,
        Field(
            default=None,
            ge=1000,
            le=2100,
            description="Maximum publication year filter.",
        ),
    ]

    author: Annotated[
        str | None,
        Field(
            default=None,
            max_length=200,
            description="Filter by author name.",
        ),
    ]


class SearchPapersRequest(SearchRequest):
    """Request to search for papers."""

    year_min: Annotated[
        int | None,
        Field(
            default=None,
            ge=1000,
            le=2100,
            description="Minimum publication year filter.",
        ),
    ]

    year_max: Annotated[
        int | None,
        Field(
            default=None,
            ge=1000,
            le=2100,
            description="Maximum publication year filter.",
        ),
    ]

    author: Annotated[
        str | None,
        Field(
            default=None,
            max_length=200,
            description="Filter by author name.",
        ),
    ]

    journal: Annotated[
        str | None,
        Field(
            default=None,
            max_length=300,
            description="Filter by journal name.",
        ),
    ]
