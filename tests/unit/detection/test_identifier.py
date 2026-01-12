"""Tests for input type detection."""

from __future__ import annotations

import pytest

from consearch.core.identifiers import DOI, ISBN, ArXivID
from consearch.core.types import InputType
from consearch.detection.identifier import DetectionResult, IdentifierDetector


@pytest.fixture
def detector() -> IdentifierDetector:
    """Create an IdentifierDetector instance."""
    return IdentifierDetector()


# ============================================================================
# ISBN Detection Tests
# ============================================================================


class TestISBNDetection:
    """Tests for ISBN detection."""

    @pytest.mark.parametrize(
        "query,expected_type",
        [
            ("0134093410", InputType.ISBN_10),
            ("155860832X", InputType.ISBN_10),
            ("0-13-409341-0", InputType.ISBN_10),
            ("ISBN: 0134093410", InputType.ISBN_10),
        ],
    )
    def test_isbn10_detection(self, detector: IdentifierDetector, query: str, expected_type: InputType):
        """ISBN-10 formats should be detected correctly."""
        result = detector.detect(query)
        assert result.input_type == expected_type
        assert result.confidence >= 0.9
        assert result.parsed_identifier is not None
        assert isinstance(result.parsed_identifier, ISBN)

    @pytest.mark.parametrize(
        "query,expected_type",
        [
            ("9780134093413", InputType.ISBN_13),
            ("978-0-13-409341-3", InputType.ISBN_13),
            ("ISBN: 9780134093413", InputType.ISBN_13),
            ("ISBN-13: 9780134093413", InputType.ISBN_13),
        ],
    )
    def test_isbn13_detection(self, detector: IdentifierDetector, query: str, expected_type: InputType):
        """ISBN-13 formats should be detected correctly."""
        result = detector.detect(query)
        assert result.input_type == expected_type
        assert result.confidence >= 0.9
        assert result.parsed_identifier is not None
        assert isinstance(result.parsed_identifier, ISBN)

    def test_isbn_invalid_checksum_low_confidence(self, detector: IdentifierDetector):
        """ISBN with invalid checksum should have lower confidence."""
        result = detector.detect("0134093411")  # Invalid checksum
        # Should still detect as ISBN but with lower confidence
        assert result.input_type in (InputType.ISBN_10, InputType.ISBN_13)
        assert result.confidence < 0.9
        assert result.parsed_identifier is None


# ============================================================================
# DOI Detection Tests
# ============================================================================


class TestDOIDetection:
    """Tests for DOI detection."""

    @pytest.mark.parametrize(
        "query",
        [
            "10.1038/nature12373",
            "10.1000/xyz123",
            "10.1234/5678/90",
            "doi:10.1038/nature12373",
            "DOI: 10.1038/nature12373",
        ],
    )
    def test_doi_detection(self, detector: IdentifierDetector, query: str):
        """DOI formats should be detected correctly."""
        result = detector.detect(query)
        assert result.input_type == InputType.DOI
        assert result.confidence >= 0.9
        assert result.parsed_identifier is not None
        assert isinstance(result.parsed_identifier, DOI)

    @pytest.mark.parametrize(
        "query",
        [
            "https://doi.org/10.1038/nature12373",
            "http://dx.doi.org/10.1038/nature12373",
        ],
    )
    def test_doi_url_detection(self, detector: IdentifierDetector, query: str):
        """DOI URLs should be detected and DOI extracted."""
        result = detector.detect(query)
        assert result.input_type == InputType.DOI
        assert result.confidence >= 0.95
        assert result.normalized_value == "10.1038/nature12373"


# ============================================================================
# ArXiv ID Detection Tests
# ============================================================================


class TestArXivDetection:
    """Tests for arXiv ID detection."""

    @pytest.mark.parametrize(
        "query",
        [
            "1234.56789",
            "1234.5678",
            "1234.56789v2",
            "arxiv:1234.56789",
            "arXiv:1234.56789",
        ],
    )
    def test_arxiv_new_format_detection(self, detector: IdentifierDetector, query: str):
        """New arXiv ID formats should be detected."""
        result = detector.detect(query)
        assert result.input_type == InputType.ARXIV
        assert result.confidence >= 0.9
        assert result.parsed_identifier is not None
        assert isinstance(result.parsed_identifier, ArXivID)

    @pytest.mark.parametrize(
        "query",
        [
            "hep-th/9901001",
            "astro-ph/0001001",
            "math/0612345",
        ],
    )
    def test_arxiv_old_format_detection(self, detector: IdentifierDetector, query: str):
        """Old arXiv ID formats should be detected."""
        result = detector.detect(query)
        assert result.input_type == InputType.ARXIV
        assert result.confidence >= 0.9

    @pytest.mark.parametrize(
        "query",
        [
            "https://arxiv.org/abs/1234.56789",
            "http://arxiv.org/pdf/1234.56789.pdf",
            "https://arxiv.org/abs/hep-th/9901001",
        ],
    )
    def test_arxiv_url_detection(self, detector: IdentifierDetector, query: str):
        """ArXiv URLs should be detected and ID extracted."""
        result = detector.detect(query)
        assert result.input_type == InputType.ARXIV
        assert result.confidence >= 0.95


# ============================================================================
# PMID Detection Tests
# ============================================================================


class TestPMIDDetection:
    """Tests for PubMed ID detection."""

    @pytest.mark.parametrize(
        "query",
        [
            "12345678",
            "PMID:12345678",
            "PMID: 12345678",
            "pmid12345678",
        ],
    )
    def test_pmid_detection(self, detector: IdentifierDetector, query: str):
        """PMID formats should be detected."""
        result = detector.detect(query)
        assert result.input_type == InputType.PMID
        assert result.confidence >= 0.9
        assert result.normalized_value == "12345678"

    @pytest.mark.parametrize(
        "query",
        [
            "https://pubmed.ncbi.nlm.nih.gov/12345678",
            "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        ],
    )
    def test_pmid_url_detection(self, detector: IdentifierDetector, query: str):
        """PubMed URLs should be detected and PMID extracted."""
        result = detector.detect(query)
        assert result.input_type == InputType.PMID
        assert result.normalized_value == "12345678"


# ============================================================================
# URL Detection Tests
# ============================================================================


class TestURLDetection:
    """Tests for URL detection."""

    def test_generic_url(self, detector: IdentifierDetector):
        """Generic URLs should be detected."""
        result = detector.detect("https://example.com/some/page")
        assert result.input_type == InputType.URL
        assert result.confidence >= 0.5


# ============================================================================
# Citation Detection Tests
# ============================================================================


class TestCitationDetection:
    """Tests for citation string detection."""

    @pytest.mark.parametrize(
        "query",
        [
            "Smith et al., Nature, 2023, vol. 600, pp. 123-130",
            "J. Doe, Journal of Science, published 2022",
            "Vaswani et al., Attention Is All You Need, Proceedings of NeurIPS 2017",
        ],
    )
    def test_citation_detection(self, detector: IdentifierDetector, query: str):
        """Citation strings should be detected."""
        result = detector.detect(query)
        assert result.input_type == InputType.CITATION
        assert result.confidence >= 0.6

    @pytest.mark.parametrize(
        "query",
        [
            "Smith 2024",
            "Smith et al. 2024",
            "Vaswani 2017",
        ],
    )
    def test_author_year_citation(self, detector: IdentifierDetector, query: str):
        """Author-year citations should be detected."""
        result = detector.detect(query)
        assert result.input_type == InputType.CITATION
        assert result.confidence >= 0.6


# ============================================================================
# Title/Fallback Detection Tests
# ============================================================================


class TestTitleDetection:
    """Tests for title (fallback) detection."""

    @pytest.mark.parametrize(
        "query",
        [
            "Clean Code",
            "Introduction to Algorithms",
            "Machine Learning: A Probabilistic Perspective",
        ],
    )
    def test_title_fallback(self, detector: IdentifierDetector, query: str):
        """Plain text should fall back to title detection."""
        result = detector.detect(query)
        assert result.input_type == InputType.TITLE
        assert result.normalized_value == query

    def test_empty_query(self, detector: IdentifierDetector):
        """Empty query should return UNKNOWN."""
        result = detector.detect("")
        assert result.input_type == InputType.UNKNOWN
        assert result.confidence == 0.0

    def test_whitespace_only_query(self, detector: IdentifierDetector):
        """Whitespace-only query should return UNKNOWN."""
        result = detector.detect("   ")
        assert result.input_type == InputType.UNKNOWN
        assert result.confidence == 0.0


# ============================================================================
# detect_all Tests
# ============================================================================


class TestDetectAll:
    """Tests for detect_all method."""

    def test_detect_all_returns_multiple(self, detector: IdentifierDetector):
        """detect_all should return multiple interpretations."""
        # This could be interpreted as multiple things
        results = detector.detect_all("10.1038/nature12373")
        assert len(results) >= 1
        # Should be sorted by confidence
        assert results[0].confidence >= results[-1].confidence

    def test_detect_all_includes_title_fallback(self, detector: IdentifierDetector):
        """detect_all should always include title as fallback."""
        results = detector.detect_all("some random text")
        types = [r.input_type for r in results]
        assert InputType.TITLE in types

    def test_detect_all_empty_returns_empty(self, detector: IdentifierDetector):
        """detect_all with empty query should return empty list."""
        results = detector.detect_all("")
        assert results == []


# ============================================================================
# DetectionResult Tests
# ============================================================================


class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_repr(self):
        """DetectionResult repr should be informative."""
        result = DetectionResult(
            input_type=InputType.DOI,
            confidence=0.95,
            normalized_value="10.1038/nature12373",
        )
        repr_str = repr(result)
        assert "DOI" in repr_str or "doi" in repr_str
        assert "0.95" in repr_str
        assert "10.1038" in repr_str
