"""Abstract base class for paper resolvers."""

from __future__ import annotations

import re
from abc import abstractmethod
from typing import ClassVar

from consearch.core.identifiers import DOI, ArXivID
from consearch.core.models import PaperRecord
from consearch.core.types import InputType, ResolutionStatus
from consearch.resolution.base import AbstractResolver, ResolutionResult


class AbstractPaperResolver(AbstractResolver[PaperRecord]):
    """
    Abstract base class for paper resolvers.

    Provides DOI and arXiv handling and paper-specific functionality.
    """

    SUPPORTED_INPUT_TYPES: ClassVar[frozenset[InputType]] = frozenset(
        {
            InputType.DOI,
            InputType.ARXIV,
            InputType.TITLE,
            InputType.CITATION,
        }
    )

    def parse_doi(self, value: str) -> DOI | None:
        """Parse a DOI string, returning None if invalid."""
        try:
            return DOI(value=value)
        except ValueError:
            return None

    def parse_arxiv(self, value: str) -> ArXivID | None:
        """Parse an arXiv ID, returning None if invalid."""
        try:
            return ArXivID.parse(value)
        except ValueError:
            return None

    @abstractmethod
    async def search_by_doi(
        self,
        doi: DOI,
    ) -> ResolutionResult[PaperRecord]:
        """Search for a paper by DOI."""
        ...

    async def search_by_arxiv(
        self,
        _arxiv_id: ArXivID,
    ) -> ResolutionResult[PaperRecord]:
        """
        Search for a paper by arXiv ID.

        Default implementation returns not found.
        Override in subclasses that support arXiv search.
        """
        return ResolutionResult(
            status=ResolutionStatus.NOT_FOUND,
            source=self.source_name,
            error_message="arXiv search not supported by this resolver",
        )

    @abstractmethod
    async def search_by_title(
        self,
        title: str,
        author: str | None = None,
    ) -> ResolutionResult[PaperRecord]:
        """Search for papers by title and optional author."""
        ...

    async def search_by_citation(
        self,
        citation: str,
    ) -> ResolutionResult[PaperRecord]:
        """
        Search using a citation string.

        Default implementation attempts to extract DOI or falls back to title.
        Override for sources with citation parsing APIs.
        """
        # Try to extract DOI from citation
        doi_match = re.search(r"10\.\d{4,}/[^\s]+", citation)
        if doi_match:
            doi = self.parse_doi(doi_match.group())
            if doi:
                return await self.search_by_doi(doi)

        # Fall back to title search
        return await self.search_by_title(citation)

    async def resolve(
        self,
        query: str,
        input_type: InputType,
    ) -> ResolutionResult[PaperRecord]:
        """Route to appropriate search method based on input type."""
        if input_type == InputType.DOI:
            doi = self.parse_doi(query)
            if not doi:
                return ResolutionResult(
                    status=ResolutionStatus.ERROR,
                    source=self.source_name,
                    error_message=f"Invalid DOI: {query}",
                )
            return await self.search_by_doi(doi)

        elif input_type == InputType.ARXIV:
            arxiv = self.parse_arxiv(query)
            if not arxiv:
                return ResolutionResult(
                    status=ResolutionStatus.ERROR,
                    source=self.source_name,
                    error_message=f"Invalid arXiv ID: {query}",
                )
            return await self.search_by_arxiv(arxiv)

        elif input_type == InputType.TITLE:
            return await self.search_by_title(query)

        elif input_type == InputType.CITATION:
            return await self.search_by_citation(query)

        else:
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                source=self.source_name,
                error_message=f"Unsupported input type: {input_type}",
            )
