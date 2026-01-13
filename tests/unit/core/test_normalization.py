"""Tests for text normalization utilities."""

from __future__ import annotations

import pytest

from consearch.core.normalization import (
    calculate_similarity,
    isbn_10_to_13,
    isbn_13_to_10,
    normalize_author_name,
    normalize_text,
    normalize_title,
)

# ============================================================================
# normalize_text Tests
# ============================================================================


class TestNormalizeText:
    """Tests for the normalize_text function."""

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert normalize_text("") == ""

    def test_lowercase(self):
        """Text should be lowercased."""
        assert normalize_text("Hello World") == "hello world"

    def test_preserve_case(self):
        """Text case should be preserved when lowercase=False."""
        assert normalize_text("Hello World", lowercase=False) == "Hello World"

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("café", "cafe"),
            ("naïve", "naive"),
            ("résumé", "resume"),
            ("Ångström", "angstrom"),
            ("São Paulo", "sao paulo"),
            ("Müller", "muller"),
        ],
    )
    def test_remove_accents(self, input_text: str, expected: str):
        """Diacritical marks should be removed."""
        assert normalize_text(input_text) == expected

    def test_preserve_accents(self):
        """Accents should be preserved when remove_accents=False."""
        result = normalize_text("café", remove_accents=False)
        assert result == "café"

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("Hello, World!", "hello world"),
            ("test's value", "tests value"),
            ("O'Reilly", "oreilly"),
            ("C++", "c"),
            ("node.js", "nodejs"),
            ("semi;colon", "semicolon"),
        ],
    )
    def test_remove_punctuation(self, input_text: str, expected: str):
        """Punctuation should be removed."""
        assert normalize_text(input_text) == expected

    def test_preserve_punctuation(self):
        """Punctuation should be preserved when remove_punctuation=False."""
        result = normalize_text("Hello, World!", remove_punctuation=False)
        assert result == "hello, world!"

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("  hello  ", "hello"),
            ("hello   world", "hello world"),
            ("  multiple   spaces   ", "multiple spaces"),
            ("\nhello\t\nworld\n", "hello world"),
        ],
    )
    def test_collapse_whitespace(self, input_text: str, expected: str):
        """Multiple whitespace should be collapsed to single space."""
        assert normalize_text(input_text) == expected

    def test_preserve_whitespace(self):
        """Whitespace should be preserved when collapse_whitespace=False."""
        result = normalize_text("hello   world", collapse_whitespace=False)
        # Only punctuation removed, whitespace preserved
        assert "   " in result

    def test_all_options_disabled(self):
        """Text should be unchanged when all options disabled."""
        text = "  Café, Test!  "
        result = normalize_text(
            text,
            lowercase=False,
            remove_accents=False,
            remove_punctuation=False,
            collapse_whitespace=False,
        )
        assert result == text


# ============================================================================
# normalize_title Tests
# ============================================================================


class TestNormalizeTitle:
    """Tests for the normalize_title function."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("The Great Gatsby", "great gatsby"),
            ("A Tale of Two Cities", "tale of two cities"),
            ("An Introduction to Algorithms", "introduction to algorithms"),
            ("THE CATCHER IN THE RYE", "catcher in the rye"),
            ("  The   Hobbit  ", "hobbit"),
        ],
    )
    def test_remove_leading_articles(self, title: str, expected: str):
        """Leading articles (the, a, an) should be removed."""
        assert normalize_title(title) == expected

    def test_article_in_middle_preserved(self):
        """Articles in the middle of titles should be preserved."""
        result = normalize_title("Gone With the Wind")
        assert "the" in result  # "the" in middle preserved

    def test_empty_title(self):
        """Empty title should return empty string."""
        assert normalize_title("") == ""

    def test_title_with_special_characters(self):
        """Title with special characters should be normalized."""
        result = normalize_title("The Lord of the Rings: The Fellowship of the Ring")
        assert result == "lord of the rings the fellowship of the ring"


# ============================================================================
# normalize_author_name Tests
# ============================================================================


class TestNormalizeAuthorName:
    """Tests for the normalize_author_name function."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("John Smith", "john smith"),
            ("Jane Doe", "jane doe"),
            ("ROBERT MARTIN", "robert martin"),
            ("  John   Smith  ", "john smith"),
        ],
    )
    def test_basic_normalization(self, name: str, expected: str):
        """Basic author names should be normalized."""
        assert normalize_author_name(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Smith, John", "john smith"),
            ("Martin, Robert C.", "robert c martin"),
            ("García Márquez, Gabriel", "gabriel garcia marquez"),
        ],
    )
    def test_last_first_format(self, name: str, expected: str):
        """Last, First format should be converted to First Last."""
        assert normalize_author_name(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("J. Smith", "j smith"),
            ("J. R. R. Tolkien", "j r r tolkien"),
            ("G. Martin", "g martin"),
        ],
    )
    def test_initials(self, name: str, expected: str):
        """Names with initials should be normalized."""
        assert normalize_author_name(name) == expected

    def test_single_name(self):
        """Single name should be preserved."""
        assert normalize_author_name("Plato") == "plato"

    def test_empty_name(self):
        """Empty name should return empty string."""
        assert normalize_author_name("") == ""


# ============================================================================
# ISBN Conversion Tests
# ============================================================================


class TestISBNConversion:
    """Tests for ISBN-10 to ISBN-13 conversion functions."""

    @pytest.mark.parametrize(
        "isbn10,expected_isbn13",
        [
            ("0134093410", "9780134093413"),
            ("0306406152", "9780306406157"),
            ("155860832X", "9781558608320"),
        ],
    )
    def test_isbn_10_to_13(self, isbn10: str, expected_isbn13: str):
        """ISBN-10 should convert to ISBN-13 correctly."""
        assert isbn_10_to_13(isbn10) == expected_isbn13

    def test_isbn_10_to_13_with_hyphens(self):
        """ISBN-10 with hyphens should be handled."""
        assert isbn_10_to_13("0-13-409341-0") == "9780134093413"

    def test_isbn_10_to_13_invalid_length(self):
        """Invalid ISBN-10 length should raise ValueError."""
        with pytest.raises(ValueError):
            isbn_10_to_13("12345")

    @pytest.mark.parametrize(
        "isbn13,expected_isbn10",
        [
            ("9780134093413", "0134093410"),
            ("9780306406157", "0306406152"),
            ("9781558608320", "155860832X"),
        ],
    )
    def test_isbn_13_to_10(self, isbn13: str, expected_isbn10: str):
        """ISBN-13 with 978 prefix should convert to ISBN-10."""
        assert isbn_13_to_10(isbn13) == expected_isbn10

    def test_isbn_13_to_10_with_hyphens(self):
        """ISBN-13 with hyphens should be handled."""
        assert isbn_13_to_10("978-0-13-409341-3") == "0134093410"

    def test_isbn_13_to_10_979_prefix_returns_none(self):
        """ISBN-13 with 979 prefix should return None."""
        assert isbn_13_to_10("9790001000000") is None

    def test_isbn_13_to_10_invalid_length_returns_none(self):
        """Invalid ISBN-13 length should return None."""
        assert isbn_13_to_10("12345") is None

    def test_roundtrip_conversion(self):
        """Converting ISBN-10 -> 13 -> 10 should return original."""
        original = "0134093410"
        isbn13 = isbn_10_to_13(original)
        back = isbn_13_to_10(isbn13)
        assert back == original


# ============================================================================
# calculate_similarity Tests
# ============================================================================


class TestCalculateSimilarity:
    """Tests for the calculate_similarity function."""

    def test_identical_strings(self):
        """Identical strings should have similarity 1.0."""
        assert calculate_similarity("hello world", "hello world") == 1.0

    def test_identical_after_normalization(self):
        """Strings identical after normalization should have similarity 1.0."""
        assert calculate_similarity("Hello, World!", "hello world") == 1.0

    def test_empty_strings(self):
        """Empty strings should have similarity 0.0."""
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "world") == 0.0

    @pytest.mark.parametrize(
        "text1,text2,expected_range",
        [
            ("hello world", "hello", (0.4, 0.6)),  # Partial match
            ("programming python", "python programming", (0.9, 1.0)),  # Same words, different order
            ("machine learning", "deep learning", (0.3, 0.4)),  # One word overlap: 1/3 Jaccard
        ],
    )
    def test_partial_similarity(self, text1: str, text2: str, expected_range: tuple[float, float]):
        """Partial matches should have appropriate similarity scores."""
        similarity = calculate_similarity(text1, text2)
        assert expected_range[0] <= similarity <= expected_range[1]

    def test_completely_different_strings(self):
        """Completely different strings should have low similarity."""
        similarity = calculate_similarity("apple orange", "car bicycle")
        assert similarity < 0.1

    def test_similarity_is_symmetric(self):
        """Similarity should be symmetric (a vs b == b vs a)."""
        text1 = "machine learning python"
        text2 = "python data science"
        assert calculate_similarity(text1, text2) == calculate_similarity(text2, text1)
