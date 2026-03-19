#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source authentication helper (includes default credentials)
source "${SCRIPT_DIR}/lib/auth_helper.sh"

# Authenticate (will use existing credentials or register new user)
quick_auth

# Submit a slow job (pdf_report) and cancel it while queued
echo -e "${YELLOW}[TEST] Submitting pdf_report job (low priority)...${NC}"
JOB=$(curl -s -X POST "${API_BASE}/reports" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"report_type":"pdf_report","priority":9,"filters":{}}' | jq -r .job_id)

echo -e "${GREEN}[TEST] ✓ Job submitted: ${JOB}${NC}"

sleep 1  # Give the job time to be queued but not yet picked up

echo -e "${YELLOW}[TEST] Cancelling job...${NC}"
CANCEL_STATUS=$(curl -s -X DELETE "${API_BASE}/reports/${JOB}" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$CANCEL_STATUS" | grep "HTTP_CODE" | cut -d: -f2)

if [ "$HTTP_CODE" == "204" ]; then
  echo -e "${GREEN}[TEST] ✓ Job cancelled (HTTP 204)${NC}"
else
  echo -e "${RED}[TEST] ✗ Cancel failed (HTTP ${HTTP_CODE})${NC}"
  echo "$CANCEL_STATUS"
fi

echo -e "${YELLOW}[TEST] Verifying job status...${NC}"
FINAL_STATUS=$(curl -s "${API_BASE}/reports/${JOB}" \
  -H "Authorization: Bearer $TOKEN" | jq -r .status)

if [ "$FINAL_STATUS" == "cancelled" ]; then
  echo -e "${GREEN}[TEST] ✓ Job status confirmed: cancelled${NC}"
else
  echo -e "${RED}[TEST] ✗ Unexpected status: ${FINAL_STATUS}${NC}"
  exit 1
fi

echo -e "\n${GREEN}✓ Job cancellation test passed!${NC}"