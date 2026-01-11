"""Health check endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from consearch.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="getHealth",
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
)
async def health_check(request: Request) -> HealthResponse:
    """Check API health status."""
    services: dict[str, Literal["up", "down", "unknown"]] = {}
    overall_status: Literal["healthy", "degraded", "unhealthy"] = "healthy"

    # Check database
    try:
        db_factory = getattr(request.app.state, "db_session_factory", None)
        if db_factory:
            async with db_factory() as session:
                await session.execute("SELECT 1")
            services["database"] = "up"
        else:
            services["database"] = "unknown"
    except Exception:
        services["database"] = "down"
        overall_status = "unhealthy"

    # Check Redis
    try:
        cache_client = getattr(request.app.state, "cache_client", None)
        if cache_client:
            await cache_client.ping()
            services["redis"] = "up"
        else:
            services["redis"] = "unknown"
    except Exception:
        services["redis"] = "down"
        if overall_status == "healthy":
            overall_status = "degraded"

    # Check Meilisearch
    try:
        search_client = getattr(request.app.state, "search_client", None)
        if search_client:
            await search_client.health()
            services["meilisearch"] = "up"
        else:
            services["meilisearch"] = "unknown"
    except Exception:
        services["meilisearch"] = "down"
        if overall_status == "healthy":
            overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        services=services,
    )


@router.get(
    "/ready",
    operation_id="getReady",
    summary="Readiness check",
    description="Check if the API is ready to serve traffic.",
)
async def readiness_check(request: Request) -> dict[str, bool]:
    """Check if API is ready to serve traffic."""
    # Check that critical services are available
    db_factory = getattr(request.app.state, "db_session_factory", None)
    resolver_registry = getattr(request.app.state, "resolver_registry", None)

    ready = db_factory is not None and resolver_registry is not None

    return {"ready": ready}
