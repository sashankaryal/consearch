"""Tests for identifier value objects: ISBN, DOI, ArXivID."""

from __future__ import annotations

import pytest

from consearch.core.identifiers import DOI, ISBN, ArXivID


# ============================================================================
# ISBN Tests
# ============================================================================


class TestISBN:
    """Tests for ISBN validation and conversion."""

    # Valid ISBN-10 examples
    @pytest.mark.parametrize(
        "isbn,expected",
        [
            ("0134093410", "0134093410"),  # Clean Code
            ("0-13-409341-0", "0134093410"),  # With hyphens
            ("0 13 409341 0", "0134093410"),  # With spaces
            ("155860832X", "155860832X"),  # X check digit
            ("155860832x", "155860832X"),  # Lowercase x
            ("0-306-40615-2", "0306406152"),  # Another valid ISBN
        ],
    )
    def test_isbn10_valid(self, isbn: str, expected: str):
        """Valid ISBN-10 should be parsed and normalized."""
        parsed = ISBN.parse(isbn)
        assert parsed.value == expected
        assert parsed.format == "isbn10"

    @pytest.mark.parametrize(
        "isbn",
        [
            "0134093411",  # Invalid checksum
            "013409341",  # Too short (9 digits)
            "01340934100",  # Too long (11 digits)
            "ABCDEFGHIJ",  # Non-numeric
            "0134093X10",  # X in wrong position
        ],
    )
    def test_isbn10_invalid(self, isbn: str):
        """Invalid ISBN-10 should raise ValueError."""
        with pytest.raises(ValueError):
            ISBN.parse(isbn)

    # Valid ISBN-13 examples
    @pytest.mark.parametrize(
        "isbn,expected",
        [
            ("9780134093413", "9780134093413"),  # Clean Code
            ("978-0-13-409341-3", "9780134093413"),  # With hyphens
            ("978 0 13 409341 3", "9780134093413"),  # With spaces
            ("9790001000000", "9790001000000"),  # 979 prefix
            ("978-3-16-148410-0", "9783161484100"),  # Another valid
        ],
    )
    def test_isbn13_valid(self, isbn: str, expected: str):
        """Valid ISBN-13 should be parsed and normalized."""
        parsed = ISBN.parse(isbn)
        assert parsed.value == expected
        assert parsed.format == "isbn13"

    @pytest.mark.parametrize(
        "isbn",
        [
            "9780134093412",  # Invalid checksum
            "978013409341",  # Too short (12 digits)
            "97801340934133",  # Too long (14 digits)
            "9770134093413",  # Invalid prefix (977)
            "978ABCDEFGHIJ",  # Non-numeric
        ],
    )
    def test_isbn13_invalid(self, isbn: str):
        """Invalid ISBN-13 should raise ValueError."""
        with pytest.raises(ValueError):
            ISBN.parse(isbn)

    # Conversion tests
    def test_isbn10_to_isbn13(self):
        """ISBN-10 to ISBN-13 conversion should work correctly."""
        isbn10 = ISBN.parse("0134093410")
        isbn13 = isbn10.to_isbn13()
        assert isbn13.value == "9780134093413"
        assert isbn13.format == "isbn13"

    def test_isbn13_to_isbn13(self):
        """Converting ISBN-13 to ISBN-13 should return same value."""
        isbn13 = ISBN.parse("9780134093413")
        result = isbn13.to_isbn13()
        assert result.value == isbn13.value

    def test_isbn13_to_isbn10(self):
        """ISBN-13 to ISBN-10 conversion should work for 978 prefix."""
        isbn13 = ISBN.parse("9780134093413")
        isbn10 = isbn13.to_isbn10()
        assert isbn10 is not None
        assert isbn10.value == "0134093410"
        assert isbn10.format == "isbn10"

    def test_isbn13_979_to_isbn10_fails(self):
        """ISBN-13 with 979 prefix cannot be converted to ISBN-10."""
        isbn13 = ISBN.parse("9790001000000")
        isbn10 = isbn13.to_isbn10()
        assert isbn10 is None

    def test_isbn_with_x_check_digit_conversion(self):
        """ISBN-10 with X check digit should convert correctly."""
        isbn10 = ISBN.parse("155860832X")
        isbn13 = isbn10.to_isbn13()
        # Convert back and verify X is preserved
        back = isbn13.to_isbn10()
        assert back is not None
        assert back.value == "155860832X"

    # Hash and equality tests
    def test_isbn10_and_isbn13_same_hash(self):
        """ISBN-10 and equivalent ISBN-13 should hash the same."""
        isbn10 = ISBN.parse("0134093410")
        isbn13 = ISBN.parse("9780134093413")
        assert hash(isbn10) == hash(isbn13)

    def test_isbn_string_representation(self):
        """ISBN __str__ should return normalized value."""
        isbn = ISBN.parse("978-0-13-409341-3")
        assert str(isbn) == "9780134093413"


# ============================================================================
# DOI Tests
# ============================================================================


class TestDOI:
    """Tests for DOI validation and normalization."""

    @pytest.mark.parametrize(
        "doi,expected",
        [
            ("10.1038/nature12373", "10.1038/nature12373"),
            ("10.1000/xyz123", "10.1000/xyz123"),
            ("10.1234/5678/90", "10.1234/5678/90"),  # With multiple slashes
            ("10.12345/example.test-v2", "10.12345/example.test-v2"),
        ],
    )
    def test_doi_valid(self, doi: str, expected: str):
        """Valid DOI should be parsed correctly."""
        parsed = DOI(value=doi)
        assert parsed.value == expected

    @pytest.mark.parametrize(
        "doi,expected",
        [
            ("https://doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("http://doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("https://dx.doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("http://dx.doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("doi:10.1038/nature12373", "10.1038/nature12373"),
            ("DOI: 10.1038/nature12373", "10.1038/nature12373"),
        ],
    )
    def test_doi_url_extraction(self, doi: str, expected: str):
        """DOI should be extracted from URLs and prefixes."""
        parsed = DOI(value=doi)
        assert parsed.value == expected

    @pytest.mark.parametrize(
        "doi",
        [
            "not-a-doi",
            "11.1038/nature12373",  # Wrong prefix
            "10.123/nature",  # Too short registrant
            "10.1038 nature12373",  # Space instead of slash
            "",
        ],
    )
    def test_doi_invalid(self, doi: str):
        """Invalid DOI should raise ValueError."""
        with pytest.raises(ValueError):
            DOI(value=doi)

    def test_doi_url_property(self):
        """DOI url property should return doi.org URL."""
        doi = DOI(value="10.1038/nature12373")
        assert doi.url == "https://doi.org/10.1038/nature12373"

    def test_doi_string_representation(self):
        """DOI __str__ should return normalized value."""
        doi = DOI(value="https://doi.org/10.1038/nature12373")
        assert str(doi) == "10.1038/nature12373"

    def test_doi_hash(self):
        """DOI hash should be case-insensitive."""
        doi1 = DOI(value="10.1038/Nature12373")
        doi2 = DOI(value="10.1038/nature12373")
        assert hash(doi1) == hash(doi2)


# ============================================================================
# ArXiv ID Tests
# ============================================================================


class TestArXivID:
    """Tests for arXiv ID validation and normalization."""

    @pytest.mark.parametrize(
        "arxiv,expected,expected_format",
        [
            ("1234.56789", "1234.56789", "new"),
            ("1234.5678", "1234.5678", "new"),
            ("1234.56789v2", "1234.56789v2", "new"),
            ("1234.56789v10", "1234.56789v10", "new"),
        ],
    )
    def test_arxiv_new_format_valid(self, arxiv: str, expected: str, expected_format: str):
        """Valid new arXiv IDs should be parsed."""
        parsed = ArXivID.parse(arxiv)
        assert parsed.value == expected
        assert parsed.format == expected_format

    @pytest.mark.parametrize(
        "arxiv,expected,expected_format",
        [
            ("hep-th/9901001", "hep-th/9901001", "old"),
            ("astro-ph/0001001", "astro-ph/0001001", "old"),
            ("math/0612345", "math/0612345", "old"),
        ],
    )
    def test_arxiv_old_format_valid(self, arxiv: str, expected: str, expected_format: str):
        """Valid old arXiv IDs should be parsed."""
        parsed = ArXivID.parse(arxiv)
        assert parsed.value == expected
        assert parsed.format == expected_format

    @pytest.mark.parametrize(
        "arxiv,expected",
        [
            ("https://arxiv.org/abs/1234.56789", "1234.56789"),
            ("http://arxiv.org/abs/1234.56789", "1234.56789"),
            ("https://arxiv.org/pdf/1234.56789.pdf", "1234.56789"),
            ("arxiv:1234.56789", "1234.56789"),
            ("arXiv:1234.56789", "1234.56789"),
            ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
        ],
    )
    def test_arxiv_url_extraction(self, arxiv: str, expected: str):
        """arXiv ID should be extracted from URLs and prefixes."""
        parsed = ArXivID.parse(arxiv)
        assert parsed.value == expected

    @pytest.mark.parametrize(
        "arxiv",
        [
            "123.56789",  # Wrong format (3 digits before dot)
            "12345.6789",  # Wrong format (5 digits before dot)
            "1234.567",  # Too short after dot
            "invalid/format",  # Invalid old format category
            "hep-th/123456",  # Too short old format number
            "",
        ],
    )
    def test_arxiv_invalid(self, arxiv: str):
        """Invalid arXiv IDs should raise ValueError."""
        with pytest.raises(ValueError):
            ArXivID.parse(arxiv)

    def test_arxiv_url_property(self):
        """ArXiv url property should return arxiv.org abstract URL."""
        arxiv = ArXivID.parse("1234.56789")
        assert arxiv.url == "https://arxiv.org/abs/1234.56789"

    def test_arxiv_pdf_url_property(self):
        """ArXiv pdf_url property should return arxiv.org PDF URL."""
        arxiv = ArXivID.parse("1234.56789")
        assert arxiv.pdf_url == "https://arxiv.org/pdf/1234.56789.pdf"

    def test_arxiv_string_representation(self):
        """ArXiv __str__ should return value."""
        arxiv = ArXivID.parse("https://arxiv.org/abs/1234.56789")
        assert str(arxiv) == "1234.56789"

    def test_arxiv_hash(self):
        """ArXiv hash should be case-insensitive."""
        arxiv1 = ArXivID.parse("HEP-TH/9901001")
        arxiv2 = ArXivID.parse("hep-th/9901001")
        assert hash(arxiv1) == hash(arxiv2)
