"""Paper resolvers for fetching academic paper metadata."""

from consearch.resolution.papers.base import AbstractPaperResolver
from consearch.resolution.papers.crossref import CrossrefResolver
from consearch.resolution.papers.semantic_scholar import SemanticScholarResolver

__all__ = [
    "AbstractPaperResolver",
    "CrossrefResolver",
    "SemanticScholarResolver",
]
