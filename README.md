# Consearch

A unified consumable (books, papers) search and resolution library. Fetches metadata from multiple sources and provides a unified API for searching and resolving identifiers like ISBN, DOI, arXiv IDs, and more.

## Design Overview

### Architecture

Consearch follows a layered architecture:

```
API Layer (FastAPI)
    │
Service Layer (ResolutionService, SearchService)
    │
Resolution Layer (ResolverRegistry, Resolver Chains)
    │
Data Layer (Repositories, Models)
    │
External Sources (Open Library, Google Books, Crossref, etc.)
```

### Key Concepts

- **Resolution**: The process of fetching metadata for a book or paper from external sources given an identifier (ISBN, DOI, etc.) or title.
- **Resolver**: A component that fetches data from a specific source (e.g., OpenLibraryResolver, CrossrefResolver).
- **Resolver Chain**: Orchestrates multiple resolvers with fallback logic and result aggregation.
- **Resolver Registry**: Manages resolver instances and creates chains for different consumable types.

### Data Flow

1. **Detection**: Input (ISBN, DOI, title) is analyzed to determine its type
2. **Resolution**: Appropriate resolvers are invoked based on input type
3. **Aggregation**: Results from multiple sources are merged
4. **Persistence**: Records are stored in PostgreSQL
5. **Indexing**: Records are indexed in Meilisearch for full-text search
6. **Caching**: Results are cached in Redis to reduce API calls

## Tech Stack

- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Data Models**: Pydantic v2
- **HTTP Client**: httpx (async)
- **Database**: PostgreSQL with SQLAlchemy (async) + asyncpg
- **Migrations**: Alembic
- **Search**: Meilisearch
- **Cache**: Redis
- **Testing**: pytest, pytest-asyncio, respx

## Project Structure

```
src/consearch/
├── api/                # FastAPI routes and schemas
│   ├── routes/         # Endpoint implementations
│   ├── schemas/        # Request/response models
│   └── dependencies.py # Dependency injection
├── cache/              # Redis caching layer
├── core/               # Core domain models and types
│   ├── models.py       # BookRecord, PaperRecord, etc.
│   ├── types.py        # Enums and type definitions
│   ├── identifiers.py  # ISBN, DOI validation
│   └── exceptions.py   # Custom exceptions
├── db/                 # Database layer
│   ├── models/         # SQLAlchemy ORM models
│   └── repositories/   # Data access patterns
├── detection/          # Input type detection
├── resolution/         # External source resolvers
│   ├── books/          # Book resolvers (OpenLibrary, Google Books, ISBNdb)
│   ├── papers/         # Paper resolvers (Crossref, Semantic Scholar)
│   ├── registry.py     # Resolver management
│   └── chain.py        # Resolver chain orchestration
├── search/             # Meilisearch integration
├── services/           # Business logic orchestration
└── config.py           # Settings via pydantic-settings

tests/
├── unit/               # Unit tests (no external dependencies)
├── integration/        # Integration tests (require Docker services)
└── fixtures/           # JSON fixtures for API mocking
```

## Supported Data Sources

### Books
- **Open Library** - Free, no API key required
- **Google Books** - Optional API key for higher rate limits
- **ISBNdb** - Requires API key

### Papers
- **Crossref** - Free, email recommended for polite pool
- **Semantic Scholar** - Optional API key for higher rate limits

## Supported Identifiers

| Type | Example | Consumable |
|------|---------|------------|
| ISBN-10 | `0134093410` | Book |
| ISBN-13 | `9780134093413` | Book |
| DOI | `10.1038/nature12373` | Paper/Book |
| arXiv | `2301.00234` | Paper |
| PMID | `12345678` | Paper |
| Title | `Clean Code` | Both |

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose

### Installation

```bash
# Clone repository
git clone https://github.com/sashankaryal/consearch.git
cd consearch

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### Start Services

```bash
# Start PostgreSQL, Redis, and Meilisearch
docker-compose up -d

# Verify services are running
docker-compose ps
```

Note: PostgreSQL is exposed on port **5433** (to avoid conflicts with local PostgreSQL installations).

### Run Migrations

```bash
alembic upgrade head
```

### Start the API

```bash
uvicorn consearch.api.app:app --reload
```

API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Running Tests

### Unit Tests

Unit tests don't require external services:

```bash
pytest tests/unit -v
```

### Integration Tests

Integration tests require Docker services running:

```bash
# Start services
docker-compose up -d

# Run integration tests
pytest tests/integration -v
```

### All Tests

```bash
pytest -v
```

### With Coverage

```bash
pytest --cov=src/consearch --cov-report=html
```

## API Endpoints

### Health
- `GET /api/v1/health` - Service health status
- `GET /api/v1/ready` - Readiness check

### Resolution
- `POST /api/v1/resolve/detect?query=...` - Detect input type
- `POST /api/v1/resolve/book` - Resolve book metadata
- `POST /api/v1/resolve/paper` - Resolve paper metadata

### Search
- `GET /api/v1/search/books?q=...` - Search books
- `GET /api/v1/search/papers?q=...` - Search papers

## Configuration

Environment variables (prefix: `CONSEARCH_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL URL | `postgresql+asyncpg://consearch:consearch@localhost:5433/consearch` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `MEILISEARCH_URL` | Meilisearch URL | `http://localhost:7700` |
| `MEILISEARCH_KEY` | Meilisearch API key | `dev-master-key` |
| `ISBNDB_API_KEY` | ISBNdb API key | None |
| `GOOGLE_BOOKS_API_KEY` | Google Books API key | None |
| `CROSSREF_EMAIL` | Email for Crossref polite pool | None |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API key | None |

## Development

### Linting

```bash
ruff check src tests
ruff check --fix src tests  # Auto-fix
```

### Formatting

```bash
ruff format src tests
```

### Type Checking

```bash
mypy src
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

## License

MIT
