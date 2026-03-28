#!/bin/bash
set -e

STAGING_URL="https://api-staging.youspeakhq.com/api/v1"
TIMESTAMP=$(date +%s)
TEST_EMAIL="test-admin-${TIMESTAMP}@youspeak-test.com"
TEST_PASSWORD="TestPassword123!"

echo "🔧 Creating test school admin account..."
echo "Email: $TEST_EMAIL"
echo ""

# Register school with admin account
REGISTER_RESPONSE=$(curl -s -X POST "${STAGING_URL}/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "school_name": "Test School '"${TIMESTAMP}"'",
    "school_type": "primary",
    "target_languages": ["Spanish"],
    "program_type": "pioneer",
    "email": "'"${TEST_EMAIL}"'",
    "password": "'"${TEST_PASSWORD}"'",
    "first_name": "Test",
    "last_name": "Admin"
  }')

echo "Register response:"
echo "$REGISTER_RESPONSE" | jq '.'
echo ""

# Check if registration was successful
if echo "$REGISTER_RESPONSE" | jq -e '.success == true' > /dev/null; then
  echo "✅ School admin account created successfully!"
  echo ""
else
  echo "❌ Registration failed. Response:"
  echo "$REGISTER_RESPONSE"
  exit 1
fi

echo "🔐 Logging in..."
# Login to get JWT token
LOGIN_RESPONSE=$(curl -s -X POST "${STAGING_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"${TEST_EMAIL}"'",
    "password": "'"${TEST_PASSWORD}"'"
  }')

echo "Login response:"
echo "$LOGIN_RESPONSE" | jq '.'
echo ""

# Extract JWT token
JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.data.access_token')

if [ "$JWT_TOKEN" = "null" ] || [ -z "$JWT_TOKEN" ]; then
  echo "❌ Failed to get JWT token"
  exit 1
fi

echo "✅ Got JWT token!"
echo ""

echo "📧 Sending test email to mbakaragoodness2003@gmail.com..."
# Send email
EMAIL_RESPONSE=$(curl -s -X POST "${STAGING_URL}/emails/send" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "recipients": ["mbakaragoodness2003@gmail.com"],
    "subject": "Test Email from YouSpeak Staging API",
    "html_body": "<html><body><h1>Hello from YouSpeak!</h1><p>This is a test email sent from the staging environment.</p><p>✅ Email API is working correctly!</p></body></html>"
  }')

echo "Email response:"
echo "$EMAIL_RESPONSE" | jq '.'
echo ""

# Check if email was sent successfully
if echo "$EMAIL_RESPONSE" | jq -e '.success == true' > /dev/null; then
  echo "✅✅✅ SUCCESS! Email sent to mbakaragoodness2003@gmail.com"
  echo ""
  echo "Test completed successfully!"
  echo "Account created: $TEST_EMAIL"
else
  echo "❌ Email sending failed. Response:"
  echo "$EMAIL_RESPONSE"
  exit 1
fi
