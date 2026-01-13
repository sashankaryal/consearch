.PHONY: help install setup up down logs migrate migrate-new dev run stop test test-unit test-integration test-cov lint lint-fix format typecheck check clean

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Paths
VENV := .venv
VENV_BIN := $(VENV)/bin
PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip

# Server
PORT := 8766

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  $(BLUE)%-18s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ============================================================================
# Setup & Installation
# ============================================================================

install: ## Install dependencies (requires active venv)
	pip install -e ".[dev]"

$(VENV)/pyvenv.cfg:
	@echo "$(GREEN)Creating virtual environment...$(RESET)"
	python -m venv $(VENV)
	$(PIP) install --upgrade pip

.venv/.installed: $(VENV)/pyvenv.cfg pyproject.toml
	@echo "$(GREEN)Installing dependencies...$(RESET)"
	$(PIP) install -e ".[dev]"
	@touch .venv/.installed

.env:
	@echo "$(GREEN)Creating .env from template...$(RESET)"
	cp .env.example .env

setup: $(VENV)/pyvenv.cfg .venv/.installed .env ## Full setup: create venv, install deps, copy env template (idempotent)
	@echo ""
	@echo "$(GREEN)Setup complete!$(RESET) Activate your venv with:"
	@echo "  source .venv/bin/activate"

# ============================================================================
# Docker Services
# ============================================================================

up: ## Start Docker services (PostgreSQL, Redis, Meilisearch) (idempotent)
	@if docker-compose ps --status running 2>/dev/null | grep -q "postgres.*running" && \
	    docker-compose ps --status running 2>/dev/null | grep -q "redis.*running" && \
	    docker-compose ps --status running 2>/dev/null | grep -q "meilisearch.*running"; then \
		echo "$(GREEN)All services already running$(RESET)"; \
		docker-compose ps; \
	else \
		echo "$(GREEN)Starting services...$(RESET)"; \
		docker-compose up -d --wait; \
		docker-compose ps; \
	fi

down: ## Stop Docker services (idempotent)
	@if docker-compose ps -q 2>/dev/null | grep -q .; then \
		docker-compose down; \
	else \
		echo "$(YELLOW)No services running$(RESET)"; \
	fi

down-v: ## Stop Docker services and remove volumes
	docker-compose down -v

logs: ## View Docker service logs (use: make logs service=postgres)
	@if [ -z "$(service)" ]; then \
		docker-compose logs -f; \
	else \
		docker-compose logs -f $(service); \
	fi

ps: ## Show status of Docker services
	docker-compose ps

# ============================================================================
# Database
# ============================================================================

migrate: ## Run database migrations (idempotent - only applies pending)
	$(VENV_BIN)/alembic upgrade head

migrate-new: ## Create a new migration (use: make migrate-new msg="add users table")
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a migration message"; \
		echo "Usage: make migrate-new msg=\"your migration message\""; \
		exit 1; \
	fi
	$(VENV_BIN)/alembic revision --autogenerate -m "$(msg)"

migrate-down: ## Rollback last migration
	$(VENV_BIN)/alembic downgrade -1

migrate-history: ## Show migration history
	$(VENV_BIN)/alembic history

# ============================================================================
# Development Server
# ============================================================================

dev: up .venv/.installed ## Start development server (ensures services + venv ready)
	@if [ ! -f .env ]; then \
		echo "$(RED)Error: .env file not found$(RESET)"; \
		echo "Run 'cp .env.example .env' to create it"; \
		exit 1; \
	fi
	@echo "$(GREEN).env file loaded$(RESET)"
	$(VENV_BIN)/uvicorn consearch.api.app:app --reload --port $(PORT)

run: dev ## Alias for dev

stop: ## Stop the development server
	@PID=$$(lsof -ti :$(PORT) 2>/dev/null); \
	if [ -n "$$PID" ]; then \
		echo "$(YELLOW)Stopping server on port $(PORT) (PID: $$PID)$(RESET)"; \
		kill $$PID 2>/dev/null || kill -9 $$PID 2>/dev/null; \
		echo "$(GREEN)Server stopped$(RESET)"; \
	else \
		echo "$(YELLOW)No server running on port $(PORT)$(RESET)"; \
	fi

# ============================================================================
# Testing
# ============================================================================

test: ## Run all tests
	pytest

test-unit: ## Run unit tests only
	pytest tests/unit -v

test-integration: ## Run integration tests (requires Docker services)
	pytest tests/integration -v

test-cov: ## Run tests with coverage report
	pytest --cov=src/consearch --cov-report=html --cov-report=term
	@echo ""
	@echo "HTML coverage report: htmlcov/index.html"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	ptw -- -v

# ============================================================================
# Code Quality
# ============================================================================

lint: ## Run linter (ruff)
	ruff check src tests

lint-fix: ## Run linter with auto-fix
	ruff check --fix src tests

format: ## Format code (ruff)
	ruff format src tests

format-check: ## Check code formatting without changes
	ruff format --check src tests

typecheck: ## Run type checker (mypy)
	mypy src

check: lint format-check typecheck ## Run all checks (lint, format, typecheck)

# ============================================================================
# Pre-commit
# ============================================================================

hooks-install: ## Install pre-commit hooks (idempotent)
	@if [ -f .git/hooks/pre-commit ] && grep -q "pre-commit" .git/hooks/pre-commit 2>/dev/null; then \
		echo "$(GREEN)Pre-commit hooks already installed$(RESET)"; \
	else \
		pre-commit install; \
	fi

hooks-run: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# ============================================================================
# Utilities
# ============================================================================

clean: ## Clean up build artifacts and caches
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

reset: down-v clean ## Full reset: stop services, remove volumes, clean artifacts
	@echo "Reset complete. Run 'make setup && make up && make migrate' to start fresh."
