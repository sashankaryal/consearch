"""API route modules."""

from consearch.api.routes.health import router as health_router
from consearch.api.routes.resolve import router as resolve_router
from consearch.api.routes.search import router as search_router

__all__ = [
    "health_router",
    "resolve_router",
    "search_router",
]
