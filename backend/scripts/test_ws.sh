#!/bin/bash
# WebSocket streaming test - connects to job progress stream
# Usage: ./scripts/test_ws.sh [report_type] [priority]
#   report_type: sales_summary, csv_export, or pdf_report (default: pdf_report)
#   priority: 1-10 (default: 3)
set -e  # Exit on any error

# Set default values for email and password
export TEST_EMAIL="admin@example.com"
export TEST_PASSWORD="your-password"

API_BASE="http://localhost:8000/api/v1"
REPORT_TYPE="${1:-pdf_report}"
PRIORITY="${2:-3}"
EMAIL="${TEST_EMAIL}"
PASSWORD="${TEST_PASSWORD}"
TIMESTAMP=$(date +%s)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ReportFlow WebSocket Stream Test${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check dependencies
for cmd in curl jq wscat; do
  if ! command -v $cmd &> /dev/null; then
    echo -e "${RED}Error: $cmd not found. Please install it first.${NC}"
    exit 1
  fi
done

echo -e "${CYAN}Configuration:${NC}"
echo -e "  Report Type: ${REPORT_TYPE}"
echo -e "  Priority:    ${PRIORITY}"
echo -e "  User:        ${EMAIL}\n"

# Step 1: Login and get token
echo -e "${YELLOW}[1/3] Authenticating...${NC}"
TOKEN_RESPONSE=$(curl -s -X POST ${API_BASE}/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
  echo -e "${RED}✗ Authentication failed${NC}"
  echo "$TOKEN_RESPONSE" | jq .
  exit 1
fi

echo -e "${GREEN}✓ Token obtained${NC}\n"

# Step 2: Submit report job
echo -e "${YELLOW}[2/3] Submitting ${REPORT_TYPE} job...${NC}"
IDEMPOTENCY_KEY="test-ws-${TIMESTAMP}-$$"

JOB_RESPONSE=$(curl -s -X POST ${API_BASE}/reports \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report_type\": \"${REPORT_TYPE}\",
    \"priority\": ${PRIORITY},
    \"idempotency_key\": \"${IDEMPOTENCY_KEY}\",
    \"filters\": {
      \"start_date\": \"2024-01-01\",
      \"end_date\": \"2024-12-31\",
      \"region\": \"EMEA\"
    }
  }")

echo "$JOB_RESPONSE" | jq .
JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.job_id')

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
  echo -e "${RED}✗ Job submission failed${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Job created: ${JOB_ID}${NC}\n"

# Step 3: Connect to WebSocket stream
echo -e "${YELLOW}[3/3] Connecting to progress stream...${NC}"
echo -e "${CYAN}WebSocket URL: ws://localhost:8000/api/v1/reports/${JOB_ID}/stream${NC}"
echo -e "${CYAN}Press CTRL+C to disconnect${NC}\n"

# Format WebSocket output with timestamps and colors
wscat -c "ws://localhost:8000/api/v1/reports/${JOB_ID}/stream?token=${TOKEN}" 2>&1 | while IFS= read -r line; do
  TIMESTAMP=$(date '+%H:%M:%S')

  # Connection status
  if echo "$line" | grep -q "Connected"; then
    echo -e "${GREEN}[${TIMESTAMP}] ${line}${NC}"
    continue
  fi

  if echo "$line" | grep -q "Disconnected"; then
    echo -e "${YELLOW}[${TIMESTAMP}] ${line}${NC}"
    echo ""
    break
  fi

  # Parse JSON events
  if echo "$line" | jq -e . >/dev/null 2>&1; then
    EVENT=$(echo "$line" | jq -r '.event // "unknown"')
    PROGRESS=$(echo "$line" | jq -r '.progress // 0')
    STAGE=$(echo "$line" | jq -r '.stage // ""')

    case "$EVENT" in
      progress)
        # Create progress bar
        FILLED=$((PROGRESS / 5))
        EMPTY=$((20 - FILLED))
        BAR=$(printf "%${FILLED}s" | tr ' ' '█')$(printf "%${EMPTY}s" | tr ' ' '░')
        echo -e "${CYAN}[${TIMESTAMP}]${NC} ${YELLOW}${PROGRESS}%${NC} [${BAR}] ${BLUE}${STAGE}${NC}"
        ;;
      completed)
        echo -e "${GREEN}[${TIMESTAMP}] ✓ Job completed!${NC}"
        DOWNLOAD_URL=$(echo "$line" | jq -r '.download_url // ""')
        if [ -n "$DOWNLOAD_URL" ] && [ "$DOWNLOAD_URL" != "null" ]; then
          echo -e "${GREEN}[${TIMESTAMP}]   Download URL: http://localhost:8000${DOWNLOAD_URL}${NC}"
        fi
        ;;
      failed)
        ERROR=$(echo "$line" | jq -r '.error // "Unknown error"')
        echo -e "${RED}[${TIMESTAMP}] ✗ Job failed: ${ERROR}${NC}"
        ;;
      queued|running)
        echo -e "${CYAN}[${TIMESTAMP}] Status: ${EVENT}${NC}"
        ;;
      *)
        echo -e "${CYAN}[${TIMESTAMP}]${NC} $(echo "$line" | jq -C '.')"
        ;;
    esac
  else
    # Non-JSON output
    echo -e "${CYAN}[${TIMESTAMP}]${NC} ${line}"
  fi
done

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Job ID: ${JOB_ID}"
echo -e "\nTo download the report:"
echo -e "  ${CYAN}curl -H \"Authorization: Bearer \${TOKEN}\" \\${NC}"
echo -e "    ${CYAN}\"${API_BASE}/reports/${JOB_ID}/download\" -o report.${REPORT_TYPE##*_}${NC}"
echo -e "\nTo check job status:"
echo -e "  ${CYAN}curl -H \"Authorization: Bearer \${TOKEN}\" \\${NC}"
echo -e "    ${CYAN}\"${API_BASE}/reports/${JOB_ID}\" | jq${NC}\n"
