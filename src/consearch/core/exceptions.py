"""Custom exception hierarchy for consearch."""

from typing import Any


class ConsearchError(Exception):
    """Base exception for all consearch errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(ConsearchError):
    """Input validation failed."""

    pass


class ResolutionError(ConsearchError):
    """Failed to resolve identifier."""

    pass


class ResolverUnavailableError(ResolutionError):
    """External resolver API is unavailable."""

    def __init__(
        self,
        message: str,
        source: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.source = source
        self.status_code = status_code


class RateLimitError(ResolutionError):
    """Rate limit exceeded for a resolver."""

    def __init__(
        self,
        message: str,
        source: str,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.source = source
        self.retry_after = retry_after


class NotFoundError(ConsearchError):
    """Resource not found."""

    pass


class DuplicateError(ConsearchError):
    """Duplicate resource detected."""

    def __init__(
        self,
        message: str,
        existing_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.existing_id = existing_id


class DatabaseError(ConsearchError):
    """Database operation failed."""

    pass


class CacheError(ConsearchError):
    """Cache operation failed."""

    pass


class SearchError(ConsearchError):
    """Search operation failed."""

    pass
