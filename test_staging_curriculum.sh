#!/usr/bin/env bash
# Quick test script for staging curriculum endpoint
# Usage: ./test_staging_curriculum.sh [EMAIL] [PASSWORD]
# If no credentials provided, creates a new test account

set -e

BASE_URL="https://api-staging.youspeakhq.com"
TEST_EMAIL="${1:-test-$(date +%s)@example.com}"
TEST_PASSWORD="${2:-TestPassword123}"

echo "🧪 Testing Staging Curriculum Endpoint"
echo "======================================="
echo ""
echo "📧 Email: $TEST_EMAIL"
echo "🔗 Base URL: $BASE_URL"
echo ""

# Step 1: Register or login
if [ -z "$1" ]; then
  echo "📝 Step 1: Registering new test account..."
  REG_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/school" \
    -H "Content-Type: application/json" \
    -d '{
      "account_type": "school",
      "email": "'"$TEST_EMAIL"'",
      "password": "'"$TEST_PASSWORD"'",
      "school_name": "Test School",
      "admin_first_name": "Test",
      "admin_last_name": "User"
    }')
  echo "✅ Registration response:"
  echo "$REG_RESP" | jq '.'
  echo ""
else
  echo "📝 Step 1: Using existing credentials"
  echo ""
fi

# Step 2: Login
echo "🔐 Step 2: Logging in..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$TEST_EMAIL"'",
    "password": "'"$TEST_PASSWORD"'"
  }')

TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token // empty')

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed:"
  echo "$LOGIN_RESP" | jq '.'
  exit 1
fi

echo "✅ Login successful"
echo "🎫 Token: ${TOKEN:0:30}..."
echo ""

# Step 3: Test curriculum endpoints
echo "📚 Step 3: Testing curriculum endpoints"
echo "----------------------------------------"
echo ""

# Test 1: List all
echo "Test 1: List all curriculums (no filters)"
curl -s -X GET "$BASE_URL/api/v1/curriculums" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 2: Empty search
echo "Test 2: List with empty search (should show all)"
curl -s -X GET "$BASE_URL/api/v1/curriculums?search=" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 3: Wildcard search
echo "Test 3: List with wildcard search (should show all)"
curl -s -X GET "$BASE_URL/api/v1/curriculums?search=*" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 4: Text search
echo "Test 4: List with text search 'English'"
curl -s -X GET "$BASE_URL/api/v1/curriculums?search=English" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 5: With status filter
echo "Test 5: List with status=published"
curl -s -X GET "$BASE_URL/api/v1/curriculums?status=published" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 6: Invalid status (should error)
echo "Test 6: Invalid status (should return 422)"
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X GET "$BASE_URL/api/v1/curriculums?status=invalid" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Test 7: Pagination
echo "Test 7: Pagination (page=2, page_size=5)"
curl -s -X GET "$BASE_URL/api/v1/curriculums?page=2&page_size=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

echo "✅ All tests complete!"
echo ""
echo "📖 View interactive API docs:"
echo "   Swagger UI: $BASE_URL/docs"
echo "   ReDoc: $BASE_URL/redoc"
echo ""
echo "💡 Frontend developer tips:"
echo "   1. Check token expiration (15 min lifetime)"
echo "   2. Ensure 'Authorization: Bearer TOKEN' header format"
echo "   3. Empty results (data: []) is NOT an error"
echo "   4. Check browser console for network errors"
echo ""
