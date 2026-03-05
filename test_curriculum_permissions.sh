#!/usr/bin/env bash
# Test curriculum permissions - verify teachers can list curriculum
set -e

STAGING_URL="https://api-staging.youspeakhq.com"

echo "======================================================================"
echo "Testing Curriculum Permissions Fix"
echo "======================================================================"
echo ""
echo "Staging URL: $STAGING_URL"

# Generate unique emails
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RAND=$(openssl rand -hex 4)
ADMIN_EMAIL="admin_curric_${TIMESTAMP}_${RAND}@test.com"
TEACHER_EMAIL="teacher_curric_${TIMESTAMP}_${RAND}@test.com"

echo "Admin Email: $ADMIN_EMAIL"
echo "Teacher Email: $TEACHER_EMAIL"
echo ""

# Step 1: Register school admin
echo "[1/5] Registering school admin..."
ADMIN_RESPONSE=$(curl -s -X POST "${STAGING_URL}/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$ADMIN_EMAIL"'",
    "password": "Test123456!",
    "first_name": "Admin",
    "last_name": "Test",
    "school_name": "Test School",
    "school_type": "secondary",
    "program_type": "partnership",
    "languages": []
  }')

SCHOOL_ID=$(echo "$ADMIN_RESPONSE" | jq -r '.data.school_id')
echo "School ID: $SCHOOL_ID"
echo ""

# Step 2: Login as admin
echo "[2/5] Logging in as admin..."
ADMIN_TOKEN_RESPONSE=$(curl -s -X POST "${STAGING_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$ADMIN_EMAIL"'",
    "password": "Test123456!"
  }')

ADMIN_TOKEN=$(echo "$ADMIN_TOKEN_RESPONSE" | jq -r '.data.access_token')
echo "Admin token obtained: ${ADMIN_TOKEN:0:20}..."
echo ""

# Step 3: Create teacher account
echo "[3/5] Creating teacher account..."
TEACHER_RESPONSE=$(curl -s -X POST "${STAGING_URL}/api/v1/schools/teachers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "email": "'"$TEACHER_EMAIL"'",
    "first_name": "Teacher",
    "last_name": "Test"
  }')

TEACHER_ACCESS_CODE=$(echo "$TEACHER_RESPONSE" | jq -r '.data.access_code')
echo "Teacher access code: $TEACHER_ACCESS_CODE"
echo ""

# Register teacher with access code
echo "[4/5] Registering teacher with access code..."
curl -s -X POST "${STAGING_URL}/api/v1/auth/register/teacher" \
  -H "Content-Type: application/json" \
  -d '{
    "access_code": "'"$TEACHER_ACCESS_CODE"'",
    "password": "Test123456!",
    "email": "'"$TEACHER_EMAIL"'"
  }' > /dev/null

# Login as teacher
TEACHER_TOKEN_RESPONSE=$(curl -s -X POST "${STAGING_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$TEACHER_EMAIL"'",
    "password": "Test123456!"
  }')

TEACHER_TOKEN=$(echo "$TEACHER_TOKEN_RESPONSE" | jq -r '.data.access_token')
echo "Teacher token obtained: ${TEACHER_TOKEN:0:20}..."
echo ""

# Step 5: Test curriculum list as teacher
echo "[5/5] Testing GET /api/v1/curriculums as teacher..."
echo ""
echo "======================================================================"
echo "REQUEST: GET $STAGING_URL/api/v1/curriculums"
echo "Authorization: Bearer <teacher_token>"
echo "======================================================================"
echo ""

CURRICULUM_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X GET "${STAGING_URL}/api/v1/curriculums?page=1&page_size=10" \
  -H "Authorization: Bearer $TEACHER_TOKEN")

HTTP_STATUS=$(echo "$CURRICULUM_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$CURRICULUM_RESPONSE" | sed '/HTTP_STATUS:/d')

echo "HTTP Status: $HTTP_STATUS"
echo ""
echo "Response:"
echo "$RESPONSE_BODY" | jq '.'
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
  echo "✅ SUCCESS: Teachers can now list curriculum!"
  echo "======================================================================"
  exit 0
elif [ "$HTTP_STATUS" = "403" ]; then
  echo "❌ FAILED: Still getting 403 Forbidden"
  echo "======================================================================"
  exit 1
else
  echo "⚠️  UNEXPECTED STATUS: $HTTP_STATUS"
  echo "======================================================================"
  exit 1
fi
