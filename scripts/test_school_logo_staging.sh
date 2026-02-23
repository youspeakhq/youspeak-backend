#!/usr/bin/env bash
# E2E test: school creation → get profile (logo_url null) → upload logo → get profile (logo_url set) → fetch logo URL.
# Verifies staging R2 bucket is configured and serves files; reproduces "logo_url null in profile" issue.
# Usage: ./scripts/test_school_logo_staging.sh [BASE_URL]
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

TEST_EMAIL="logo-test-$(date +%s)@example.com"
TEST_PASSWORD="TestPassword123!"

# Minimal 1x1 PNG (valid image/jpeg not required; API accepts image/png)
TEMP_PNG=""
cleanup() { [ -n "$TEMP_PNG" ] && [ -f "$TEMP_PNG" ] && rm -f "$TEMP_PNG"; }
trap cleanup EXIT
TEMP_PNG="$(mktemp)"
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" | base64 -d > "$TEMP_PNG"

echo "Staging base URL: $BASE_URL"
echo ""

# 1. Health
echo "=== 1. GET /health ==="
HEALTH_CODE="$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")"
echo "HTTP $HEALTH_CODE"
[ "$HEALTH_CODE" = "200" ] || { echo "FAIL: health $HEALTH_CODE"; exit 1; }
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
    \"school_name\": \"Logo E2E Test School\"
  }")"
REG_BODY="$(echo "$REG_RESP" | sed '$d')"
REG_CODE="$(echo "$REG_RESP" | tail -1)"
echo "HTTP $REG_CODE"
[ "$REG_CODE" = "200" ] || [ "$REG_CODE" = "201" ] || { echo "$REG_BODY"; echo "FAIL: register $REG_CODE"; exit 1; }
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
[ "$LOGIN_CODE" = "200" ] || { echo "$LOGIN_BODY"; echo "FAIL: login $LOGIN_CODE"; exit 1; }
TOKEN=""
if command -v jq >/dev/null 2>&1; then
  TOKEN="$(echo "$LOGIN_BODY" | jq -r '.data.access_token // empty')"
fi
[ -n "$TOKEN" ] || TOKEN="$(echo "$LOGIN_BODY" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
[ -n "$TOKEN" ] || { echo "FAIL: no access_token"; echo "$LOGIN_BODY" | head -c 500; exit 1; }
echo "OK (token obtained)"
echo ""

# 4. Get school profile (before logo) — expect logo_url null
echo "=== 4. GET /api/v1/schools/profile (before logo) ==="
PROFILE1_RESP="$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/schools/profile" \
  -H "Authorization: Bearer $TOKEN")"
PROFILE1_BODY="$(echo "$PROFILE1_RESP" | sed '$d')"
PROFILE1_CODE="$(echo "$PROFILE1_RESP" | tail -1)"
echo "HTTP $PROFILE1_CODE"
[ "$PROFILE1_CODE" = "200" ] || { echo "$PROFILE1_BODY"; echo "FAIL: get profile $PROFILE1_CODE"; exit 1; }
if command -v jq >/dev/null 2>&1; then
  LOGO_BEFORE="$(echo "$PROFILE1_BODY" | jq -r '.data.logo_url // "null"')"
  echo "logo_url: $LOGO_BEFORE"
  [ "$LOGO_BEFORE" = "null" ] || [ -z "$LOGO_BEFORE" ] || echo "WARN: expected logo_url null for new school"
else
  echo "$PROFILE1_BODY"
fi
echo "OK"
echo ""

# 5. Upload logo (multipart)
echo "=== 5. POST /api/v1/schools/logo ==="
UPLOAD_RESP="$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/schools/logo" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TEMP_PNG;type=image/png;filename=logo.png")"
UPLOAD_BODY="$(echo "$UPLOAD_RESP" | sed '$d')"
UPLOAD_CODE="$(echo "$UPLOAD_RESP" | tail -1)"
echo "HTTP $UPLOAD_CODE"
if [ "$UPLOAD_CODE" != "200" ]; then
  echo "$UPLOAD_BODY"
  echo "FAIL: logo upload $UPLOAD_CODE (check R2 env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, STORAGE_PUBLIC_BASE_URL)"
  exit 1
fi
if command -v jq >/dev/null 2>&1; then
  LOGO_URL="$(echo "$UPLOAD_BODY" | jq -r '.data.logo_url // empty')"
  echo "Response data.logo_url: ${LOGO_URL:-<empty>}"
  if [ -z "$LOGO_URL" ] || [ "$LOGO_URL" = "null" ]; then
    echo "FAIL: upload returned 200 but data.logo_url is null/empty — bug: logo not saved in response or DB"
    echo "$UPLOAD_BODY" | jq .
    exit 1
  fi
else
  LOGO_URL=""
  echo "$UPLOAD_BODY"
fi
echo "OK (logo uploaded)"
echo ""

# 6. Get school profile again — expect logo_url set
echo "=== 6. GET /api/v1/schools/profile (after logo) ==="
PROFILE2_RESP="$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/schools/profile" \
  -H "Authorization: Bearer $TOKEN")"
PROFILE2_BODY="$(echo "$PROFILE2_RESP" | sed '$d')"
PROFILE2_CODE="$(echo "$PROFILE2_RESP" | tail -1)"
echo "HTTP $PROFILE2_CODE"
[ "$PROFILE2_CODE" = "200" ] || { echo "$PROFILE2_BODY"; echo "FAIL: get profile after logo $PROFILE2_CODE"; exit 1; }
if command -v jq >/dev/null 2>&1; then
  LOGO_AFTER="$(echo "$PROFILE2_BODY" | jq -r '.data.logo_url // "null"')"
  echo "logo_url: $LOGO_AFTER"
  if [ -z "$LOGO_AFTER" ] || [ "$LOGO_AFTER" = "null" ]; then
    echo "FAIL: profile still has logo_url null after upload — DB not updated or GET returning stale data"
    echo "$PROFILE2_BODY" | jq .
    exit 1
  fi
  [ -z "$LOGO_URL" ] && LOGO_URL="$LOGO_AFTER"
else
  echo "$PROFILE2_BODY"
fi
echo "OK (logo_url persisted in profile)"
echo ""

# 7. Fetch logo URL — bucket must serve the file (200)
echo "=== 7. GET logo URL (bucket public access) ==="
[ -n "$LOGO_URL" ] || { echo "SKIP: no LOGO_URL to fetch (install jq to extract)"; exit 0; }
LOGO_HTTP="$(curl -s -o /dev/null -w "%{http_code}" "$LOGO_URL")"
echo "HTTP $LOGO_HTTP for $LOGO_URL"
if [ "$LOGO_HTTP" != "200" ]; then
  echo "FAIL: bucket returned $LOGO_HTTP — check STORAGE_PUBLIC_BASE_URL and R2 bucket public access / custom domain"
  exit 1
fi
echo "OK (bucket serves logo)"
echo ""
echo "Done. School creation → profile → logo upload → profile → URL fetch all passed."
echo "Bucket is configured and logo_url is persisted and served."
echo ""
echo "If logo upload returns 503 SignatureDoesNotMatch: regenerate R2 API token (Dashboard → R2 → Manage R2 API Tokens), update AWS Secrets Manager (r2-secret-access-key, etc.), then force ECS redeploy. Ensure STORAGE_PUBLIC_BASE_URL is set so profile returns a reachable logo URL."
