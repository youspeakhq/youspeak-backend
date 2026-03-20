#!/bin/bash
set -e

API_BASE="https://api-staging.youspeakhq.com/api/v1"

# Teacher details
TEACHER_EMAIL="mbakaragoodness2003@gmail.com"
TEACHER_PASSWORD="MISSERUN123a#"
TEACHER_FIRST_NAME="Goodness"
TEACHER_LAST_NAME="Mbakara"

echo "=== Checking if teacher email already exists ==="

# Try to login first to see if account exists
LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${TEACHER_EMAIL}\",
    \"password\": \"${TEACHER_PASSWORD}\"
  }")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Teacher account already exists!"
  echo "$BODY" | python3 -m json.tool
  exit 0
fi

echo "Teacher doesn't exist yet. Need to create account with access code."
echo ""

# Check if we have a stored school admin token
if [ -f "/tmp/staging-jwt-token.txt" ]; then
  echo "=== Found existing school admin token ==="
  ADMIN_TOKEN=$(cat /tmp/staging-jwt-token.txt)

  # Try to generate an access code
  echo "=== Generating teacher access code ==="

  ACCESS_CODE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE}/admin/access-codes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -d '{
      "num_codes": 1
    }')

  HTTP_CODE=$(echo "$ACCESS_CODE_RESPONSE" | tail -n1)
  BODY=$(echo "$ACCESS_CODE_RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    ACCESS_CODE=$(echo "$BODY" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['data']['codes'][0]['code'])")
    echo "✅ Access code generated: ${ACCESS_CODE}"

    # Now register the teacher
    echo ""
    echo "=== Registering teacher ==="

    REGISTER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE}/auth/register/teacher" \
      -H "Content-Type: application/json" \
      -d "{
        \"access_code\": \"${ACCESS_CODE}\",
        \"email\": \"${TEACHER_EMAIL}\",
        \"password\": \"${TEACHER_PASSWORD}\",
        \"first_name\": \"${TEACHER_FIRST_NAME}\",
        \"last_name\": \"${TEACHER_LAST_NAME}\"
      }")

    HTTP_CODE=$(echo "$REGISTER_RESPONSE" | tail -n1)
    BODY=$(echo "$REGISTER_RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
      echo "✅ Teacher registered successfully!"
      echo "$BODY" | python3 -m json.tool

      # Try to login
      echo ""
      echo "=== Verifying login ==="

      LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{
          \"email\": \"${TEACHER_EMAIL}\",
          \"password\": \"${TEACHER_PASSWORD}\"
        }")

      echo "$LOGIN_RESPONSE" | python3 -m json.tool

    else
      echo "❌ Failed to register teacher (HTTP ${HTTP_CODE})"
      echo "$BODY" | python3 -m json.tool
      exit 1
    fi

  else
    echo "❌ Failed to generate access code (HTTP ${HTTP_CODE})"
    echo "$BODY" | python3 -m json.tool
    exit 1
  fi

else
  echo "❌ No admin token found. Please provide an access code manually."
  echo ""
  echo "To create a school admin first, run:"
  echo ""
  echo "curl -X POST \"${API_BASE}/auth/register/school\" \\"
  echo "  -H \"Content-Type: application/json\" \\"
  echo "  -d '{"
  echo "    \"email\": \"admin@example.com\","
  echo "    \"password\": \"SecurePassword123\","
  echo "    \"school_name\": \"Test School\","
  echo "    \"address_country\": \"USA\""
  echo "  }'"
  exit 1
fi
