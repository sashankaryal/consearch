"""Book resolvers for fetching book metadata."""

from consearch.resolution.books.base import AbstractBookResolver
from consearch.resolution.books.google_books import GoogleBooksResolver
from consearch.resolution.books.isbndb import ISBNDbResolver
from consearch.resolution.books.openlibrary import OpenLibraryResolver

__all__ = [
    "AbstractBookResolver",
    "GoogleBooksResolver",
    "ISBNDbResolver",
    "OpenLibraryResolver",
]
