"""Text normalization utilities for matching and deduplication."""

import re
import unicodedata


def normalize_text(
    text: str,
    *,
    lowercase: bool = True,
    remove_accents: bool = True,
    remove_punctuation: bool = True,
    collapse_whitespace: bool = True,
) -> str:
    """
    Normalize text for matching purposes.

    Args:
        text: Input text to normalize
        lowercase: Convert to lowercase
        remove_accents: Remove diacritical marks (e -> e)
        remove_punctuation: Remove all punctuation
        collapse_whitespace: Replace multiple spaces with single space

    Returns:
        Normalized string suitable for comparison
    """
    if not text:
        return ""

    result = text

    if remove_accents:
        # Decompose unicode characters and remove combining marks
        nfkd = unicodedata.normalize("NFKD", result)
        result = "".join(c for c in nfkd if not unicodedata.combining(c))

    if lowercase:
        result = result.lower()

    if remove_punctuation:
        # Keep alphanumeric and whitespace
        result = re.sub(r"[^\w\s]", "", result)

    if collapse_whitespace:
        result = re.sub(r"\s+", " ", result).strip()

    return result


def normalize_title(title: str) -> str:
    """
    Normalize a title for matching.

    Removes common articles and normalizes text.
    """
    normalized = normalize_text(title)
    # Remove common leading articles
    normalized = re.sub(r"^(the|a|an)\s+", "", normalized)
    return normalized


def normalize_author_name(name: str) -> str:
    """
    Normalize an author name for matching.

    Handles various name formats:
    - "John Smith" -> "john smith"
    - "Smith, John" -> "john smith"
    - "J. Smith" -> "j smith"
    """
    normalized = normalize_text(name)

    # Handle "Last, First" format
    if "," in name:
        parts = [p.strip() for p in normalized.split(",", 1)]
        if len(parts) == 2:
            normalized = f"{parts[1]} {parts[0]}"

    return normalized


def isbn_10_to_13(isbn10: str) -> str:
    """Convert ISBN-10 to ISBN-13."""
    # Remove any hyphens/spaces
    isbn10 = re.sub(r"[-\s]", "", isbn10).upper()

    if len(isbn10) != 10:
        raise ValueError(f"Invalid ISBN-10 length: {isbn10}")

    # Remove check digit, add 978 prefix
    base = "978" + isbn10[:-1]

    # Calculate new check digit
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    check = (10 - (total % 10)) % 10

    return base + str(check)


def isbn_13_to_10(isbn13: str) -> str | None:
    """Convert ISBN-13 to ISBN-10 (only works for 978 prefix)."""
    # Remove any hyphens/spaces
    isbn13 = re.sub(r"[-\s]", "", isbn13)

    if len(isbn13) != 13 or not isbn13.startswith("978"):
        return None

    base = isbn13[3:-1]  # Remove 978 prefix and check digit

    # Calculate ISBN-10 check digit
    total = sum(int(d) * (10 - i) for i, d in enumerate(base))
    check = (11 - (total % 11)) % 11
    check_char = "X" if check == 10 else str(check)

    return base + check_char


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two strings using Jaccard similarity.

    Returns a score between 0.0 and 1.0.
    """
    if not text1 or not text2:
        return 0.0

    # Normalize texts
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if norm1 == norm2:
        return 1.0

    # Use word-level Jaccard similarity
    words1 = set(norm1.split())
    words2 = set(norm2.split())

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0
