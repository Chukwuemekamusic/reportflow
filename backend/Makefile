.PHONY: test test-unit test-integration test-flow test-coverage help

# Default target
help:
	@echo "ReportFlow Backend - Available Commands"
	@echo "========================================"
	@echo "make test              - Run all tests (unit + integration)"
	@echo "make test-unit         - Run unit tests only"
	@echo "make test-integration  - Run integration tests only"
	@echo "make test-flow         - Run end-to-end flow test (shell script)"
	@echo "make test-coverage     - Run tests with coverage report"
	@echo "make migrate           - Apply database migrations"
	@echo "make migrate-create    - Create new migration (MSG='description')"
	@echo "make seed              - Seed database with demo data"
	@echo "make shell             - Open Python REPL with app context"
	@echo "make lint              - Run ruff linter"
	@echo "make format            - Format code with ruff"
	@echo "make clean             - Clean generated files"

# Testing
test:
	docker compose exec api uv run pytest

test-unit:
	docker compose exec api uv run pytest tests/unit/

test-integration:
	docker compose exec api uv run pytest tests/integration/

test-flow:
	@chmod +x scripts/test_flow.sh
	@./scripts/test_flow.sh

test-coverage:
	docker compose exec api uv run pytest --cov=app --cov-report=html --cov-report=term-missing

# Database
migrate:
	docker compose exec api uv run alembic upgrade head

migrate-create:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Please provide a message with MSG='description'"; \
		echo "Example: make migrate-create MSG='add user table'"; \
		exit 1; \
	fi
	docker compose exec api uv run alembic revision --autogenerate -m "$(MSG)"

seed:
	docker compose exec api uv run python -m app.db.seed

# Development
shell:
	docker compose exec api uv run python

lint:
	docker compose exec api uv run ruff check app/ tests/

format:
	docker compose exec api uv run ruff format app/ tests/
	docker compose exec api uv run ruff check --fix app/ tests/

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	rm -f report-*.pdf


# Docker restart
restart:
	docker compose restart

# Docker full-restart (dynamic rebuild where container name could be added as an argument)
full-restart:
	docker compose down
	docker compose up --build
