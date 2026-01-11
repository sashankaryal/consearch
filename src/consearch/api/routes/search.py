"""Search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from consearch.api.dependencies import SearchSvc
from consearch.api.schemas import (
    SearchBooksResponse,
    SearchPapersResponse,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "/books",
    response_model=SearchBooksResponse,
    operation_id="searchBooks",
    summary="Search books",
    description="Full-text search for books in the index.",
)
async def search_books(
    search_service: SearchSvc,
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="Results per page"),
    year_min: int | None = Query(None, ge=1000, le=2100, alias="yearMin"),
    year_max: int | None = Query(None, ge=1000, le=2100, alias="yearMax"),
    author: str | None = Query(None, max_length=200),
    language: str | None = Query(None, max_length=10),
) -> SearchBooksResponse:
    """Search for books using full-text search."""
    if search_service is None:
        raise HTTPException(
            status_code=503,
            detail="Search service not available. Meilisearch may not be configured.",
        )

    return await search_service.search_books(
        query,
        year_min=year_min,
        year_max=year_max,
        author=author,
        language=language,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/papers",
    response_model=SearchPapersResponse,
    operation_id="searchPapers",
    summary="Search papers",
    description="Full-text search for academic papers in the index.",
)
async def search_papers(
    search_service: SearchSvc,
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="Results per page"),
    year_min: int | None = Query(None, ge=1000, le=2100, alias="yearMin"),
    year_max: int | None = Query(None, ge=1000, le=2100, alias="yearMax"),
    author: str | None = Query(None, max_length=200),
    journal: str | None = Query(None, max_length=300),
) -> SearchPapersResponse:
    """Search for papers using full-text search."""
    if search_service is None:
        raise HTTPException(
            status_code=503,
            detail="Search service not available. Meilisearch may not be configured.",
        )

    return await search_service.search_papers(
        query,
        year_min=year_min,
        year_max=year_max,
        author=author,
        journal=journal,
        page=page,
        page_size=page_size,
    )
