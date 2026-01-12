"""Input type detection for identifiers and queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlparse

from consearch.core.identifiers import DOI, ISBN, ArXivID
from consearch.core.types import ConsumableType, InputType


@dataclass
class DetectionResult:
    """Result of input type detection."""

    input_type: InputType
    confidence: float  # 0.0 to 1.0
    normalized_value: str | None = None
    parsed_identifier: ISBN | DOI | ArXivID | None = None

    @property
    def consumable_type(self) -> ConsumableType | None:
        """Derive the consumable type from the detected input type.

        Returns:
            ConsumableType.BOOK for ISBN types
            ConsumableType.PAPER for arXiv/PMID types
            None for types that could be either (DOI, title, etc.)
        """
        match self.input_type:
            case InputType.ISBN_10 | InputType.ISBN_13:
                return ConsumableType.BOOK
            case InputType.ARXIV | InputType.PMID:
                return ConsumableType.PAPER
            case _:
                # DOI, URL, TITLE, CITATION, UNKNOWN could be either
                return None

    def __repr__(self) -> str:
        return (
            f"DetectionResult(type={self.input_type.value}, "
            f"confidence={self.confidence:.2f}, value={self.normalized_value!r})"
        )


class IdentifierDetector:
    """Detects the type of identifier from user input."""

    # Regex patterns for detection (looser than validation patterns)
    ISBN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:ISBN(?:-?(?:10|13))?[:\s]*)?"  # Optional ISBN/ISBN-10/ISBN-13 prefix
        r"(97[89][-\s]?)?"  # Optional 978/979 prefix
        r"([\dX][-\s]?){9,12}"  # Digits with optional separators
        r"[\dX]$",  # Final digit/X
        re.IGNORECASE,
    )

    DOI_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:https?://(?:dx\.)?doi\.org/|doi:?\s*)?"  # Optional URL/prefix
        r"(10\.\d{4,}(?:\.\d+)*/[^\s]+)",
        re.IGNORECASE,
    )

    # Valid old arXiv archive prefixes
    ARXIV_OLD_ARCHIVES: ClassVar[str] = (
        "acc-phys|adap-org|alg-geom|ao-sci|astro-ph|atom-ph|bayes-an|chao-dyn|"
        "chem-ph|cmp-lg|comp-gas|cond-mat|cs|dg-ga|funct-an|gr-qc|hep-ex|hep-lat|"
        "hep-ph|hep-th|math|math-ph|mtrl-th|nlin|nucl-ex|nucl-th|patt-sol|physics|"
        "plasm-ph|q-alg|q-bio|quant-ph|solv-int|stat|supr-con"
    )

    ARXIV_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:?\s*)?"  # Optional URL/prefix
        rf"(\d{{4}}\.\d{{4,5}}(?:v\d+)?|(?:{ARXIV_OLD_ARCHIVES})/\d{{7}})",
        re.IGNORECASE,
    )

    PMID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:PMID[:\s]*)?(\d{7,8})$",
        re.IGNORECASE,
    )

    URL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^https?://",
        re.IGNORECASE,
    )

    # Citation indicators for heuristic detection
    CITATION_INDICATORS: ClassVar[list[str]] = [
        "et al",
        "pp.",
        "vol.",
        "journal",
        "proceedings",
        "conference",
        "published",
        "press",
    ]

    def detect(self, query: str) -> DetectionResult:
        """
        Detect the input type from a query string.

        Returns the most likely input type with confidence score.
        """
        query = query.strip()

        if not query:
            return DetectionResult(
                input_type=InputType.UNKNOWN,
                confidence=0.0,
                normalized_value=None,
            )

        # Try specific identifier patterns first (highest confidence)
        if result := self._try_doi(query):
            return result

        if result := self._try_arxiv(query):
            return result

        if result := self._try_isbn(query):
            return result

        if result := self._try_pmid(query):
            return result

        # Check if it's a URL that might contain identifiers
        if result := self._try_url(query):
            return result

        # Check if it looks like a citation
        if result := self._try_citation(query):
            return result

        # Default to title search
        return DetectionResult(
            input_type=InputType.TITLE,
            confidence=0.5,
            normalized_value=query,
        )

    def detect_all(self, query: str) -> list[DetectionResult]:
        """
        Return all possible interpretations of the input, sorted by confidence.

        Useful when the input could be interpreted multiple ways.
        """
        results: list[DetectionResult] = []
        query = query.strip()

        if not query:
            return results

        # Try all patterns
        if result := self._try_doi(query):
            results.append(result)
        if result := self._try_arxiv(query):
            results.append(result)
        if result := self._try_isbn(query):
            results.append(result)
        if result := self._try_pmid(query):
            results.append(result)
        if result := self._try_url(query):
            results.append(result)
        if result := self._try_citation(query):
            results.append(result)

        # Always include title as fallback
        results.append(
            DetectionResult(
                input_type=InputType.TITLE,
                confidence=0.3,
                normalized_value=query,
            )
        )

        # Sort by confidence (highest first)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _try_doi(self, query: str) -> DetectionResult | None:
        """Attempt to parse as DOI."""
        match = self.DOI_PATTERN.search(query)
        if match:
            doi_value = match.group(1)
            try:
                parsed = DOI(value=doi_value)
                return DetectionResult(
                    input_type=InputType.DOI,
                    confidence=0.95,
                    normalized_value=parsed.value,
                    parsed_identifier=parsed,
                )
            except ValueError:
                pass
        return None

    def _try_arxiv(self, query: str) -> DetectionResult | None:
        """Attempt to parse as arXiv ID."""
        match = self.ARXIV_PATTERN.search(query)
        if match:
            arxiv_value = match.group(1)
            try:
                parsed = ArXivID.parse(arxiv_value)
                return DetectionResult(
                    input_type=InputType.ARXIV,
                    confidence=0.95,
                    normalized_value=parsed.value,
                    parsed_identifier=parsed,
                )
            except ValueError:
                pass
        return None

    def _try_isbn(self, query: str) -> DetectionResult | None:
        """Attempt to parse as ISBN."""
        if self.ISBN_PATTERN.match(query):
            # Remove ISBN prefix before extracting digits (to avoid "13" from "ISBN-13")
            isbn_part = re.sub(r"^ISBN(?:-?(?:10|13))?[:\s]*", "", query, flags=re.IGNORECASE)
            # Extract digits and X
            normalized = re.sub(r"[^\dXx]", "", isbn_part).upper()
            try:
                parsed = ISBN.parse(normalized)
                input_type = InputType.ISBN_10 if parsed.format == "isbn10" else InputType.ISBN_13
                return DetectionResult(
                    input_type=input_type,
                    confidence=0.95,
                    normalized_value=parsed.value,
                    parsed_identifier=parsed,
                )
            except ValueError:
                # Looks like ISBN but invalid checksum - still report as likely ISBN
                if len(normalized) in (10, 13):
                    return DetectionResult(
                        input_type=InputType.ISBN_13 if len(normalized) == 13 else InputType.ISBN_10,
                        confidence=0.5,
                        normalized_value=normalized,
                    )
        return None

    def _try_pmid(self, query: str) -> DetectionResult | None:
        """Attempt to parse as PubMed ID."""
        match = self.PMID_PATTERN.match(query)
        if match:
            pmid_value = match.group(1)
            return DetectionResult(
                input_type=InputType.PMID,
                confidence=0.9,
                normalized_value=pmid_value,
            )
        return None

    def _try_url(self, query: str) -> DetectionResult | None:
        """Check if query is a URL and extract identifier."""
        if not self.URL_PATTERN.match(query):
            return None

        parsed_url = urlparse(query)
        host = parsed_url.netloc.lower()
        path = parsed_url.path

        # doi.org
        if "doi.org" in host:
            doi_value = path.lstrip("/")
            try:
                parsed = DOI(value=doi_value)
                return DetectionResult(
                    input_type=InputType.DOI,
                    confidence=0.98,
                    normalized_value=parsed.value,
                    parsed_identifier=parsed,
                )
            except ValueError:
                pass

        # arxiv.org
        if "arxiv.org" in host:
            arxiv_match = re.search(r"/(?:abs|pdf)/(.+?)(?:\.pdf)?$", path)
            if arxiv_match:
                try:
                    parsed = ArXivID.parse(arxiv_match.group(1))
                    return DetectionResult(
                        input_type=InputType.ARXIV,
                        confidence=0.98,
                        normalized_value=parsed.value,
                        parsed_identifier=parsed,
                    )
                except ValueError:
                    pass

        # pubmed.gov / ncbi.nlm.nih.gov
        if "pubmed" in host or "ncbi.nlm.nih.gov" in host:
            pmid_match = re.search(r"/(\d{7,8})(?:/|$)", path)
            if pmid_match:
                return DetectionResult(
                    input_type=InputType.PMID,
                    confidence=0.95,
                    normalized_value=pmid_match.group(1),
                )

        # Generic URL - might be a reference page
        return DetectionResult(
            input_type=InputType.URL,
            confidence=0.6,
            normalized_value=query,
        )

    def _try_citation(self, query: str) -> DetectionResult | None:
        """Check if query looks like a citation string."""
        query_lower = query.lower()

        # Count citation indicators
        indicator_count = sum(
            1 for indicator in self.CITATION_INDICATORS if indicator.lower() in query_lower
        )

        # Check for year patterns like (2024) or , 2024
        has_year = bool(re.search(r"[,\(]\s*(?:19|20)\d{2}\s*[\),]?", query))

        # If multiple indicators or has year pattern and long enough, likely a citation
        if (indicator_count >= 2 or (indicator_count >= 1 and has_year)) and len(query) > 30:
            return DetectionResult(
                input_type=InputType.CITATION,
                confidence=0.7,
                normalized_value=query,
            )

        # Check for author-year pattern like "Smith et al. 2024" or "Vaswani 2017"
        if re.search(r"^[A-Z][a-z]+(?:\s+et\s+al\.?)?\s*,?\s*(?:19|20)\d{2}", query):
            return DetectionResult(
                input_type=InputType.CITATION,
                confidence=0.65,
                normalized_value=query,
            )

        return None
