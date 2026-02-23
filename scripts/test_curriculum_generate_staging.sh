#!/usr/bin/env bash
# Test the staging API generate-curriculum endpoint (real AI, not mock).
# Resolves staging URL from Terraform (api_staging_url_https or alb_staging_dns_name), then:
#   health → register school → login → GET languages → POST curriculums/generate.
# Usage: ./scripts/test_curriculum_generate_staging.sh [BASE_URL]
# Or set BASE_URL. Terraform: BASE_URL=$(terraform -chdir=terraform output -raw api_staging_url_https)

set -e

if [ -n "$1" ]; then
  BASE_URL="$1"
elif [ -z "$BASE_URL" ]; then
  if command -v terraform >/dev/null 2>&1; then
    ROOT="$(cd "$(dirname "$0")/.." && pwd)"
    if [ -d "$ROOT/terraform" ]; then
      STAGING_HTTPS="$(terraform -chdir="$ROOT/terraform" output -raw api_staging_url_https 2>/dev/null)" || true
      if [ -n "$STAGING_HTTPS" ] && [ "$STAGING_HTTPS" != "null" ]; then
        BASE_URL="$STAGING_HTTPS"
      else
        ALB_DNS="$(terraform -chdir="$ROOT/terraform" output -raw alb_staging_dns_name 2>/dev/null)" || true
        if [ -n "$ALB_DNS" ]; then
          BASE_URL="http://${ALB_DNS}"
        fi
      fi
    fi
  fi
  [ -n "$BASE_URL" ] || BASE_URL="http://youspeak-alb-staging-620291408.us-east-1.elb.amazonaws.com"
fi

TEST_EMAIL="curriculum-test-$(date +%s)@example.com"
TEST_PASSWORD="TestPassword123!"
PROMPT="Spanish 1 for high school: greetings, numbers 1-20, and basic questions (What is your name? Where are you from?)."

echo "Staging base URL: $BASE_URL"
echo ""

# 1. Health
echo "=== 1. GET /health ==="
HEALTH_CODE="$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")"
echo "HTTP $HEALTH_CODE"
if [ "$HEALTH_CODE" != "200" ]; then
  echo "FAIL: health check returned $HEALTH_CODE"
  exit 1
fi
echo "OK"
echo ""

# 2. Register school
echo "=== 2. POST /api/v1/auth/register/school ==="
REG_RESP="$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d "{
    \"account_type\": \"school\",
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"school_name\": \"Curriculum E2E Test School\"
  }")"
REG_BODY="$(echo "$REG_RESP" | sed '$d')"
REG_CODE="$(echo "$REG_RESP" | tail -1)"
echo "HTTP $REG_CODE"
if [ "$REG_CODE" != "200" ] && [ "$REG_CODE" != "201" ]; then
  echo "$REG_BODY"
  echo "FAIL: register returned $REG_CODE"
  exit 1
fi
echo "OK (school created)"
echo ""

# 3. Login
echo "=== 3. POST /api/v1/auth/login ==="
LOGIN_RESP="$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")"
LOGIN_BODY="$(echo "$LOGIN_RESP" | sed '$d')"
LOGIN_CODE="$(echo "$LOGIN_RESP" | tail -1)"
echo "HTTP $LOGIN_CODE"
if [ "$LOGIN_CODE" != "200" ]; then
  echo "$LOGIN_BODY"
  echo "FAIL: login returned $LOGIN_CODE"
  exit 1
fi
TOKEN="$(echo "$LOGIN_BODY" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
if [ -z "$TOKEN" ]; then
  if command -v jq >/dev/null 2>&1; then
    TOKEN="$(echo "$LOGIN_BODY" | jq -r '.data.access_token // empty')"
  fi
fi
if [ -z "$TOKEN" ]; then
  echo "FAIL: could not extract access_token from login response"
  echo "$LOGIN_BODY" | head -c 500
  exit 1
fi
echo "OK (token obtained)"
echo ""

# 4. Get languages (to use a valid language_id)
echo "=== 4. GET /api/v1/references/languages ==="
LANG_RESP="$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/references/languages" \
  -H "Authorization: Bearer $TOKEN")"
LANG_BODY="$(echo "$LANG_RESP" | sed '$d')"
LANG_CODE="$(echo "$LANG_RESP" | tail -1)"
echo "HTTP $LANG_CODE"
if [ "$LANG_CODE" != "200" ]; then
  echo "$LANG_BODY"
  echo "WARN: languages returned $LANG_CODE, will use language_id=1"
  LANGUAGE_ID=1
else
  if command -v jq >/dev/null 2>&1; then
    LANGUAGE_ID="$(echo "$LANG_BODY" | jq -r '.data[0].id // 1')"
    echo "Using language_id=$LANGUAGE_ID"
  else
    LANGUAGE_ID=1
  fi
fi
echo ""

# 5. Generate curriculum (real AI when TEST_MODE is not set on server)
echo "=== 5. POST /api/v1/curriculums/generate ==="
echo "Prompt: $PROMPT"
echo "language_id: $LANGUAGE_ID"
GEN_RESP="$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/curriculums/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"$PROMPT\",\"language_id\":$LANGUAGE_ID}")"
GEN_BODY="$(echo "$GEN_RESP" | sed '$d')"
GEN_CODE="$(echo "$GEN_RESP" | tail -1)"
echo "HTTP $GEN_CODE"
if [ "$GEN_CODE" != "200" ]; then
  echo "$GEN_BODY"
  echo "FAIL: generate returned $GEN_CODE"
  exit 1
fi

if command -v jq >/dev/null 2>&1; then
  COUNT="$(echo "$GEN_BODY" | jq '.data | length')"
  echo "OK: received $COUNT topic(s)"
  echo ""
  echo "First topic:"
  echo "$GEN_BODY" | jq '.data[0]'
  echo ""
  echo "All topic titles:"
  echo "$GEN_BODY" | jq -r '.data[].title'
else
  echo "$GEN_BODY"
  echo "OK: generate returned 200 (install jq to pretty-print topics)"
fi
echo ""
echo "Done. Generate curriculum is live (not mock) when server does not set TEST_MODE=true."
echo "If generate returned 500, check staging env: AWS credentials, BEDROCK_MODEL_ID, and Bedrock access."
