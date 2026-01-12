"""Identifier value objects with validation and normalization."""

from __future__ import annotations

import re
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class ISBN(BaseModel):
    """Normalized ISBN representation supporting both ISBN-10 and ISBN-13."""

    value: str = Field(..., description="Normalized ISBN value (digits only, with X for ISBN-10)")
    format: Literal["isbn10", "isbn13"]

    # Regex patterns for validation
    ISBN10_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9]{9}[0-9X]$")
    ISBN13_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^(978|979)[0-9]{10}$")

    @field_validator("value", mode="before")
    @classmethod
    def normalize_isbn(cls, v: str) -> str:
        """Remove hyphens and spaces, uppercase X."""
        return re.sub(r"[-\s]", "", str(v)).upper()

    @model_validator(mode="after")
    def validate_isbn_format(self) -> Self:
        """Validate ISBN checksum and format consistency."""
        if self.format == "isbn10":
            if not self.ISBN10_PATTERN.match(self.value):
                raise ValueError(f"Invalid ISBN-10 format: {self.value}")
            if not self._validate_isbn10_checksum():
                raise ValueError(f"Invalid ISBN-10 checksum: {self.value}")
        else:
            if not self.ISBN13_PATTERN.match(self.value):
                raise ValueError(f"Invalid ISBN-13 format: {self.value}")
            if not self._validate_isbn13_checksum():
                raise ValueError(f"Invalid ISBN-13 checksum: {self.value}")
        return self

    def _validate_isbn10_checksum(self) -> bool:
        """Validate ISBN-10 checksum using modulo 11."""
        total = sum(
            (10 if c == "X" else int(c)) * (10 - i) for i, c in enumerate(self.value)
        )
        return total % 11 == 0

    def _validate_isbn13_checksum(self) -> bool:
        """Validate ISBN-13 checksum using alternating 1/3 weights."""
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(self.value))
        return total % 10 == 0

    def to_isbn13(self) -> ISBN:
        """Convert to ISBN-13 format."""
        if self.format == "isbn13":
            return self
        # Convert ISBN-10 to ISBN-13
        base = "978" + self.value[:-1]
        checksum = self._calculate_isbn13_checksum(base)
        return ISBN(value=base + str(checksum), format="isbn13")

    def to_isbn10(self) -> ISBN | None:
        """Convert to ISBN-10 if possible (only 978 prefix)."""
        if self.format == "isbn10":
            return self
        if not self.value.startswith("978"):
            return None  # Cannot convert 979 prefix to ISBN-10
        base = self.value[3:-1]
        checksum = self._calculate_isbn10_checksum(base)
        return ISBN(value=base + checksum, format="isbn10")

    @staticmethod
    def _calculate_isbn13_checksum(base: str) -> int:
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))
        return (10 - (total % 10)) % 10

    @staticmethod
    def _calculate_isbn10_checksum(base: str) -> str:
        total = sum(int(c) * (10 - i) for i, c in enumerate(base))
        checksum = (11 - (total % 11)) % 11
        return "X" if checksum == 10 else str(checksum)

    @classmethod
    def parse(cls, value: str) -> ISBN:
        """Parse an ISBN string, auto-detecting format."""
        normalized = re.sub(r"[-\s]", "", value).upper()
        if len(normalized) == 10:
            return cls(value=normalized, format="isbn10")
        elif len(normalized) == 13:
            return cls(value=normalized, format="isbn13")
        raise ValueError(f"Invalid ISBN length: {len(normalized)}")

    def __str__(self) -> str:
        return self.value

    def __hash__(self) -> int:
        # Normalize to ISBN-13 for consistent hashing
        isbn13 = self.to_isbn13()
        return hash(isbn13.value)


class DOI(BaseModel):
    """Digital Object Identifier value object."""

    value: str = Field(..., description="DOI value (e.g., 10.1000/xyz123)")

    DOI_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^10\.\d{4,}(?:\.\d+)*/[^\s]+$")

    @field_validator("value", mode="before")
    @classmethod
    def normalize_doi(cls, v: str) -> str:
        """Extract DOI from URL if provided."""
        v = str(v).strip()
        # Handle doi.org URLs
        if v.startswith(("https://doi.org/", "http://doi.org/")):
            v = v.split("doi.org/", 1)[1]
        elif v.startswith(("https://dx.doi.org/", "http://dx.doi.org/")):
            v = v.split("dx.doi.org/", 1)[1]
        # Remove doi: prefix
        if v.lower().startswith("doi:"):
            v = v[4:].strip()
        return v

    @model_validator(mode="after")
    def validate_doi(self) -> Self:
        if not self.DOI_PATTERN.match(self.value):
            raise ValueError(f"Invalid DOI format: {self.value}")
        return self

    @property
    def url(self) -> str:
        """Return the doi.org URL."""
        return f"https://doi.org/{self.value}"

    def __str__(self) -> str:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value.lower())


class ArXivID(BaseModel):
    """arXiv identifier supporting old and new formats."""

    value: str = Field(..., description="Normalized arXiv ID")
    format: Literal["old", "new"]

    # Old format: archive/YYMMNNN (e.g., hep-th/9901001)
    OLD_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z-]+/\d{7}$")
    # New format: YYMM.NNNNN[vN] (e.g., 1234.56789, 1234.56789v2)
    NEW_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")

    @field_validator("value", mode="before")
    @classmethod
    def normalize_arxiv(cls, v: str) -> str:
        """Extract arXiv ID from URL or prefix."""
        v = str(v).strip()
        # Handle arxiv.org URLs
        for prefix in [
            "https://arxiv.org/abs/",
            "http://arxiv.org/abs/",
            "https://arxiv.org/pdf/",
            "http://arxiv.org/pdf/",
        ]:
            if v.startswith(prefix):
                v = v[len(prefix) :].rstrip(".pdf")
                break
        # Remove arXiv: prefix
        if v.lower().startswith("arxiv:"):
            v = v[6:].strip()
        return v

    @model_validator(mode="after")
    def validate_arxiv(self) -> Self:
        if self.format == "old":
            if not self.OLD_PATTERN.match(self.value):
                raise ValueError(f"Invalid old arXiv format: {self.value}")
        else:
            if not self.NEW_PATTERN.match(self.value):
                raise ValueError(f"Invalid new arXiv format: {self.value}")
        return self

    @classmethod
    def parse(cls, value: str) -> ArXivID:
        """Parse an arXiv ID, auto-detecting format."""
        normalized = value.strip()
        # Remove URL/prefix
        for prefix in [
            "https://arxiv.org/abs/",
            "http://arxiv.org/abs/",
            "https://arxiv.org/pdf/",
            "http://arxiv.org/pdf/",
        ]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].rstrip(".pdf")
                break
        if normalized.lower().startswith("arxiv:"):
            normalized = normalized[6:].strip()

        if "/" in normalized:
            # Old format: lowercase the archive prefix
            return cls(value=normalized.lower(), format="old")
        return cls(value=normalized, format="new")

    @property
    def url(self) -> str:
        """Return the arXiv abstract URL."""
        return f"https://arxiv.org/abs/{self.value}"

    @property
    def pdf_url(self) -> str:
        """Return the arXiv PDF URL."""
        return f"https://arxiv.org/pdf/{self.value}.pdf"

    def __str__(self) -> str:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value.lower())


# Type alias for any identifier
Identifier = ISBN | DOI | ArXivID
