#!/bin/bash
# Authentication helper for ReportFlow test scripts
# Source this file in your test scripts: source scripts/lib/auth_helper.sh

# Default API base URL (can be overridden before sourcing)
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"

# Default test credentials (can be overridden via environment variables)
export TEST_EMAIL="${TEST_EMAIL:-admin@example.com}"
export TEST_PASSWORD="${TEST_PASSWORD:-your-password}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Register a new user with timestamp-based unique email
# Sets: USER_ID, USER_EMAIL, USER_PASSWORD, TOKEN
register_new_user() {
    local tenant_name="${1:-TestTenant}"

    TIMESTAMP=$(date +%s)
    USER_EMAIL="test-${TIMESTAMP}@example.com"
    USER_PASSWORD="testpass123"

    echo -e "${YELLOW}[AUTH] Registering new user: ${USER_EMAIL}${NC}" >&2

    REGISTER_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${USER_EMAIL}\",\"password\":\"${USER_PASSWORD}\",\"tenant_name\":\"${tenant_name}-${TIMESTAMP}\"}")

    USER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.id')

    if [ "$USER_ID" == "null" ] || [ -z "$USER_ID" ]; then
        echo -e "${RED}[AUTH] Registration failed${NC}" >&2
        echo "$REGISTER_RESPONSE" | jq . >&2
        return 1
    fi

    echo -e "${GREEN}[AUTH] ✓ User registered: ${USER_ID}${NC}" >&2

    # Automatically login after registration
    login_user "$USER_EMAIL" "$USER_PASSWORD"
}

# Login with existing credentials or provided email/password
# Sets: TOKEN
# Usage:
#   login_user                              # Uses TEST_EMAIL and TEST_PASSWORD env vars
#   login_user "user@example.com" "pass123" # Uses provided credentials
login_user() {
    local email="${1:-${TEST_EMAIL}}"
    local password="${2:-${TEST_PASSWORD}}"

    if [ -z "$email" ] || [ -z "$password" ]; then
        echo -e "${RED}[AUTH] Error: Email and password required${NC}" >&2
        echo "[AUTH] Usage: login_user <email> <password>" >&2
        echo "[AUTH]    OR: Set TEST_EMAIL and TEST_PASSWORD env vars" >&2
        return 1
    fi

    echo -e "${YELLOW}[AUTH] Logging in as: ${email}${NC}" >&2

    TOKEN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/token" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${email}\",\"password\":\"${password}\"}")

    TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

    if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
        echo -e "${RED}[AUTH] Login failed${NC}" >&2
        echo "$TOKEN_RESPONSE" | jq . >&2
        return 1
    fi

    echo -e "${GREEN}[AUTH] ✓ Token obtained${NC}" >&2
    export TOKEN
}

# Quick auth for test scripts - tries existing user first, registers if fails
# Uses TEST_EMAIL and TEST_PASSWORD if set, otherwise creates new user
# Sets: TOKEN (and USER_ID, USER_EMAIL, USER_PASSWORD if new user)
quick_auth() {
    if [ -n "$TEST_EMAIL" ] && [ -n "$TEST_PASSWORD" ]; then
        echo -e "${YELLOW}[AUTH] Attempting login with existing credentials...${NC}" >&2
        if login_user "$TEST_EMAIL" "$TEST_PASSWORD"; then
            return 0
        else
            echo -e "${YELLOW}[AUTH] Login failed, registering new user instead...${NC}" >&2
            register_new_user
        fi
    else
        echo -e "${YELLOW}[AUTH] No credentials provided, registering new user...${NC}" >&2
        register_new_user
    fi
}

# Export functions so they can be used by sourcing scripts
export -f register_new_user
export -f login_user
export -f quick_auth
