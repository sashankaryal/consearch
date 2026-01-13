"""Resolution service for orchestrating the resolve → store → index flow."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from consearch.core.models import BookRecord, PaperRecord
from consearch.core.normalization import normalize_title
from consearch.core.types import ConsumableType, InputType, ResolutionStatus
from consearch.detection.identifier import IdentifierDetector
from consearch.resolution.chain import AggregatedResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from consearch.cache.client import AsyncRedisClient
    from consearch.db.models.author import AuthorModel
    from consearch.db.models.work import WorkModel
    from consearch.resolution.registry import ResolverRegistry
    from consearch.search.indexer import SearchIndexer

logger = logging.getLogger(__name__)


class ResolutionService:
    """
    Service for resolving consumables with caching, persistence, and indexing.

    Orchestrates the full resolution flow:
    1. Check cache for recent results
    2. Check database for existing records
    3. Resolve from external sources
    4. Persist new records to database
    5. Index to search engine
    6. Cache results
    """

    CACHE_TTL = 3600 * 24  # 24 hours

    def __init__(
        self,
        session: "AsyncSession",
        resolver_registry: "ResolverRegistry",
        cache: "AsyncRedisClient | None" = None,
        indexer: "SearchIndexer | None" = None,
    ) -> None:
        """
        Initialize the resolution service.

        Args:
            session: Database session for persistence
            resolver_registry: Registry of resolvers
            cache: Optional Redis client for caching
            indexer: Optional search indexer for Meilisearch
        """
        self._session = session
        self._registry = resolver_registry
        self._cache = cache
        self._indexer = indexer
        self._detector = IdentifierDetector()

    async def resolve_book(
        self,
        query: str,
        input_type: InputType | None = None,
    ) -> AggregatedResult[BookRecord]:
        """
        Resolve a book with caching and persistence.

        Args:
            query: ISBN, title, or other identifier
            input_type: Explicit input type (auto-detected if not provided)

        Returns:
            Aggregated result with records from all sources
        """
        start = time.monotonic()

        # Detect input type if not provided
        if input_type is None:
            detection = self._detector.detect(query)
            input_type = detection.input_type

        # Try cache first
        cache_key = f"resolve:book:{input_type.value}:{query}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for book resolution: {query}")
                # TODO: Deserialize cached result
                pass

        # Try database for identifier lookups
        existing_work = await self._check_db_for_book(query, input_type)
        if existing_work:
            logger.debug(f"Database hit for book: {query}")
            # Convert to record and return
            record = self._work_to_book_record(existing_work)
            if record:
                return AggregatedResult(
                    primary_result=None,
                    all_records=[record],
                    sources_tried=["database"],
                )

        # Resolve from external sources
        chain = self._registry.get_book_chain()
        result = await chain.resolve(query, input_type)

        # Persist new records
        if result.success and result.all_records:
            for record in result.all_records:
                await self._persist_book_record(record)

        # Cache result
        if self._cache and result.success:
            # TODO: Serialize and cache result
            pass

        duration = time.monotonic() - start
        logger.info(f"Book resolution completed in {duration:.2f}s: {query}")

        return result

    async def resolve_paper(
        self,
        query: str,
        input_type: InputType | None = None,
    ) -> AggregatedResult[PaperRecord]:
        """
        Resolve a paper with caching and persistence.

        Args:
            query: DOI, arXiv ID, title, or citation
            input_type: Explicit input type (auto-detected if not provided)

        Returns:
            Aggregated result with records from all sources
        """
        start = time.monotonic()

        # Detect input type if not provided
        if input_type is None:
            detection = self._detector.detect(query)
            input_type = detection.input_type

        # Try cache first
        cache_key = f"resolve:paper:{input_type.value}:{query}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for paper resolution: {query}")
                # TODO: Deserialize cached result
                pass

        # Try database for identifier lookups
        existing_work = await self._check_db_for_paper(query, input_type)
        if existing_work:
            logger.debug(f"Database hit for paper: {query}")
            record = self._work_to_paper_record(existing_work)
            if record:
                return AggregatedResult(
                    primary_result=None,
                    all_records=[record],
                    sources_tried=["database"],
                )

        # Resolve from external sources
        chain = self._registry.get_paper_chain()
        result = await chain.resolve(query, input_type)

        # Persist new records
        if result.success and result.all_records:
            for record in result.all_records:
                await self._persist_paper_record(record)

        # Cache result
        if self._cache and result.success:
            # TODO: Serialize and cache result
            pass

        duration = time.monotonic() - start
        logger.info(f"Paper resolution completed in {duration:.2f}s: {query}")

        return result

    async def _check_db_for_book(
        self,
        query: str,
        input_type: InputType,
    ) -> "WorkModel | None":
        """Check database for existing book by identifier."""
        from consearch.db.repositories.work import WorkRepository

        repo = WorkRepository(self._session)

        if input_type in (InputType.ISBN_10, InputType.ISBN_13):
            return await repo.get_by_isbn(query)

        # For title searches, we don't check DB (would need fuzzy match)
        return None

    async def _check_db_for_paper(
        self,
        query: str,
        input_type: InputType,
    ) -> "WorkModel | None":
        """Check database for existing paper by identifier."""
        from consearch.db.repositories.work import WorkRepository

        repo = WorkRepository(self._session)

        if input_type == InputType.DOI:
            return await repo.get_by_doi(query)
        elif input_type == InputType.ARXIV:
            return await repo.get_by_arxiv_id(query)

        # For title/citation searches, we don't check DB
        return None

    async def _persist_book_record(self, record: BookRecord) -> "WorkModel | None":
        """Persist a book record to the database."""
        from consearch.db.models.author import AuthorModel
        from consearch.db.models.source_record import SourceRecordModel
        from consearch.db.models.work import WorkModel
        from consearch.db.repositories.author import AuthorRepository
        from consearch.db.repositories.work import WorkRepository

        work_repo = WorkRepository(self._session)
        author_repo = AuthorRepository(self._session)

        # Check if work already exists by identifiers
        existing = None
        if record.identifiers.isbn_13:
            existing = await work_repo.get_by_isbn(record.identifiers.isbn_13)
        elif record.identifiers.isbn_10:
            existing = await work_repo.get_by_isbn(record.identifiers.isbn_10)

        if existing:
            logger.debug(f"Book already exists: {record.title}")
            return existing

        # Build identifiers dict
        identifiers = {
            "isbn_10": record.identifiers.isbn_10,
            "isbn_13": record.identifiers.isbn_13,
            "openlibrary_id": record.identifiers.openlibrary_id,
            "google_books_id": record.identifiers.google_books_id,
            "publisher": record.publisher,
            "subjects": record.subjects,
            "language": record.language,
        }
        # Remove None values
        identifiers = {k: v for k, v in identifiers.items() if v is not None}

        # Create work
        work = WorkModel(
            work_type=ConsumableType.BOOK,
            title=record.title,
            title_normalized=normalize_title(record.title),
            year=record.year,
            identifiers=identifiers,
        )

        self._session.add(work)
        await self._session.flush()  # Flush work first to get its ID

        # Create/link authors with positions
        from sqlalchemy import insert
        from consearch.db.models.associations import work_author_association

        for i, author_record in enumerate(record.authors):
            author, _ = await author_repo.get_or_create(
                name=author_record.name,
                name_normalized=normalize_title(author_record.name),  # Normalize for matching
                external_ids={"orcid": author_record.orcid} if author_record.orcid else None,
            )
            # Insert into association table with explicit position
            stmt = insert(work_author_association).values(
                work_id=work.id,
                author_id=author.id,
                position=i,
            )
            await self._session.execute(stmt)

        # Create source record if we have metadata and it doesn't exist
        if record.source_metadata:
            from sqlalchemy import select

            # Check if source record already exists
            existing_source = await self._session.execute(
                select(SourceRecordModel).where(
                    SourceRecordModel.source == record.source_metadata.source,
                    SourceRecordModel.source_id == record.source_metadata.source_id,
                )
            )
            if not existing_source.scalar_one_or_none():
                source_record = SourceRecordModel(
                    work=work,
                    source=record.source_metadata.source,
                    source_id=record.source_metadata.source_id,
                    raw_data=record.source_metadata.raw_data or {},
                    fetched_at=datetime.now(timezone.utc),
                )
                self._session.add(source_record)

        await self._session.flush()

        # Refresh work to load authors relationship for indexer
        await self._session.refresh(work, ["authors"])

        # Index to search
        if self._indexer:
            await self._indexer.index_book(work)

        logger.info(f"Persisted book: {record.title}")
        return work

    async def _persist_paper_record(self, record: PaperRecord) -> "WorkModel | None":
        """Persist a paper record to the database."""
        from consearch.db.models.author import AuthorModel
        from consearch.db.models.source_record import SourceRecordModel
        from consearch.db.models.work import WorkModel
        from consearch.db.repositories.author import AuthorRepository
        from consearch.db.repositories.work import WorkRepository

        work_repo = WorkRepository(self._session)
        author_repo = AuthorRepository(self._session)

        # Check if work already exists by identifiers
        existing = None
        if record.identifiers.doi:
            existing = await work_repo.get_by_doi(record.identifiers.doi)
        elif record.identifiers.arxiv_id:
            existing = await work_repo.get_by_arxiv_id(record.identifiers.arxiv_id)

        if existing:
            logger.debug(f"Paper already exists: {record.title}")
            return existing

        # Build identifiers dict
        identifiers = {
            "doi": record.identifiers.doi,
            "arxiv_id": record.identifiers.arxiv_id,
            "pmid": record.identifiers.pmid,
            "crossref_id": record.identifiers.crossref_id,
            "semantic_scholar_id": record.identifiers.semantic_scholar_id,
            "abstract": record.abstract,
            "journal": record.journal,
            "volume": record.volume,
            "issue": record.issue,
            "pages": record.pages_range,
            "citation_count": record.citation_count,
        }
        # Remove None values
        identifiers = {k: v for k, v in identifiers.items() if v is not None}

        # Create work
        work = WorkModel(
            work_type=ConsumableType.PAPER,
            title=record.title,
            title_normalized=normalize_title(record.title),
            year=record.year,
            identifiers=identifiers,
        )

        self._session.add(work)
        await self._session.flush()  # Flush work first to get its ID

        # Create/link authors with positions
        from sqlalchemy import insert
        from consearch.db.models.associations import work_author_association

        for i, author_record in enumerate(record.authors):
            author, _ = await author_repo.get_or_create(
                name=author_record.name,
                name_normalized=normalize_title(author_record.name),
                external_ids={"orcid": author_record.orcid} if author_record.orcid else None,
            )
            # Insert into association table with explicit position
            stmt = insert(work_author_association).values(
                work_id=work.id,
                author_id=author.id,
                position=i,
            )
            await self._session.execute(stmt)

        # Create source record if we have metadata and it doesn't exist
        if record.source_metadata:
            from sqlalchemy import select

            # Check if source record already exists
            existing_source = await self._session.execute(
                select(SourceRecordModel).where(
                    SourceRecordModel.source == record.source_metadata.source,
                    SourceRecordModel.source_id == record.source_metadata.source_id,
                )
            )
            if not existing_source.scalar_one_or_none():
                source_record = SourceRecordModel(
                    work=work,
                    source=record.source_metadata.source,
                    source_id=record.source_metadata.source_id,
                    raw_data=record.source_metadata.raw_data or {},
                    fetched_at=datetime.now(timezone.utc),
                )
                self._session.add(source_record)

        await self._session.flush()

        # Refresh work to load authors relationship for indexer
        await self._session.refresh(work, ["authors"])

        # Index to search
        if self._indexer:
            await self._indexer.index_paper(work)

        logger.info(f"Persisted paper: {record.title}")
        return work

    def _work_to_book_record(self, work: "WorkModel") -> BookRecord | None:
        """Convert a WorkModel to BookRecord."""
        from consearch.core.models import Author, Identifiers

        if work.work_type != ConsumableType.BOOK:
            return None

        authors = [
            Author(name=a.name, orcid=a.external_ids.get("orcid") if a.external_ids else None)
            for a in work.authors
        ]

        idents = work.identifiers or {}
        identifiers = Identifiers(
            isbn_10=idents.get("isbn_10"),
            isbn_13=idents.get("isbn_13"),
            openlibrary_id=idents.get("openlibrary_id"),
            google_books_id=idents.get("google_books_id"),
        )

        return BookRecord(
            title=work.title,
            authors=authors,
            year=work.year,
            identifiers=identifiers,
            publisher=idents.get("publisher"),
            subjects=idents.get("subjects", []),
            language=idents.get("language"),
        )

    def _work_to_paper_record(self, work: "WorkModel") -> PaperRecord | None:
        """Convert a WorkModel to PaperRecord."""
        from consearch.core.models import Author, Identifiers

        if work.work_type != ConsumableType.PAPER:
            return None

        authors = [
            Author(name=a.name, orcid=a.external_ids.get("orcid") if a.external_ids else None)
            for a in work.authors
        ]

        idents = work.identifiers or {}
        identifiers = Identifiers(
            doi=idents.get("doi"),
            arxiv_id=idents.get("arxiv_id"),
            pmid=idents.get("pmid"),
            crossref_id=idents.get("crossref_id"),
            semantic_scholar_id=idents.get("semantic_scholar_id"),
        )

        return PaperRecord(
            title=work.title,
            authors=authors,
            year=work.year,
            identifiers=identifiers,
            abstract=idents.get("abstract"),
            journal=idents.get("journal"),
            volume=idents.get("volume"),
            issue=idents.get("issue"),
            pages_range=idents.get("pages"),
            citation_count=idents.get("citation_count"),
        )
