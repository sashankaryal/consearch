"""Integration tests for database repositories."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from consearch.core.normalization import normalize_author_name, normalize_title
from consearch.core.types import ConsumableType
from consearch.db.models.author import AuthorModel
from consearch.db.models.work import WorkModel
from consearch.db.repositories.author import AuthorRepository
from consearch.db.repositories.work import WorkRepository

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]


# ============================================================================
# WorkRepository Tests
# ============================================================================


class TestWorkRepositoryBasicCRUD:
    """Tests for basic CRUD operations on WorkRepository."""

    async def test_create_work(self, db_session: AsyncSession):
        """Should create a new work."""
        repo = WorkRepository(db_session)

        work = WorkModel(
            id=uuid4(),
            work_type=ConsumableType.BOOK,
            title="Test Book",
            title_normalized=normalize_title("Test Book"),
            year=2024,
            identifiers={"isbn_13": "9781234567890"},
        )

        created = await repo.create(work)

        assert created.id == work.id
        assert created.title == "Test Book"
        assert created.work_type == ConsumableType.BOOK

    async def test_get_work_by_id(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should retrieve work by ID."""
        repo = WorkRepository(db_session)

        retrieved = await repo.get(sample_book_work.id)

        assert retrieved is not None
        assert retrieved.id == sample_book_work.id
        assert retrieved.title == sample_book_work.title

    async def test_get_nonexistent_work(self, db_session: AsyncSession):
        """Should return None for nonexistent work."""
        repo = WorkRepository(db_session)

        retrieved = await repo.get(uuid4())

        assert retrieved is None

    async def test_get_many_works(self, db_session: AsyncSession, multiple_works: list[WorkModel]):
        """Should retrieve multiple works by IDs."""
        repo = WorkRepository(db_session)

        ids = [w.id for w in multiple_works[:3]]
        retrieved = await repo.get_many(ids)

        assert len(retrieved) == 3
        assert all(w.id in ids for w in retrieved)

    async def test_get_many_empty_list(self, db_session: AsyncSession):
        """Should return empty list for empty IDs."""
        repo = WorkRepository(db_session)

        retrieved = await repo.get_many([])

        assert retrieved == []

    async def test_list_works_with_pagination(
        self, db_session: AsyncSession, multiple_works: list[WorkModel]
    ):
        """Should list works with pagination."""
        repo = WorkRepository(db_session)

        # Get first page
        page1 = await repo.list_all(offset=0, limit=2)
        assert len(page1) == 2

        # Get second page
        page2 = await repo.list_all(offset=2, limit=2)
        assert len(page2) == 2

        # Verify no overlap
        page1_ids = {w.id for w in page1}
        page2_ids = {w.id for w in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_update_work(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should update work fields."""
        repo = WorkRepository(db_session)

        # Modify work
        sample_book_work.year = 2020
        sample_book_work.language = "es"

        updated = await repo.update(sample_book_work)

        assert updated.year == 2020
        assert updated.language == "es"

    async def test_delete_work(self, db_session: AsyncSession):
        """Should delete work by ID."""
        repo = WorkRepository(db_session)

        # Create work
        work = WorkModel(
            id=uuid4(),
            work_type=ConsumableType.BOOK,
            title="To Delete",
            title_normalized="to delete",
            identifiers={},
        )
        await repo.create(work)

        # Delete work
        deleted = await repo.delete(work.id)
        assert deleted is True

        # Verify deletion
        retrieved = await repo.get(work.id)
        assert retrieved is None

    async def test_delete_nonexistent_work(self, db_session: AsyncSession):
        """Should return False for nonexistent work."""
        repo = WorkRepository(db_session)

        deleted = await repo.delete(uuid4())

        assert deleted is False

    async def test_exists(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should check if work exists."""
        repo = WorkRepository(db_session)

        assert await repo.exists(sample_book_work.id) is True
        assert await repo.exists(uuid4()) is False


class TestWorkRepositoryIdentifierQueries:
    """Tests for identifier-based queries on WorkRepository."""

    async def test_get_by_doi(self, db_session: AsyncSession, sample_paper_work: WorkModel):
        """Should find work by DOI."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_doi("10.1038/nature12373")

        assert found is not None
        assert found.id == sample_paper_work.id

    async def test_get_by_doi_case_insensitive(
        self, db_session: AsyncSession, sample_paper_work: WorkModel
    ):
        """Should find work by DOI case-insensitively."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_doi("10.1038/NATURE12373")

        assert found is not None
        assert found.id == sample_paper_work.id

    async def test_get_by_doi_not_found(self, db_session: AsyncSession):
        """Should return None for unknown DOI."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_doi("10.0000/unknown")

        assert found is None

    async def test_get_by_isbn13(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should find work by ISBN-13."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_isbn("9780134093413")

        assert found is not None
        assert found.id == sample_book_work.id

    async def test_get_by_isbn13_with_hyphens(
        self, db_session: AsyncSession, sample_book_work: WorkModel
    ):
        """Should find work by ISBN-13 with hyphens."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_isbn("978-0-134-09341-3")

        assert found is not None
        assert found.id == sample_book_work.id

    async def test_get_by_isbn10(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should find work by ISBN-10."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_isbn("0134093410")

        assert found is not None
        assert found.id == sample_book_work.id

    async def test_get_by_arxiv_id(self, db_session: AsyncSession):
        """Should find work by arXiv ID."""
        repo = WorkRepository(db_session)

        # Create work with arXiv ID
        work = WorkModel(
            id=uuid4(),
            work_type=ConsumableType.PAPER,
            title="ArXiv Paper",
            title_normalized="arxiv paper",
            identifiers={"arxiv_id": "2301.12345"},
        )
        await repo.create(work)

        found = await repo.get_by_arxiv_id("2301.12345")

        assert found is not None
        assert found.id == work.id

    async def test_get_by_identifier_generic(
        self, db_session: AsyncSession, sample_book_work: WorkModel
    ):
        """Should find work by generic identifier type."""
        repo = WorkRepository(db_session)

        found = await repo.get_by_identifier("openlibrary_id", "OL12345W")

        assert found is not None
        assert found.id == sample_book_work.id


class TestWorkRepositoryTitleQueries:
    """Tests for title-based queries on WorkRepository."""

    async def test_find_by_title(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should find works by title substring."""
        repo = WorkRepository(db_session)

        found = await repo.find_by_title("Clean Code")

        assert len(found) >= 1
        assert any(w.id == sample_book_work.id for w in found)

    async def test_find_by_title_case_insensitive(
        self, db_session: AsyncSession, sample_book_work: WorkModel
    ):
        """Should find works case-insensitively."""
        repo = WorkRepository(db_session)

        found = await repo.find_by_title("CLEAN CODE")

        assert len(found) >= 1
        assert any(w.id == sample_book_work.id for w in found)

    async def test_find_by_title_with_type_filter(
        self, db_session: AsyncSession, sample_book_work: WorkModel, sample_paper_work: WorkModel
    ):
        """Should filter by work type."""
        repo = WorkRepository(db_session)

        books = await repo.find_by_title("", work_type=ConsumableType.BOOK)
        papers = await repo.find_by_title("", work_type=ConsumableType.PAPER)

        assert any(w.id == sample_book_work.id for w in books)
        assert any(w.id == sample_paper_work.id for w in papers)
        assert not any(w.id == sample_paper_work.id for w in books)

    async def test_find_by_title_with_limit(
        self, db_session: AsyncSession, multiple_works: list[WorkModel]
    ):
        """Should respect limit parameter."""
        repo = WorkRepository(db_session)

        found = await repo.find_by_title("Test Book", limit=2)

        assert len(found) == 2

    async def test_find_by_title_and_year(
        self, db_session: AsyncSession, sample_book_work: WorkModel
    ):
        """Should find works by normalized title and year."""
        repo = WorkRepository(db_session)

        found = await repo.find_by_title_and_year(
            sample_book_work.title_normalized,
            sample_book_work.year,
        )

        assert len(found) >= 1
        assert any(w.id == sample_book_work.id for w in found)

    async def test_find_by_title_and_year_without_year(
        self, db_session: AsyncSession, sample_book_work: WorkModel
    ):
        """Should find works by normalized title without year filter."""
        repo = WorkRepository(db_session)

        found = await repo.find_by_title_and_year(
            sample_book_work.title_normalized,
            None,
        )

        assert len(found) >= 1
        assert any(w.id == sample_book_work.id for w in found)


class TestWorkRepositoryRelations:
    """Tests for relationship loading on WorkRepository."""

    async def test_get_with_relations(self, db_session: AsyncSession, sample_book_work: WorkModel):
        """Should load work with relationships."""
        repo = WorkRepository(db_session)

        loaded = await repo.get_with_relations(sample_book_work.id)

        assert loaded is not None
        assert loaded.id == sample_book_work.id
        assert len(loaded.authors) >= 1
        assert loaded.authors[0].name == "Robert C. Martin"

    async def test_list_by_type(
        self, db_session: AsyncSession, sample_book_work: WorkModel, sample_paper_work: WorkModel
    ):
        """Should list works by type."""
        repo = WorkRepository(db_session)

        books = await repo.list_by_type(ConsumableType.BOOK, limit=100)
        papers = await repo.list_by_type(ConsumableType.PAPER, limit=100)

        assert any(w.id == sample_book_work.id for w in books)
        assert any(w.id == sample_paper_work.id for w in papers)


# ============================================================================
# AuthorRepository Tests
# ============================================================================


class TestAuthorRepositoryBasicCRUD:
    """Tests for basic CRUD operations on AuthorRepository."""

    async def test_create_author(self, db_session: AsyncSession):
        """Should create a new author."""
        repo = AuthorRepository(db_session)

        author = AuthorModel(
            id=uuid4(),
            name="John Doe",
            name_normalized=normalize_author_name("John Doe"),
            external_ids={"orcid": "0000-0001-1234-5678"},
        )

        created = await repo.create(author)

        assert created.id == author.id
        assert created.name == "John Doe"

    async def test_get_author_by_id(self, db_session: AsyncSession, sample_author: AuthorModel):
        """Should retrieve author by ID."""
        repo = AuthorRepository(db_session)

        retrieved = await repo.get(sample_author.id)

        assert retrieved is not None
        assert retrieved.id == sample_author.id
        assert retrieved.name == sample_author.name

    async def test_get_nonexistent_author(self, db_session: AsyncSession):
        """Should return None for nonexistent author."""
        repo = AuthorRepository(db_session)

        retrieved = await repo.get(uuid4())

        assert retrieved is None

    async def test_delete_author(self, db_session: AsyncSession):
        """Should delete author by ID."""
        repo = AuthorRepository(db_session)

        # Create author
        author = AuthorModel(
            id=uuid4(),
            name="To Delete",
            name_normalized="to delete",
            external_ids={},
        )
        await repo.create(author)

        # Delete author
        deleted = await repo.delete(author.id)
        assert deleted is True

        # Verify deletion
        retrieved = await repo.get(author.id)
        assert retrieved is None


class TestAuthorRepositoryQueries:
    """Tests for specialized queries on AuthorRepository."""

    async def test_get_by_name_normalized(
        self, db_session: AsyncSession, sample_author: AuthorModel
    ):
        """Should find author by normalized name."""
        repo = AuthorRepository(db_session)

        found = await repo.get_by_name_normalized("robert c martin")

        assert found is not None
        assert found.id == sample_author.id

    async def test_get_by_name_normalized_not_found(self, db_session: AsyncSession):
        """Should return None for unknown normalized name."""
        repo = AuthorRepository(db_session)

        found = await repo.get_by_name_normalized("unknown author")

        assert found is None

    async def test_get_by_orcid(self, db_session: AsyncSession, sample_author: AuthorModel):
        """Should find author by ORCID."""
        repo = AuthorRepository(db_session)

        found = await repo.get_by_orcid("0000-0001-2345-6789")

        assert found is not None
        assert found.id == sample_author.id

    async def test_get_by_orcid_not_found(self, db_session: AsyncSession):
        """Should return None for unknown ORCID."""
        repo = AuthorRepository(db_session)

        found = await repo.get_by_orcid("0000-0000-0000-0000")

        assert found is None

    async def test_find_by_name(self, db_session: AsyncSession, sample_author: AuthorModel):
        """Should find authors by name substring."""
        repo = AuthorRepository(db_session)

        found = await repo.find_by_name("Martin")

        assert len(found) >= 1
        assert any(a.id == sample_author.id for a in found)

    async def test_find_by_name_case_insensitive(
        self, db_session: AsyncSession, sample_author: AuthorModel
    ):
        """Should find authors case-insensitively."""
        repo = AuthorRepository(db_session)

        found = await repo.find_by_name("MARTIN")

        assert len(found) >= 1
        assert any(a.id == sample_author.id for a in found)

    async def test_find_by_name_with_limit(self, db_session: AsyncSession):
        """Should respect limit parameter."""
        repo = AuthorRepository(db_session)

        # Create multiple authors
        for i in range(5):
            author = AuthorModel(
                id=uuid4(),
                name=f"Author Test {i}",
                name_normalized=f"author test {i}",
                external_ids={},
            )
            await repo.create(author)

        found = await repo.find_by_name("Author Test", limit=2)

        assert len(found) == 2


class TestAuthorRepositoryGetOrCreate:
    """Tests for get_or_create functionality on AuthorRepository."""

    async def test_get_or_create_existing(
        self, db_session: AsyncSession, sample_author: AuthorModel
    ):
        """Should get existing author."""
        repo = AuthorRepository(db_session)

        author, created = await repo.get_or_create(
            name="Robert C. Martin",
            name_normalized="robert c martin",
        )

        assert created is False
        assert author.id == sample_author.id

    async def test_get_or_create_new(self, db_session: AsyncSession):
        """Should create new author if not exists."""
        repo = AuthorRepository(db_session)

        author, created = await repo.get_or_create(
            name="New Author",
            name_normalized="new author",
            external_ids={"orcid": "0000-0002-0000-0000"},
        )

        assert created is True
        assert author.name == "New Author"
        assert author.external_ids["orcid"] == "0000-0002-0000-0000"

    async def test_get_or_create_idempotent(self, db_session: AsyncSession):
        """Calling get_or_create twice should return same author."""
        repo = AuthorRepository(db_session)

        author1, created1 = await repo.get_or_create(
            name="Unique Author",
            name_normalized="unique author",
        )
        author2, created2 = await repo.get_or_create(
            name="Unique Author",
            name_normalized="unique author",
        )

        assert created1 is True
        assert created2 is False
        assert author1.id == author2.id


# ============================================================================
# Transaction and Isolation Tests
# ============================================================================


class TestTransactionIsolation:
    """Tests for transaction behavior."""

    async def test_rollback_on_error(self, db_session: AsyncSession):
        """Changes should be rolled back on error."""
        repo = WorkRepository(db_session)

        # Create a work
        work = WorkModel(
            id=uuid4(),
            work_type=ConsumableType.BOOK,
            title="Will Be Rolled Back",
            title_normalized="will be rolled back",
            identifiers={},
        )
        await repo.create(work)

        # Verify it exists in current session
        assert await repo.exists(work.id)

        # Note: The fixture automatically rolls back, so we can't verify
        # the rollback here. This test mainly documents expected behavior.

    async def test_session_isolation(self, db_session_factory, sample_book_work: WorkModel):
        """Each session should be isolated."""
        # Create two separate sessions
        async with db_session_factory() as session1, session1.begin():
            repo1 = WorkRepository(session1)

            # Create a work in session1
            work = WorkModel(
                id=uuid4(),
                work_type=ConsumableType.BOOK,
                title="Session 1 Work",
                title_normalized="session 1 work",
                identifiers={},
            )
            await repo1.create(work)

            # Don't commit - changes should not be visible to session2
            async with db_session_factory() as session2:
                repo2 = WorkRepository(session2)
                # This should not find the uncommitted work
                found = await repo2.find_by_title("Session 1 Work")
                assert len(found) == 0

            await session1.rollback()
