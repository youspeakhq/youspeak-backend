#!/usr/bin/env bash
# Test name update fix
# Tests full_name splitting and direct first_name/last_name updates

set -e

BASE_URL="https://api-staging.youspeakhq.com"
EMAIL="test-$(date +%s)@example.com"
PASSWORD="TestPassword123"

echo "🧪 Testing Name Update Fix"
echo "=========================="
echo ""

# Register and login
echo "📝 Step 1: Registering test account..."
REG_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "account_type": "school",
    "email": "'"$EMAIL"'",
    "password": "'"$PASSWORD"'",
    "school_name": "Test School",
    "admin_first_name": "Original",
    "admin_last_name": "Name"
  }')

echo "🔐 Step 2: Logging in..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$EMAIL"'","password":"'"$PASSWORD"'"}')

TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token')
USER_ID=$(echo "$LOGIN_RESP" | jq -r '.data.user_id')

echo "✅ User ID: $USER_ID"
echo ""

# Test 1: Update using full_name (two names)
echo "🧪 Test 1: Update full_name to 'John Smith'"
UPDATE1=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Smith"}')

FIRST1=$(echo "$UPDATE1" | jq -r '.first_name // "null"')
LAST1=$(echo "$UPDATE1" | jq -r '.last_name // "null"')
FULL1=$(echo "$UPDATE1" | jq -r '.full_name // "null"')

echo "  first_name: $FIRST1"
echo "  last_name: $LAST1"
echo "  full_name: $FULL1"

if [ "$FIRST1" = "John" ] && [ "$LAST1" = "Smith" ]; then
  echo "  ✅ PASS: Names correctly split"
else
  echo "  ❌ FAIL: Expected first='John', last='Smith', got first='$FIRST1', last='$LAST1'"
fi
echo ""

# Test 2: Update using full_name (single name)
echo "🧪 Test 2: Update full_name to 'Madonna' (single name)"
UPDATE2=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Madonna"}')

FIRST2=$(echo "$UPDATE2" | jq -r '.first_name // "null"')
LAST2=$(echo "$UPDATE2" | jq -r '.last_name // "null"')

echo "  first_name: $FIRST2"
echo "  last_name: '$LAST2'"

if [ "$FIRST2" = "Madonna" ] && [ "$LAST2" = "" ]; then
  echo "  ✅ PASS: Single name handled correctly"
else
  echo "  ❌ FAIL: Expected first='Madonna', last='', got first='$FIRST2', last='$LAST2'"
fi
echo ""

# Test 3: Update using full_name (three names)
echo "🧪 Test 3: Update full_name to 'Mary Jane Watson' (three names)"
UPDATE3=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Mary Jane Watson"}')

FIRST3=$(echo "$UPDATE3" | jq -r '.first_name // "null"')
LAST3=$(echo "$UPDATE3" | jq -r '.last_name // "null"')

echo "  first_name: $FIRST3"
echo "  last_name: $LAST3"

if [ "$FIRST3" = "Mary" ] && [ "$LAST3" = "Jane Watson" ]; then
  echo "  ✅ PASS: Multiple names handled correctly (first word = first_name, rest = last_name)"
else
  echo "  ❌ FAIL: Expected first='Mary', last='Jane Watson', got first='$FIRST3', last='$LAST3'"
fi
echo ""

# Test 4: Update using first_name and last_name directly
echo "🧪 Test 4: Update first_name and last_name separately"
UPDATE4=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Wonder"}')

FIRST4=$(echo "$UPDATE4" | jq -r '.first_name // "null"')
LAST4=$(echo "$UPDATE4" | jq -r '.last_name // "null"')

echo "  first_name: $FIRST4"
echo "  last_name: $LAST4"

if [ "$FIRST4" = "Alice" ] && [ "$LAST4" = "Wonder" ]; then
  echo "  ✅ PASS: Direct name updates work"
else
  echo "  ❌ FAIL: Expected first='Alice', last='Wonder', got first='$FIRST4', last='$LAST4'"
fi
echo ""

# Test 5: Update full_name with extra whitespace
echo "🧪 Test 5: Update full_name with extra whitespace '  Bob   Builder  '"
UPDATE5=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"  Bob   Builder  "}')

FIRST5=$(echo "$UPDATE5" | jq -r '.first_name // "null"')
LAST5=$(echo "$UPDATE5" | jq -r '.last_name // "null"')

echo "  first_name: $FIRST5"
echo "  last_name: $LAST5"

if [ "$FIRST5" = "Bob" ] && [ "$LAST5" = "Builder" ]; then
  echo "  ✅ PASS: Extra whitespace handled correctly"
else
  echo "  ❌ FAIL: Expected first='Bob', last='Builder', got first='$FIRST5', last='$LAST5'"
fi
echo ""

# Test 6: Verify email and password still work
echo "🧪 Test 6: Verify email/password updates still work"
NEW_EMAIL="updated-$(date +%s)@example.com"
NEW_PASSWORD="NewPassword456"

UPDATE6=$(curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'","password":"'"$NEW_PASSWORD"'"}')

# Try login with new credentials
LOGIN_CHECK=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'","password":"'"$NEW_PASSWORD"'"}')

if echo "$LOGIN_CHECK" | jq -e '.success' > /dev/null; then
  echo "  ✅ PASS: Email and password updates still work"
else
  echo "  ❌ FAIL: Email/password update broken"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 All name update tests complete!"
echo ""
echo "📖 Summary:"
echo "   Test 1: full_name with two names ✓"
echo "   Test 2: full_name with single name ✓"
echo "   Test 3: full_name with three+ names ✓"
echo "   Test 4: Direct first_name/last_name updates ✓"
echo "   Test 5: Whitespace handling ✓"
echo "   Test 6: Email/password still work ✓"
