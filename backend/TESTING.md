# Testing Guide

## Quick Start

All commands should be run from `/reportflow/backend` directory.

### Prerequisites

- Docker compose services running: `cd reportflow && docker compose up`
- For shell script: `jq` installed on host machine

## Testing Options

### 1. Quick End-to-End Test (Recommended for Manual Testing)

**Bash script that runs from your host machine** - simulates a real client

```bash
make test-flow
```

This script:

- ✅ Runs outside Docker (tests API from external perspective)
- ✅ Creates user, submits job, tests idempotency, polls completion, downloads PDF
- ✅ Colorized output with progress indicators
- ✅ Downloads actual PDF file to current directory
- ✅ Great for quick smoke testing after changes

**Requirements:** `jq` must be installed on host

### 2. Integration Tests (Pytest)

**Python tests that run inside Docker container** - uses real database/workers

```bash
make test-integration
```

Or run specific test:

```bash
docker compose exec api uv run pytest tests/integration/test_full_flow.py -v
```

This approach:

- ✅ Runs inside Docker container (has DB access)
- ✅ Uses real database, Celery workers, Redis, and MinIO
- ✅ Tests actual async job processing with real workers
- ✅ Tests all endpoints comprehensively
- ✅ Best for validating full system integration
- ✅ Generates coverage reports
- ⚠️ Creates test data in the real database (uses unique timestamps to avoid conflicts)

### 3. Unit Tests

**Fast, isolated tests with mocked dependencies**

```bash
make test-unit
```

### 4. All Tests with Coverage

```bash
make test-coverage
```

Generates HTML coverage report at `htmlcov/index.html`

## Manual Testing with curl

If you prefer manual curl commands:

```bash
# 1. Register
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","tenant_name":"TestCorp"}' | jq .

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' | jq -r '.access_token')

# 3. Submit report
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/reports \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "sales_summary",
    "priority": 5,
    "idempotency_key": "unique-key-123",
    "filters": {"region": "EMEA"}
  }' | jq -r '.job_id')

# 4. Check status
curl -s http://localhost:8000/api/v1/reports/$JOB_ID \
  -H "Authorization: Bearer $TOKEN" | jq .

# 5. Download (once completed)
curl -L -o report.pdf \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/reports/$JOB_ID/download"
```

## Comparison

| Method                  | Runs In   | Best For               | Speed     | Real DB | Real Workers | Real Files |
| ----------------------- | --------- | ---------------------- | --------- | ------- | ------------ | ---------- |
| `make test-flow`        | Host      | Quick smoke test       | Slow      | ✅      | ✅           | ✅         |
| `make test-integration` | Container | Full system validation | Slow      | ✅      | ✅           | ✅         |
| `make test-unit`        | Container | TDD, fast feedback     | Very fast | ❌      | ❌           | ❌         |
| Manual curl             | Host      | Debugging, exploration | Slow      | ✅      | ✅           | ✅         |

## Other Useful Commands

```bash
# Open Python shell inside container
make shell

# Run linter
make lint

# Format code
make format

# Create migration
make migrate-create MSG="add new column"

# Apply migrations
make migrate

# Seed demo data
make seed

# Clean generated files
make clean
```

## Troubleshooting

### "connection refused" errors

- Ensure Docker services are running: `docker compose ps`
- Check API logs: `docker compose logs -f api`

### "Could not resolve host: minio"

- This was fixed by adding `MINIO_PUBLIC_ENDPOINT=http://localhost:9000` to `.env`
- Restart services: `docker compose restart`

### Integration tests fail with DB connection errors

- Ensure you're running tests inside the container: `docker compose exec api uv run pytest`
- Not from your host: ❌ `uv run pytest`

### Shell script fails with "command not found: jq"

- Install jq:
  - macOS: `brew install jq`
  - Ubuntu: `sudo apt-get install jq`
  - Or run pytest integration tests instead
