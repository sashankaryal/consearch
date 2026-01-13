"""Abstract base class for book resolvers."""

from __future__ import annotations

from abc import abstractmethod
from typing import ClassVar

from consearch.core.identifiers import ISBN
from consearch.core.models import BookRecord
from consearch.core.types import InputType, ResolutionStatus
from consearch.resolution.base import AbstractResolver, ResolutionResult


class AbstractBookResolver(AbstractResolver[BookRecord]):
    """
    Abstract base class for book resolvers.

    Provides ISBN handling and book-specific functionality.
    """

    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset(
        {
            InputType.ISBN_10,
            InputType.ISBN_13,
            InputType.TITLE,
        }
    )

    def normalize_isbn(self, isbn: str | ISBN) -> tuple[str | None, str | None]:
        """
        Normalize ISBN to both formats for maximum API compatibility.

        Returns:
            Tuple of (isbn10, isbn13), either may be None
        """
        if isinstance(isbn, str):
            try:
                isbn = ISBN.parse(isbn)
            except ValueError:
                return (None, None)

        isbn10 = isbn.to_isbn10()
        isbn13 = isbn.to_isbn13()

        return (
            isbn10.value if isbn10 else None,
            isbn13.value if isbn13 else None,
        )

    @abstractmethod
    async def search_by_isbn(
        self,
        isbn: ISBN,
    ) -> ResolutionResult[BookRecord]:
        """Search for a book by ISBN."""
        ...

    @abstractmethod
    async def search_by_title(
        self,
        title: str,
        author: str | None = None,
    ) -> ResolutionResult[BookRecord]:
        """Search for books by title and optional author."""
        ...

    async def resolve(
        self,
        query: str,
        input_type: InputType,
    ) -> ResolutionResult[BookRecord]:
        """Route to appropriate search method based on input type."""
        if input_type in (InputType.ISBN_10, InputType.ISBN_13):
            try:
                isbn = ISBN.parse(query)
                return await self.search_by_isbn(isbn)
            except ValueError as e:
                return ResolutionResult(
                    status=ResolutionStatus.ERROR,
                    source=self.source_name,
                    error_message=f"Invalid ISBN: {e}",
                )

        elif input_type == InputType.TITLE:
            return await self.search_by_title(query)

        else:
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=self.source_name,
                error_message=f"Unsupported input type: {input_type}",
            )
