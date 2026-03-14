#!/bin/bash
# End-to-end test script - runs from HOST machine (outside Docker)
# Tests the API as an external client would via curl
# Requires: docker compose services running, jq installed
set -e  # Exit on any error

API_BASE="http://localhost:8000/api/v1"
TIMESTAMP=$(date +%s)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ReportFlow End-to-End Test${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Step 1: Register user
echo -e "${YELLOW}[1/6] Registering user...${NC}"
REGISTER_RESPONSE=$(curl -s -X POST ${API_BASE}/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test-${TIMESTAMP}@example.com\",\"password\":\"testpass123\",\"tenant_name\":\"TestTenant-${TIMESTAMP}\"}")

echo "$REGISTER_RESPONSE" | jq .
USER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.id')
echo -e "${GREEN}✓ User created: ${USER_ID}${NC}\n"

# Step 2: Login and get token
echo -e "${YELLOW}[2/6] Logging in...${NC}"
TOKEN_RESPONSE=$(curl -s -X POST ${API_BASE}/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test-${TIMESTAMP}@example.com\",\"password\":\"testpass123\"}")

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
echo -e "${GREEN}✓ Token obtained${NC}\n"

# Step 3: Submit report job
echo -e "${YELLOW}[3/6] Submitting sales_summary report...${NC}"
IDEMPOTENCY_KEY="test-job-${TIMESTAMP}"
JOB_RESPONSE=$(curl -s -X POST ${API_BASE}/reports \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report_type\": \"sales_summary\",
    \"priority\": 5,
    \"idempotency_key\": \"${IDEMPOTENCY_KEY}\",
    \"filters\": {\"region\": \"EMEA\", \"status\": \"active\"}
  }")

echo "$JOB_RESPONSE" | jq .
JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.job_id')
echo -e "${GREEN}✓ Job submitted: ${JOB_ID}${NC}\n"

# Step 4: Test idempotency
echo -e "${YELLOW}[4/6] Testing idempotency (resubmitting same key)...${NC}"
IDEMPOTENT_RESPONSE=$(curl -s -X POST ${API_BASE}/reports \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report_type\": \"sales_summary\",
    \"priority\": 5,
    \"idempotency_key\": \"${IDEMPOTENCY_KEY}\",
    \"filters\": {\"region\": \"EMEA\", \"status\": \"active\"}
  }")

RETURNED_JOB_ID=$(echo "$IDEMPOTENT_RESPONSE" | jq -r '.job_id')
if [ "$RETURNED_JOB_ID" == "$JOB_ID" ]; then
  echo -e "${GREEN}✓ Idempotency working: same job returned${NC}\n"
else
  echo -e "\033[0;31m✗ Idempotency failed: different job returned${NC}\n"
fi

# Step 5: Poll for completion
echo -e "${YELLOW}[5/6] Polling for job completion (max 60s)...${NC}"
for i in {1..30}; do
  sleep 2
  STATUS_RESPONSE=$(curl -s -X GET "${API_BASE}/reports/${JOB_ID}" \
    -H "Authorization: Bearer ${TOKEN}")

  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress')

  echo -e "  Status: ${STATUS} | Progress: ${PROGRESS}%"

  if [ "$STATUS" == "completed" ]; then
    echo -e "${GREEN}✓ Job completed!${NC}\n"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo -e "\033[0;31m✗ Job failed${NC}"
    echo "$STATUS_RESPONSE" | jq .
    exit 1
  fi
done

if [ "$STATUS" != "completed" ]; then
  echo -e "\033[0;31m✗ Job did not complete within timeout${NC}"
  exit 1
fi

# Step 6: Download report
echo -e "${YELLOW}[6/6] Downloading report...${NC}"
OUTPUT_FILE="report-${JOB_ID}.pdf"
curl -L -o "${OUTPUT_FILE}" \
  -H "Authorization: Bearer ${TOKEN}" \
  "${API_BASE}/reports/${JOB_ID}/download"

FILE_SIZE=$(stat -f%z "${OUTPUT_FILE}" 2>/dev/null || stat -c%s "${OUTPUT_FILE}" 2>/dev/null)
echo -e "${GREEN}✓ Report downloaded: ${OUTPUT_FILE} (${FILE_SIZE} bytes)${NC}\n"

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "User ID:      ${USER_ID}"
echo -e "Job ID:       ${JOB_ID}"
echo -e "Report File:  ${OUTPUT_FILE}"
echo -e "File Size:    ${FILE_SIZE} bytes"
echo -e "${GREEN}\n✓ All tests passed!${NC}\n"
