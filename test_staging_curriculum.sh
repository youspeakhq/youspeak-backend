#!/bin/bash
# Quick test script for staging curriculum GET endpoint

set -e

STAGING_URL="https://api-staging.youspeakhq.com"
API_BASE="${STAGING_URL}/api/v1"

echo "============================================================"
echo "Testing Curriculum GET endpoint on staging"
echo "Staging URL: ${STAGING_URL}"
echo "============================================================"
echo ""

# Get credentials
read -p "Enter admin email: " ADMIN_EMAIL
read -sp "Enter admin password: " ADMIN_PASSWORD
echo ""
echo ""

# Step 1: Login
echo "[1/3] Logging in as admin..."
LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")

if echo "$LOGIN_RESPONSE" | grep -q '"success":true'; then
  TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
  echo "✅ Login successful"
else
  echo "❌ Login failed:"
  echo "$LOGIN_RESPONSE" | jq '.' 2>/dev/null || echo "$LOGIN_RESPONSE"
  exit 1
fi
echo ""

# Step 2: List curriculums
echo "[2/3] Listing curriculums..."
LIST_RESPONSE=$(curl -s -X GET "${API_BASE}/curriculums?page=1&page_size=10" \
  -H "Authorization: Bearer ${TOKEN}")

if echo "$LIST_RESPONSE" | grep -q '"success":true'; then
  CURRICULUM_COUNT=$(echo "$LIST_RESPONSE" | jq '.data | length' 2>/dev/null || echo "0")
  echo "✅ Found ${CURRICULUM_COUNT} curriculum(s)"

  if [ "$CURRICULUM_COUNT" -eq 0 ]; then
    echo "⚠️  No curriculums found. Please create one first."
    exit 0
  fi

  CURRICULUM_ID=$(echo "$LIST_RESPONSE" | jq -r '.data[0].id' 2>/dev/null)
  echo "   Testing with ID: ${CURRICULUM_ID}"
else
  echo "❌ List failed:"
  echo "$LIST_RESPONSE" | jq '.' 2>/dev/null || echo "$LIST_RESPONSE"
  exit 1
fi
echo ""

# Step 3: Get specific curriculum
echo "[3/3] Getting curriculum by ID..."
GET_RESPONSE=$(curl -s -X GET "${API_BASE}/curriculums/${CURRICULUM_ID}" \
  -H "Authorization: Bearer ${TOKEN}")

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "${API_BASE}/curriculums/${CURRICULUM_ID}" \
  -H "Authorization: Bearer ${TOKEN}")

echo "Response Status: ${HTTP_CODE}"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ GET curriculum successful!"
  echo ""
  echo "Curriculum Details:"
  echo "$GET_RESPONSE" | jq '.data | {id, title, status, language_name, topics: (.topics | length)}' 2>/dev/null || \
    echo "$GET_RESPONSE"
else
  echo "❌ GET failed:"
  echo "$GET_RESPONSE" | jq '.' 2>/dev/null || echo "$GET_RESPONSE"
  exit 1
fi

echo ""
echo "============================================================"
echo "✅ TEST PASSED: Curriculum GET endpoint is working"
echo "============================================================"
