#!/bin/bash
# Test the create class endpoint on staging
# This script tests both documentation and functionality

set -e

STAGING_URL="https://api-staging.youspeakhq.com"
API_BASE="${STAGING_URL}/api/v1"

# Generate unique identifiers for this test
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RANDOM_SUFFIX=$(openssl rand -hex 4)
TEACHER_EMAIL="teacher_${TIMESTAMP}_${RANDOM_SUFFIX}@test.com"
ADMIN_EMAIL="admin_${TIMESTAMP}_${RANDOM_SUFFIX}@test.com"
TEST_PASSWORD="TestPass123!"

echo "======================================================================"
echo "Create Class Endpoint Test"
echo "======================================================================"
echo ""
echo "Staging URL: ${STAGING_URL}"
echo "Admin Email: ${ADMIN_EMAIL}"
echo "Teacher Email: ${TEACHER_EMAIL}"
echo ""

# Step 1: Register school admin
echo "[1/6] Registering school admin..."
REGISTER_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/register/school" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${ADMIN_EMAIL}\",
    \"password\": \"${TEST_PASSWORD}\",
    \"first_name\": \"Admin\",
    \"last_name\": \"Test\",
    \"school_name\": \"Test School ${TIMESTAMP}\",
    \"account_type\": \"school\",
    \"admin_first_name\": \"Admin\",
    \"admin_last_name\": \"Test\"
  }")

echo "$REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REGISTER_RESPONSE"
echo ""

# Step 2: Login as admin
echo "[2/6] Logging in as admin..."
LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${ADMIN_EMAIL}\",
    \"password\": \"${TEST_PASSWORD}\"
  }")

ADMIN_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$ADMIN_TOKEN" ]; then
  echo "ERROR: Failed to get admin access token"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

echo "Admin token obtained: ${ADMIN_TOKEN:0:20}..."
echo ""

# Step 3: Create a teacher
echo "[3/6] Creating teacher account..."
CREATE_TEACHER_RESPONSE=$(curl -s -X POST "${API_BASE}/teachers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d "{
    \"email\": \"${TEACHER_EMAIL}\",
    \"first_name\": \"Teacher\",
    \"last_name\": \"Test\"
  }")

echo "$CREATE_TEACHER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CREATE_TEACHER_RESPONSE"

ACCESS_CODE=$(echo "$CREATE_TEACHER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_code'])" 2>/dev/null)

if [ -z "$ACCESS_CODE" ]; then
  echo "ERROR: Failed to get teacher access code"
  exit 1
fi

echo "Teacher access code: $ACCESS_CODE"
echo ""

# Step 4: Register teacher with access code
echo "[4/6] Registering teacher with access code..."
TEACHER_REGISTER_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/register/teacher" \
  -H "Content-Type: application/json" \
  -d "{
    \"access_code\": \"${ACCESS_CODE}\",
    \"email\": \"${TEACHER_EMAIL}\",
    \"password\": \"${TEST_PASSWORD}\",
    \"first_name\": \"Teacher\",
    \"last_name\": \"Test\"
  }")

echo "$TEACHER_REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TEACHER_REGISTER_RESPONSE"
echo ""

# Step 5: Login as teacher
echo "[5/6] Logging in as teacher..."
TEACHER_LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${TEACHER_EMAIL}\",
    \"password\": \"${TEST_PASSWORD}\"
  }")

TEACHER_TOKEN=$(echo "$TEACHER_LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$TEACHER_TOKEN" ]; then
  echo "ERROR: Failed to get teacher access token"
  echo "$TEACHER_LOGIN_RESPONSE"
  exit 1
fi

echo "Teacher token obtained: ${TEACHER_TOKEN:0:20}..."
echo ""

# Get semester ID
echo "[5.5/6] Getting semester ID..."
SEMESTERS_RESPONSE=$(curl -s -X GET "${API_BASE}/schools/semesters" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}")

echo "$SEMESTERS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SEMESTERS_RESPONSE"

SEMESTER_ID=$(echo "$SEMESTERS_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin)['data']; print(data[0]['id'] if data else '')" 2>/dev/null)

if [ -z "$SEMESTER_ID" ]; then
  echo "ERROR: No semesters found"
  exit 1
fi

echo "Semester ID: $SEMESTER_ID"
echo ""

# Step 6: Create a class (TEST THE ENDPOINT)
echo "[6/6] Testing CREATE CLASS endpoint..."
echo ""
echo "======================================================================"
echo "REQUEST SAMPLE FOR CREATE CLASS ENDPOINT"
echo "======================================================================"
echo ""
echo "Endpoint: POST ${API_BASE}/my-classes"
echo "Headers:"
echo "  Content-Type: application/json"
echo "  Authorization: Bearer <teacher_token>"
echo ""
echo "Request Body:"
cat <<EOF
{
  "name": "French 101",
  "description": "Beginner French class (optional field)",
  "timeline": "Spring 2026 (optional field)",
  "schedule": [
    {
      "day_of_week": "Mon",
      "start_time": "09:00:00",
      "end_time": "10:00:00"
    }
  ],
  "language_id": 1,
  "semester_id": "<semester_id_from_/schools/semesters>"
}

Optional fields:
- sub_class: string (optional)
- level: string (optional)
- classroom_id: UUID (optional)
- status: "active" | "inactive" | "archived" (defaults to "active")

Required fields:
- name: string
- schedule: array of schedule objects (each with day_of_week, start_time, end_time)
- language_id: integer (1 for French, 2 for Spanish, etc.)
- semester_id: UUID (get from /schools/semesters endpoint)

Alternative: Multipart form-data with CSV roster
Content-Type: multipart/form-data
- data: JSON string (same structure as above)
- file: CSV file with columns: first_name, last_name, email
EOF

echo ""
echo "======================================================================"
echo "ACTUAL TEST REQUEST"
echo "======================================================================"
echo ""

CREATE_CLASS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "${API_BASE}/my-classes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}" \
  -d "{
    \"name\": \"Test Class ${TIMESTAMP}\",
    \"description\": \"This is a test class\",
    \"timeline\": \"Spring 2026\",
    \"schedule\": [
      {
        \"day_of_week\": \"Mon\",
        \"start_time\": \"09:00:00\",
        \"end_time\": \"10:00:00\"
      }
    ],
    \"language_id\": 1,
    \"semester_id\": \"${SEMESTER_ID}\"
  }")

HTTP_CODE=$(echo "$CREATE_CLASS_RESPONSE" | grep "HTTP_STATUS:" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$CREATE_CLASS_RESPONSE" | sed '/HTTP_STATUS:/d')

echo "HTTP Status: $HTTP_CODE"
echo ""
echo "Response:"
echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
echo ""

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
  echo "✅ SUCCESS: Class created successfully!"
else
  echo "❌ FAILED: HTTP $HTTP_CODE"
  echo ""
  echo "Possible reasons for failure:"
  echo "- Missing required fields (name, schedule, language_id, semester_id)"
  echo "- Invalid semester_id or language_id"
  echo "- Invalid schedule format"
  echo "- Authentication issues"
fi

echo ""
echo "======================================================================"
echo "Test complete"
echo "======================================================================"
