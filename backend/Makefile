.PHONY: test test-unit test-integration test-flow test-coverage help restart restart-worker restart-service rebuild rebuild-clean curl-register curl-test-token curl-create-token curl-new-token curl-csv-export curl-pdf-report curl-check-job curl-download-report curl-download-file curl-list-jobs check-user-role set-admin-role

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
	@echo "make check-user-role   - Check user role (EMAIL='admin@example.com')"
	@echo "make set-admin-role    - Set user as admin (EMAIL='admin@example.com')"
	@echo "make shell             - Open Python REPL with app context"
	@echo "make lint              - Run ruff linter"
	@echo "make format            - Format code with ruff"
	@echo "make clean             - Clean generated files"
	@echo "make restart           - Restart all services"
	@echo "make restart-worker   - Restart Celery workers"
	@echo "make restart-service   - Restart specific service (SERVICE=api|db|redis|etc)"
	@echo "make rebuild           - Rebuild and restart all services (detached)"
	@echo "make rebuild-clean     - Clean rebuild (removes volumes, no cache)"
	@echo "make curl-register     - Register a new user"
	@echo "make curl-test-token   - Test authentication token"
	@echo "make curl-create-token - Create a new authentication token"
	@echo "make curl-csv-export   - Submit a CSV export job"
	@echo "make curl-pdf-report   - Submit a PDF report job"
	@echo "make curl-check-job    - Check job status (JOB_ID=<uuid>)"
	@echo "make curl-download-report - Get download URL (JOB_ID=<uuid>)"
	@echo "make curl-download-file - Download report file (JOB_ID=<uuid>)"
	@echo "make curl-list-jobs    - List all jobs"

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

check-user-role:
	@if [ -z "$(EMAIL)" ]; then \
		echo "Error: Please provide EMAIL='user@example.com'"; \
		exit 1; \
	fi
	docker compose exec api sh -c "cd /app && PYTHONPATH=/app uv run python scripts/check_user_role.py '$(EMAIL)'"

set-admin-role:
	@if [ -z "$(EMAIL)" ]; then \
		echo "Error: Please provide EMAIL='user@example.com'"; \
		exit 1; \
	fi
	docker compose exec api sh -c "cd /app && PYTHONPATH=/app uv run python scripts/set_admin_role.py '$(EMAIL)'"

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


# Docker Operations
restart:
	@echo "Restarting all services..."
	docker compose restart
	@echo "Services restarted successfully!"

restart-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Error: Please specify a service with SERVICE=<name>"; \
		echo "Example: make restart-service SERVICE=api"; \
		echo "Available services: api, db, redis, minio, worker, beat"; \
		exit 1; \
	fi
	@echo "Restarting $(SERVICE)..."
	docker compose restart $(SERVICE)
	@echo "$(SERVICE) restarted successfully!"

restart-worker:
	@echo "Restarting Celery workers..."
	docker compose restart worker-default worker-high worker-low
	@echo "Workers restarted successfully!"

rebuild:
	@echo "Rebuilding and restarting all services (detached mode)..."
	docker compose down
	docker compose up --build -d
	@echo "Services rebuilt and started successfully!"
	@echo "Use 'docker compose logs -f' to view logs"

rebuild-clean:
	@echo "WARNING: This will remove all volumes and rebuild from scratch!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	docker compose down -v
	docker compose build --no-cache
	docker compose up -d
	@echo "Clean rebuild complete!"
	@echo "Don't forget to run: make migrate && make seed"


# curl commands
curl-register:
	@curl -s -X POST http://localhost:8000/api/v1/auth/register \
		-H "Content-Type: application/json" \
		-d '{"email":"admin@example.com","password":"your-password","tenant_name":"TestCorp"}' | jq .
curl-test-token:
	@curl -s -o /dev/null -w "%{http_code}\n" \
        -H "Authorization: Bearer $(TOKEN)" \
        http://localhost:8000/api/v1/reports

curl-create-token:
	@curl -s -X POST http://localhost:8000/api/v1/auth/token \
		-H "Content-Type: application/json" \
		-d '{"email":"admin@example.com","password":"your-password"}' | jq .

curl-new-token:
	@$(MAKE) curl-create-token | jq -r ".access_token"
	
curl-csv-export:
	@curl -s -X POST http://localhost:8000/api/v1/reports \
		-H "Authorization: Bearer $$TOKEN" \
		-H "Content-Type: application/json" \
		-d '{ \
			"report_type": "csv_export", \
			"priority": 5, \
			"filters": {"status": "active", "columns": ["customer_name", "plan_name", "mrr", "region"]} \
		}' | jq '{job_id, report_type, status, progress}'

curl-pdf-report:
	@curl -s -X POST http://localhost:8000/api/v1/reports \
		-H "Authorization: Bearer $$TOKEN" \
		-H "Content-Type: application/json" \
		-d '{ \
			"report_type": "pdf_report", \
			"priority": 5, \
			"filters": {"status": "active"} \
		}' | jq '{job_id, report_type, status, progress}'

curl-check-job:
	@if [ -z "$(JOB_ID)" ]; then \
		echo "Error: Please provide JOB_ID=<uuid>"; \
		echo "Example: make curl-check-job JOB_ID=ca392489-ca81-4dc0-8377-18c76cc88440"; \
		exit 1; \
	fi
	@curl -s -H "Authorization: Bearer $$TOKEN" \
		http://localhost:8000/api/v1/reports/$(JOB_ID) | jq

curl-download-report:
	@if [ -z "$(JOB_ID)" ]; then \
		echo "Error: Please provide JOB_ID=<uuid>"; \
		exit 1; \
	fi
	@echo "Download URL:"
	@curl -s -w "%{redirect_url}\n" -o /dev/null -H "Authorization: Bearer $$TOKEN" \
		http://localhost:8000/api/v1/reports/$(JOB_ID)/download

curl-download-file:
	@if [ -z "$(JOB_ID)" ]; then \
		echo "Error: Please provide JOB_ID=<uuid>"; \
		exit 1; \
	fi
	@curl -L -H "Authorization: Bearer $$TOKEN" \
		http://localhost:8000/api/v1/reports/$(JOB_ID)/download \
		-o report-$(JOB_ID).pdf
	@echo "Downloaded to: report-$(JOB_ID).pdf"

curl-list-jobs:
	@curl -s -H "Authorization: Bearer $$TOKEN" \
		http://localhost:8000/api/v1/reports?limit=100 | jq '.items[] | {job_id, report_type, status, progress}'