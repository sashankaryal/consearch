# Contributing to Consearch

Thank you for your interest in contributing to Consearch! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive. We're all here to build something useful.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/sashankaryal/consearch.git
cd consearch

# Set up the development environment
make setup
source .venv/bin/activate

# Start required services
make up

# Run migrations
make migrate

# Verify everything works
make test
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write code following the project's style (enforced by ruff)
- Add type hints to all new code
- Write tests for new functionality
- Update documentation if needed

### 3. Run Quality Checks

```bash
# Run all checks (required to pass)
make check

# Run tests
make test

# Run tests with coverage
make test-cov
```

### 4. Commit Your Changes

Write clear, concise commit messages:

```bash
git commit -m "Add resolver for new data source"
git commit -m "Fix ISBN-13 validation edge case"
```

### 5. Push and Create PR

```bash
git push origin your-branch-name
```

Then open a Pull Request on GitHub.

## Code Style

### Python Style

- **Formatter**: Ruff (100 char line length)
- **Linter**: Ruff with strict rules
- **Type Checker**: mypy in strict mode

Run `make check` to verify compliance.

### Import Order

Imports are sorted automatically by ruff:
1. Standard library
2. Third-party packages
3. Local imports (`consearch.*`)

### Type Hints

All public functions must have type hints:

```python
async def resolve_book(isbn: str) -> BookRecord | None:
    ...
```

## Testing

### Test Structure

- `tests/unit/` - Unit tests (no external dependencies)
- `tests/integration/` - Integration tests (require Docker services)
- `tests/fixtures/` - JSON mock data

### Writing Tests

```python
import pytest
from consearch.resolution.books import OpenLibraryResolver

@pytest.mark.asyncio
async def test_resolve_by_isbn(mock_http_client):
    resolver = OpenLibraryResolver(client=mock_http_client)
    result = await resolver.resolve("9780134093413", IdentifierType.ISBN_13)
    assert result is not None
    assert result.title == "Clean Architecture"
```

### Running Tests

```bash
make test           # All tests
make test-unit      # Unit tests only (fast)
make test-integration  # Integration tests
make test-cov       # With coverage report
```

## Adding a New Resolver

1. **Create the resolver** in `src/consearch/resolution/books/` or `papers/`:

```python
from consearch.resolution.base import BaseResolver
from consearch.core.models import BookRecord
from consearch.core.types import SourceName

class NewSourceResolver(BaseResolver[BookRecord]):
    SOURCE = SourceName.NEW_SOURCE
    BASE_URL = "https://api.newsource.com"

    async def resolve(self, identifier: str, id_type: IdentifierType) -> BookRecord | None:
        # Implementation
        ...
```

2. **Add to SourceName enum** in `src/consearch/core/types.py`

3. **Register in registry** at `src/consearch/resolution/registry.py`

4. **Add tests** in `tests/unit/resolution/`

5. **Add fixtures** in `tests/fixtures/`

## Adding a New Identifier Type

1. Add to `IdentifierType` enum in `src/consearch/core/types.py`
2. Add detection logic in `src/consearch/detection/`
3. Add validation in `src/consearch/core/identifiers.py`
4. Update relevant resolvers to handle the new type
5. Add tests

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass (`make test`)
- [ ] Code style checks pass (`make check`)
- [ ] New code has type hints
- [ ] Tests added for new functionality
- [ ] Documentation updated if needed

### PR Description

- Clearly describe what the PR does
- Reference related issues
- Include testing instructions if not obvious

### Review Process

1. Automated CI checks must pass
2. At least one maintainer review required
3. Address review feedback
4. Squash and merge when approved

## Release Process

Releases are automated via GitHub Actions when a version tag is pushed:

```bash
# Update version in pyproject.toml
# Commit the change
git tag v0.2.0
git push origin v0.2.0
```

This triggers:
1. Build of distribution packages
2. Upload to PyPI
3. GitHub Release creation

## Questions?

- Open a [Discussion](https://github.com/sashankaryal/consearch/discussions) for questions
- Open an [Issue](https://github.com/sashankaryal/consearch/issues) for bugs or feature requests

Thanks for contributing!
