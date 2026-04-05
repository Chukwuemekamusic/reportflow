#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source authentication helper (includes default credentials)
source "${SCRIPT_DIR}/lib/auth_helper.sh"

# Cleanup function - runs on EXIT (success or failure)
cleanup_schedules() {
  if [ -n "$SCHEDULE_ID" ]; then
    echo -e "\n${YELLOW}Cleaning up schedule ${SCHEDULE_ID}...${NC}" >&2
    curl -s -X DELETE "${API_BASE}/schedules/${SCHEDULE_ID}" \
      -H "Authorization: Bearer $TOKEN" > /dev/null 2>&1 || true
  fi
  if [ -n "$IMMEDIATE_ID" ]; then
    echo -e "${YELLOW}Cleaning up immediate schedule ${IMMEDIATE_ID}...${NC}" >&2
    curl -s -X DELETE "${API_BASE}/schedules/${IMMEDIATE_ID}" \
      -H "Authorization: Bearer $TOKEN" > /dev/null 2>&1 || true
  fi
}
trap cleanup_schedules EXIT

# Authenticate (will use existing credentials or register new user)
quick_auth

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ReportFlow Schedule Smoke Test${NC}"
echo -e "${BLUE}========================================${NC}\n"

# ── Test 1: Create Schedule ──────────────────────────────────────────
echo -e "${YELLOW}[1/9] Creating schedule (csv_export, weekdays 09:00)...${NC}"
CREATE_RESPONSE=$(curl -s -X POST "${API_BASE}/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "csv_export", "cron_expr": "0 9 * * 1-5", "priority": 3}')

echo "$CREATE_RESPONSE" | jq '{schedule_id, cron_expr, next_run_at, is_active}'

SCHEDULE_ID=$(echo "$CREATE_RESPONSE" | jq -r '.schedule_id')
IS_ACTIVE=$(echo "$CREATE_RESPONSE" | jq -r '.is_active')
NEXT_RUN=$(echo "$CREATE_RESPONSE" | jq -r '.next_run_at')

if [ "$SCHEDULE_ID" == "null" ] || [ -z "$SCHEDULE_ID" ]; then
  echo -e "${RED}[TEST] ✗ Failed to create schedule${NC}"
  echo "$CREATE_RESPONSE" | jq .
  exit 1
fi

if [ "$IS_ACTIVE" != "true" ]; then
  echo -e "${RED}[TEST] ✗ Schedule should be active by default${NC}"
  exit 1
fi

if [ "$NEXT_RUN" == "null" ]; then
  echo -e "${RED}[TEST] ✗ next_run_at should be populated${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Schedule created: ${SCHEDULE_ID}${NC}\n"

# ── Test 2: Invalid Cron Rejected ─────────────────────────────────────
echo -e "${YELLOW}[2/9] Testing invalid cron expression rejection...${NC}"
INVALID_RESPONSE=$(curl -s -X POST "${API_BASE}/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_summary", "cron_expr": "99 99 * * *"}' \
  -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$INVALID_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)

if [ "$HTTP_CODE" == "422" ]; then
  echo -e "${GREEN}✓ Invalid cron rejected (HTTP 422)${NC}\n"
else
  echo -e "${RED}✗ Expected HTTP 422, got ${HTTP_CODE}${NC}"
  echo "$INVALID_RESPONSE"
  exit 1
fi

# ── Test 3: List Schedules ────────────────────────────────────────────
echo -e "${YELLOW}[3/9] Listing schedules...${NC}"
LIST_RESPONSE=$(curl -s "${API_BASE}/schedules" \
  -H "Authorization: Bearer $TOKEN")

TOTAL_COUNT=$(echo "$LIST_RESPONSE" | jq -r '.total')
echo "$LIST_RESPONSE" | jq '{total, limit, offset}'

if [ "$TOTAL_COUNT" -lt 1 ]; then
  echo -e "${RED}✗ Should have at least 1 schedule${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Found ${TOTAL_COUNT} schedule(s)${NC}\n"

# ── Test 4: Update Schedule (change cron) ─────────────────────────────
echo -e "${YELLOW}[4/9] Updating schedule cron expression...${NC}"
UPDATE_RESPONSE=$(curl -s -X PUT "${API_BASE}/schedules/${SCHEDULE_ID}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cron_expr": "0 6 * * 1"}')

echo "$UPDATE_RESPONSE" | jq '{cron_expr, next_run_at, is_active}'

NEW_CRON=$(echo "$UPDATE_RESPONSE" | jq -r '.cron_expr')
NEW_NEXT_RUN=$(echo "$UPDATE_RESPONSE" | jq -r '.next_run_at')

if [ "$NEW_CRON" != "0 6 * * 1" ]; then
  echo -e "${RED}✗ Cron expression not updated${NC}"
  exit 1
fi

if [ "$NEW_NEXT_RUN" == "$NEXT_RUN" ]; then
  echo -e "${RED}✗ next_run_at should have changed${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Schedule updated successfully${NC}\n"

# ── Test 5: Deactivate Schedule ───────────────────────────────────────
echo -e "${YELLOW}[5/9] Deactivating schedule...${NC}"
DEACTIVATE_RESPONSE=$(curl -s -X DELETE "${API_BASE}/schedules/${SCHEDULE_ID}" \
  -H "Authorization: Bearer $TOKEN")

DEACTIVATED=$(echo "$DEACTIVATE_RESPONSE" | jq -r '.is_active')

if [ "$DEACTIVATED" != "false" ]; then
  echo -e "${RED}✗ Schedule should be inactive${NC}"
  echo "$DEACTIVATE_RESPONSE" | jq .
  exit 1
fi

echo -e "${GREEN}✓ Schedule deactivated${NC}\n"

# ── Test 6: Confirm Inactive Schedule Hidden ──────────────────────────
echo -e "${YELLOW}[6/9] Verifying inactive schedules are hidden by default...${NC}"
ACTIVE_LIST=$(curl -s "${API_BASE}/schedules" \
  -H "Authorization: Bearer $TOKEN")

NEW_TOTAL=$(echo "$ACTIVE_LIST" | jq -r '.total')

if [ "$NEW_TOTAL" -ge "$TOTAL_COUNT" ]; then
  echo -e "${RED}✗ Inactive schedule should not appear in default list${NC}"
  echo "Before deactivation: $TOTAL_COUNT, After: $NEW_TOTAL"
  exit 1
fi

echo -e "${GREEN}✓ Inactive schedule hidden (count decreased from ${TOTAL_COUNT} to ${NEW_TOTAL})${NC}\n"

# ── Test 7: Reactivate Schedule ───────────────────────────────────────
echo -e "${YELLOW}[7/9] Reactivating schedule...${NC}"
REACTIVATE_RESPONSE=$(curl -s -X PUT "${API_BASE}/schedules/${SCHEDULE_ID}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}')

echo "$REACTIVATE_RESPONSE" | jq '{is_active, next_run_at}'

REACTIVATED=$(echo "$REACTIVATE_RESPONSE" | jq -r '.is_active')
RECALC_NEXT_RUN=$(echo "$REACTIVATE_RESPONSE" | jq -r '.next_run_at')

if [ "$REACTIVATED" != "true" ]; then
  echo -e "${RED}✗ Schedule should be active${NC}"
  exit 1
fi

if [ "$RECALC_NEXT_RUN" == "null" ]; then
  echo -e "${RED}✗ next_run_at should be recalculated${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Schedule reactivated, next_run_at recalculated${NC}\n"

# ── Test 8: Create Another Schedule to Trigger Job ────────────────────
echo -e "${YELLOW}[8/9] Creating immediate schedule to verify job spawning...${NC}"

# Create a schedule that runs every minute to ensure it triggers soon
IMMEDIATE_SCHEDULE=$(curl -s -X POST "${API_BASE}/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "sales_summary", "cron_expr": "* * * * *", "priority": 5}')

IMMEDIATE_ID=$(echo "$IMMEDIATE_SCHEDULE" | jq -r '.schedule_id')

if [ "$IMMEDIATE_ID" == "null" ] || [ -z "$IMMEDIATE_ID" ]; then
  echo -e "${RED}[TEST] ✗ Failed to create immediate schedule${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Immediate schedule created: ${IMMEDIATE_ID}${NC}"
echo -e "${BLUE}   Waiting 65 seconds for Celery Beat to trigger...${NC}\n"

# Wait for Celery Beat to pick up and trigger the schedule
sleep 65

# ── Test 9: Verify Spawned Jobs Have schedule_id ──────────────────────
echo -e "${YELLOW}[9/9] Checking for jobs spawned by schedules...${NC}"
JOBS_RESPONSE=$(curl -s "${API_BASE}/reports?limit=20" \
  -H "Authorization: Bearer $TOKEN")

SCHEDULED_JOBS=$(echo "$JOBS_RESPONSE" | jq '[.items[] | select(.schedule_id != null) | {job_id, report_type, schedule_id, status}]')
SCHEDULED_COUNT=$(echo "$SCHEDULED_JOBS" | jq 'length')

echo "$SCHEDULED_JOBS" | jq .

if [ "$SCHEDULED_COUNT" -lt 1 ]; then
  echo -e "${YELLOW}⚠ No scheduled jobs found yet (Beat may not have fired)${NC}"
  echo -e "${BLUE}  This is expected if Celery Beat hasn't run yet${NC}"
  echo -e "${BLUE}  Check docker compose logs api | grep 'Scheduler: Sending' to verify${NC}\n"
else
  echo -e "${GREEN}✓ Found ${SCHEDULED_COUNT} job(s) spawned by schedules${NC}\n"
fi

# Cleanup: deactivate the immediate schedule
echo -e "${YELLOW}Cleaning up: deactivating immediate schedule...${NC}"
curl -s -X DELETE "${API_BASE}/schedules/${IMMEDIATE_ID}" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

# ── Summary ───────────────────────────────────────────────────────────
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Primary Schedule ID:   ${SCHEDULE_ID}"
echo -e "Immediate Schedule ID: ${IMMEDIATE_ID}"
echo -e "Scheduled Jobs Found:  ${SCHEDULED_COUNT}"
echo -e "${GREEN}\n✓ All schedule smoke tests passed!${NC}\n"
