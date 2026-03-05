#!/bin/bash
# Test: Upload curriculum, then GET it to reproduce the 500 error

STAGING_URL="https://api-staging.youspeakhq.com"
API_BASE="${STAGING_URL}/api/v1"

# Use the test account we just created
TEST_EMAIL="admin_20260305_101054_720d321d@test.com"
TEST_PASSWORD="TestPass123!"

echo "======================================================================"
echo "Testing Curriculum Upload + GET (Reproducing 500 Error)"
echo "======================================================================"
echo ""

# Login
echo "[1/3] Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.data.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo "❌ Login failed"
    echo "$LOGIN_RESPONSE" | jq '.'
    exit 1
fi
echo "✅ Login successful"
echo ""

# Upload curriculum
echo "[2/3] Uploading test curriculum..."

# Create a simple test PDF content
TEST_PDF_CONTENT="Test curriculum content for debugging"

UPLOAD_RESPONSE=$(curl -s -X POST "${API_BASE}/curriculums" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "title=Test Curriculum Upload $(date +%H%M%S)" \
  -F "language_id=1" \
  -F "description=Testing upload and GET" \
  -F "file=@-;filename=test.pdf;type=application/pdf" <<< "$TEST_PDF_CONTENT")

echo "Upload response:"
echo "$UPLOAD_RESPONSE" | jq '.'

CURRICULUM_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.data.id // empty')

if [ -z "$CURRICULUM_ID" ] || [ "$CURRICULUM_ID" = "null" ]; then
    echo ""
    echo "❌ Upload failed or returned no ID"
    exit 1
fi

echo ""
echo "✅ Upload successful"
echo "   Curriculum ID: $CURRICULUM_ID"
echo ""

# Try to GET the curriculum (this is where the 500 error occurs)
echo "[3/3] Getting uploaded curriculum..."
echo ""

GET_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "${API_BASE}/curriculums/${CURRICULUM_ID}" \
  -H "Authorization: Bearer ${TOKEN}")

HTTP_CODE=$(echo "$GET_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
BODY=$(echo "$GET_RESPONSE" | sed '/HTTP_CODE:/d')

echo "HTTP Status: $HTTP_CODE"
echo "Response body:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"

if [ "$HTTP_CODE" = "500" ]; then
    echo ""
    echo "❌ REPRODUCED: Got 500 Internal Server Error"
    echo ""
    echo "This is the issue you're seeing!"
elif [ "$HTTP_CODE" = "200" ]; then
    echo ""
    echo "✅ GET worked correctly (issue may be intermittent)"
else
    echo ""
    echo "⚠️  Got unexpected status: $HTTP_CODE"
fi

echo ""
echo "======================================================================"
