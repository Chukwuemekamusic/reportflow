#!/bin/bash
set -e

# ============================================================================
# DLQ (Dead Letter Queue) Testing Script
# ============================================================================
#
# PURPOSE:
# Tests the complete retry + DLQ flow by forcing tasks to fail and verifying:
# - Exponential backoff retry timing (30s → 120s → 480s)
# - on_retry() callback fires and updates DB retry_count
# - on_failure() callback fires after max retries exhausted
# - Failed job gets inserted into dead_letter_queue table with full traceback
# - Error message captured in report_jobs.error_message
#
# ============================================================================
# SETUP BEFORE RUNNING:
# ============================================================================
#
# 1. Add failure trigger to backend/app/workers/tasks/sales_summary.py
#    (Insert at line 31, right after "try:" block starts):
#
#    import os
#    if os.getenv("FORCE_TASK_FAILURE") == "1":
#        raise RuntimeError("🔴 Simulated failure for DLQ testing")
#
# 2. Add environment variable to docker-compose.yml
#    (Under worker-default service, add to environment section):
#
#    environment:
#      FORCE_TASK_FAILURE: "1"
#
# 3. Restart worker to apply changes:
#
#    docker compose up -d --force-recreate worker-default
#
# 4. Update TEST_EMAIL and TEST_PASSWORD below to match your test user
#
# ============================================================================
# EXPECTED BEHAVIOR (Total time: ~10-11 minutes):
# ============================================================================
#
# - Initial attempt fails immediately
# - Retry 1 after 30 seconds
# - Retry 2 after 120 seconds (2 minutes)
# - Retry 3 after 480 seconds (8 minutes)
# - After retry 3 fails → job status=failed + DLQ entry created
#
# Watch logs for pattern:
# [job_id] sales_summary failed → on_retry → retry: Retry in 30s
# [job_id] sales_summary failed → on_retry → retry: Retry in 120s
# [job_id] sales_summary failed → on_retry → retry: Retry in 480s
# [job_id] on_failure → INSERT INTO dead_letter_queue
#
# ============================================================================
# CLEANUP AFTER TESTING:
# ============================================================================
#
# 1. Remove the failure trigger code from sales_summary.py
# 2. Remove FORCE_TASK_FAILURE env var from docker-compose.yml
# 3. Restart worker:
#
#    docker compose restart worker-default
#
# ============================================================================
# VERIFY RESULTS:
# ============================================================================
#
# Check DLQ entries:
# docker compose exec db psql -U reportflow -c \
#   "SELECT job_id, retry_count, resolved, last_error_at
#    FROM dead_letter_queue ORDER BY last_error_at DESC LIMIT 5;"
#
# Check job status:
# docker compose exec db psql -U reportflow -c \
#   "SELECT id, status, retry_count, error_message
#    FROM report_jobs WHERE id = '<job_id>';"
#
# ============================================================================

export TEST_EMAIL="admin@example.com"
export TEST_PASSWORD="your-password"

EMAIL="${TEST_EMAIL}"
PASSWORD="${TEST_PASSWORD}"
API_BASE="http://localhost:8000/api/v1"

echo "🔴 DLQ Testing Script - Force Task Failure"
echo "=========================================="
echo ""

# Change to the reportflow directory
# cd /Users/emekaanyaegbunam/Workspace/python/reportFlow/reportflow

# # Step 1: Restart worker with failure flag
# echo "Step 1: Restarting worker-default with FORCE_TASK_FAILURE=1..."
# docker compose up -d --force-recreate worker-default
# echo "✅ Worker restarted"
# echo ""

# Wait for worker to be ready
echo "Waiting 5 seconds for worker to initialize..."
sleep 5
echo ""

# Step 2: Get auth token
echo "Step 2: Getting auth token..."
TOKEN=$(curl -s -X POST ${API_BASE}/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Failed to get auth token. Make sure:"
  echo "   - Services are running: docker compose up -d"
  echo "   - DB is seeded: docker compose exec api uv run python -m app.db.seed"
  exit 1
fi

echo "✅ Got token: ${TOKEN:0:20}..."
echo ""

# Step 3: Submit job
echo "Step 3: Submitting sales_summary job (will fail 3 times)..."
JOB_ID=$(curl -s -X POST ${API_BASE}/reports \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "sales_summary",
    "priority": 5,
    "filters": {}
  }' | jq -r .job_id)

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
  echo "❌ Failed to submit job"
  exit 1
fi

echo "✅ Job submitted: $JOB_ID"
echo ""

# Step 4: Watch logs
echo "Step 4: Watching worker logs (will show 3 retry attempts)..."
echo "Press Ctrl+C after you see all 3 retries fail"
echo "Expected pattern: FAILURE → retry 1 (30s) → retry 2 (120s) → retry 3 (480s) → DLQ"
echo "────────────────────────────────────────────────────────────────────────"
docker compose logs -f worker-default | grep --color=always -E "retry|FAILURE|$JOB_ID|Simulated"

# Note: User will Ctrl+C the above, so the script continues in the background
# We'll add final check commands that they can run manually
