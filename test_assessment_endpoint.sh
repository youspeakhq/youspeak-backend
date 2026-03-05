#!/bin/bash
# Test the assessment (assignment) creation endpoint on staging
# Clarifies that "assessment" and "assignment" are the same thing

set -e

STAGING_URL="https://api-staging.youspeakhq.com"
API_BASE="${STAGING_URL}/api/v1"

# Generate unique identifiers for this test
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RANDOM_SUFFIX=$(openssl rand -hex 4)
TEACHER_EMAIL="teacher_assess_${TIMESTAMP}_${RANDOM_SUFFIX}@test.com"
ADMIN_EMAIL="admin_assess_${TIMESTAMP}_${RANDOM_SUFFIX}@test.com"
TEST_PASSWORD="TestPass123!"

echo "======================================================================"
echo "Assessment/Assignment Endpoint Test"
echo "======================================================================"
echo ""
echo "KEY FINDING: 'Assessment' and 'Assignment' are THE SAME THING"
echo "  - API Route: /api/v1/assessments"
echo "  - Database Model: Assignment"
echo "  - No separate 'assignment' endpoint exists"
echo ""
echo "======================================================================"
echo ""
echo "Staging URL: ${STAGING_URL}"
echo "Admin Email: ${ADMIN_EMAIL}"
echo "Teacher Email: ${TEACHER_EMAIL}"
echo ""

# Step 1: Register school admin
echo "[1/7] Registering school admin..."
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
echo "[2/7] Logging in as admin..."
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
echo "[3/7] Creating teacher account..."
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
echo "[4/7] Registering teacher with access code..."
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
echo "[5/7] Logging in as teacher..."
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

# Step 6: Create a class (needed for assessment)
echo "[6/7] Creating a class for the assessment..."
SEMESTERS_RESPONSE=$(curl -s -X GET "${API_BASE}/schools/semesters" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}")

SEMESTER_ID=$(echo "$SEMESTERS_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin)['data']; print(data[0]['id'] if data else '')" 2>/dev/null)

if [ -z "$SEMESTER_ID" ]; then
  echo "ERROR: No semesters found"
  exit 1
fi

CREATE_CLASS_RESPONSE=$(curl -s -X POST "${API_BASE}/my-classes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}" \
  -d "{
    \"name\": \"Test Class for Assessment ${TIMESTAMP}\",
    \"schedule\": [{\"day_of_week\": \"Mon\", \"start_time\": \"09:00:00\", \"end_time\": \"10:00:00\"}],
    \"language_id\": 1,
    \"semester_id\": \"${SEMESTER_ID}\"
  }")

CLASS_ID=$(echo "$CREATE_CLASS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ -z "$CLASS_ID" ]; then
  echo "ERROR: Failed to create class"
  exit 1
fi

echo "Class created with ID: $CLASS_ID"
echo ""

# Step 7: Create an assessment (THIS IS THE MAIN TEST)
echo "[7/7] Testing CREATE ASSESSMENT endpoint..."
echo ""
echo "======================================================================"
echo "REQUEST SAMPLE FOR CREATE ASSESSMENT ENDPOINT"
echo "======================================================================"
echo ""
echo "Endpoint: POST ${API_BASE}/assessments"
echo "Headers:"
echo "  Content-Type: application/json"
echo "  Authorization: Bearer <teacher_token>"
echo ""
echo "Request Body:"
cat <<EOF
{
  "title": "French Vocabulary Quiz",
  "type": "oral" | "written",
  "instructions": "Complete the following questions (optional)",
  "due_date": "2026-03-15T23:59:59Z" (optional),
  "class_ids": ["<class_id>"],
  "enable_ai_marking": false,
  "questions": [
    {
      "question_id": "<uuid>",
      "points": 10
    }
  ]
}

Required fields:
- title: string (assessment name)
- type: "oral" or "written" (AssignmentType enum)
- class_ids: array of class UUIDs

Optional fields:
- instructions: string (task instructions)
- due_date: datetime (ISO format)
- enable_ai_marking: boolean (default: false)
- questions: array of {question_id, points} (from question bank)
EOF

echo ""
echo "======================================================================"
echo "ACTUAL TEST REQUEST"
echo "======================================================================"
echo ""

CREATE_ASSESSMENT_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "${API_BASE}/assessments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}" \
  -d "{
    \"title\": \"Test Assessment ${TIMESTAMP}\",
    \"type\": \"written\",
    \"instructions\": \"Please complete all questions carefully.\",
    \"due_date\": \"2026-03-20T23:59:59Z\",
    \"class_ids\": [\"${CLASS_ID}\"],
    \"enable_ai_marking\": true
  }")

HTTP_CODE=$(echo "$CREATE_ASSESSMENT_RESPONSE" | grep "HTTP_STATUS:" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$CREATE_ASSESSMENT_RESPONSE" | sed '/HTTP_STATUS:/d')

echo "HTTP Status: $HTTP_CODE"
echo ""
echo "Response:"
echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
echo ""

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
  echo "✅ SUCCESS: Assessment (aka Assignment) created successfully!"

  ASSESSMENT_ID=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

  echo ""
  echo "======================================================================"
  echo "Listing assessments to confirm..."
  echo "======================================================================"

  LIST_RESPONSE=$(curl -s -X GET "${API_BASE}/assessments" \
    -H "Authorization: Bearer ${TEACHER_TOKEN}")

  echo "$LIST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LIST_RESPONSE"

else
  echo "❌ FAILED: HTTP $HTTP_CODE"
  echo ""
  echo "Possible reasons for failure:"
  echo "- Missing required fields (title, type, class_ids)"
  echo "- Invalid class_ids"
  echo "- Invalid type (must be 'oral' or 'written')"
  echo "- Authentication issues"
fi

echo ""
echo "======================================================================"
echo "SUMMARY: Assessment vs Assignment Terminology"
echo "======================================================================"
echo ""
echo "✅ The endpoint /api/v1/assessments creates an 'Assignment' in the database"
echo "✅ 'Assessment' (API) = 'Assignment' (Database) - same entity"
echo "✅ No separate /api/v1/assignments endpoint exists"
echo "✅ Use POST /api/v1/assessments for creating tasks"
echo ""
echo "Test complete"
echo "======================================================================"
