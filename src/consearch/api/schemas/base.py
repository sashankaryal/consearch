"""Base schema configuration for API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel_case(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split("_")
    return components[0] + "".join(word.capitalize() for word in components[1:])


class APIBaseSchema(BaseModel):
    """
    Base schema for all API models.

    Configured with camelCase aliases for TypeScript-friendly JSON serialization.
    """

    model_config = ConfigDict(
        alias_generator=to_camel_case,
        populate_by_name=True,
        from_attributes=True,
    )


class PaginatedResponse(APIBaseSchema):
    """Base class for paginated responses."""

    total: int
    page: int
    page_size: int
    has_more: bool


class ErrorDetail(APIBaseSchema):
    """Error detail for API responses."""

    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class APIError(APIBaseSchema):
    """Standard API error response."""

    error: ErrorDetail
