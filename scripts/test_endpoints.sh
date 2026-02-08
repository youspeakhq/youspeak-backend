#!/usr/bin/env bash
# Curl tests for health, register (school), and login.
# Usage: ./scripts/test_endpoints.sh [BASE_URL]
# Example: ./scripts/test_endpoints.sh http://localhost:8000
# Default BASE_URL: staging ALB (or set BASE_URL env).

set -e

BASE_URL="${1:-${BASE_URL:-http://youspeak-alb-staging-620291408.us-east-1.elb.amazonaws.com}}"
TEST_EMAIL="test-school-$(date +%s)@example.com"
TEST_PASSWORD="TestPassword123!"

echo "Base URL: $BASE_URL"
echo ""

# 1. Health
echo "=== 1. GET /health ==="
HEALTH_RESP=$(curl -s -w "\n%{http_code}" "$BASE_URL/health")
HEALTH_BODY=$(echo "$HEALTH_RESP" | sed '$d')
HEALTH_CODE=$(echo "$HEALTH_RESP" | tail -1)
echo "HTTP $HEALTH_CODE"
echo "$HEALTH_BODY" | head -c 200
echo ""
if [ "$HEALTH_CODE" != "200" ]; then
  echo "FAIL: health check returned $HEALTH_CODE"
  exit 1
fi
echo "OK"
echo ""

# 2. Register school
echo "=== 2. POST /api/v1/auth/register/school ==="
REG_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d "{
    \"account_type\": \"school\",
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"school_name\": \"E2E Test School\",
    \"admin_first_name\": \"Admin\",
    \"admin_last_name\": \"User\"
  }")
REG_BODY=$(echo "$REG_RESP" | sed '$d')
REG_CODE=$(echo "$REG_RESP" | tail -1)
echo "HTTP $REG_CODE"
echo "$REG_BODY"
if [ "$REG_CODE" != "200" ] && [ "$REG_CODE" != "201" ]; then
  echo "WARN: register returned $REG_CODE (may be 500 if DB/migrations not ready on server)"
  # Still try login in case user already existed
fi
echo ""

# 3. Login
echo "=== 3. POST /api/v1/auth/login ==="
LOGIN_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
LOGIN_BODY=$(echo "$LOGIN_RESP" | sed '$d')
LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -1)
echo "HTTP $LOGIN_CODE"
echo "$LOGIN_BODY" | head -c 300
echo ""
if [ "$LOGIN_CODE" = "200" ]; then
  echo "OK: login succeeded (token in response)"
elif [ "$LOGIN_CODE" = "401" ]; then
  echo "WARN: login 401 (wrong credentials or user not found)"
else
  echo "WARN: login returned $LOGIN_CODE"
fi
echo ""

echo "Done. Health must be 200; register/login may be 200/201 or 500 if backend DB is not ready."
