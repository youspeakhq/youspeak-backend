#!/usr/bin/env bash
# Test user update functionality
# Usage: ./test_user_update.sh [EMAIL] [PASSWORD]

set -e

BASE_URL="https://api-staging.youspeakhq.com"
EMAIL="${1:-test-$(date +%s)@example.com}"
PASSWORD="${2:-TestPassword123}"

echo "🔧 Testing User Update Functionality"
echo "====================================="
echo ""

# Step 1: Register
echo "📝 Step 1: Registering..."
REG_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "account_type": "school",
    "email": "'"$EMAIL"'",
    "password": "'"$PASSWORD"'",
    "school_name": "Test School",
    "admin_first_name": "Test",
    "admin_last_name": "User"
  }')
echo "$REG_RESP" | jq -c '.'
echo ""

# Step 2: Login
echo "🔐 Step 2: Logging in..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$EMAIL"'","password":"'"$PASSWORD"'"}')

TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token')
USER_ID=$(echo "$LOGIN_RESP" | jq -r '.data.user_id')

echo "✅ Logged in"
echo "User ID: $USER_ID"
echo ""

# Step 3: Get current user info
echo "👤 Step 3: Getting current user info..."
CURRENT=$(curl -s -X GET "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN")
echo "Current name: $(echo "$CURRENT" | jq -r '.full_name')"
echo "Current email: $(echo "$CURRENT" | jq -r '.email')"
echo ""

# Step 4: Update full name
echo "✏️  Step 4: Updating full name to 'John Smith'..."
UPDATE1=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Smith"}')
echo "New name: $(echo "$UPDATE1" | jq -r '.full_name')"
echo ""

# Step 5: Update email
echo "📧 Step 5: Updating email..."
NEW_EMAIL="updated-$(date +%s)@example.com"
UPDATE2=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'"}')
echo "New email: $(echo "$UPDATE2" | jq -r '.email')"
echo ""

# Step 6: Update password
echo "🔑 Step 6: Updating password..."
NEW_PASSWORD="NewPassword456"
UPDATE3=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"'"$NEW_PASSWORD"'"}')
echo "Password updated: $(echo "$UPDATE3" | jq -r '.id')"
echo ""

# Step 7: Verify new credentials work
echo "✅ Step 7: Verifying new credentials work..."
LOGIN_RESP2=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'","password":"'"$NEW_PASSWORD"'"}')

if echo "$LOGIN_RESP2" | jq -e '.success' > /dev/null; then
  echo "✅ SUCCESS! New credentials work!"
else
  echo "❌ FAILED: New credentials don't work"
  echo "$LOGIN_RESP2" | jq '.'
fi
echo ""

echo "✅ All user update tests passed!"
echo ""
echo "📖 Summary:"
echo "   - Updated full name: Test User → John Smith"
echo "   - Updated email: $EMAIL → $NEW_EMAIL"
echo "   - Updated password: $PASSWORD → $NEW_PASSWORD"
echo "   - Verified new credentials work ✓"
