#!/bin/bash

# Simple test script for email sending API on staging
# Usage: ./test-email-staging-simple.sh JWT_TOKEN

if [ -z "$1" ]; then
    echo "❌ Error: JWT token required"
    echo ""
    echo "Usage: ./test-email-staging-simple.sh YOUR_JWT_TOKEN"
    echo ""
    echo "To get your JWT token:"
    echo "  1. Login to https://app-staging.youspeakhq.com (or your staging frontend)"
    echo "  2. Open browser DevTools → Application/Storage → Local Storage"
    echo "  3. Copy the JWT token (or check the Authorization header in Network tab)"
    exit 1
fi

JWT_TOKEN="$1"
STAGING_URL="https://api-staging.youspeakhq.com"
API_PREFIX="/api/v1"

echo "🧪 Testing Email Sending API on Staging"
echo "========================================"
echo ""
echo "Endpoint: ${STAGING_URL}${API_PREFIX}/emails/send"
echo "JWT Token (first 20 chars): ${JWT_TOKEN:0:20}..."
echo ""

# Test 1: Send email to single recipient
echo "📧 Test 1: Sending email to single recipient"
echo "--------------------------------------------"
RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/emails/send" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d '{
        "recipients": ["student1@example.com"],
        "subject": "Test Email from Staging",
        "html_body": "<html><body><h1>Hello!</h1><p>This is a test email from staging.</p></body></html>"
    }' \
    -w "\nHTTP_STATUS:%{http_code}" \
    -s)

HTTP_STATUS=$(echo "$RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

echo "HTTP Status: $HTTP_STATUS"
echo ""
echo "Response:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

case $HTTP_STATUS in
    200)
        echo "✅ SUCCESS: Email sent successfully"
        EMAIL_LOG_ID=$(echo "$BODY" | jq -r '.data.email_log_id // empty')
        SUCCESS=$(echo "$BODY" | jq -r '.data.successful_sends // 0')
        FAILED=$(echo "$BODY" | jq -r '.data.failed_sends // 0')
        echo "   Email Log ID: $EMAIL_LOG_ID"
        echo "   Successful: $SUCCESS, Failed: $FAILED"
        ;;
    401)
        echo "❌ AUTHENTICATION FAILED"
        echo "   Your JWT token is invalid or expired"
        echo "   Please get a fresh token from the frontend app"
        ;;
    403)
        echo "❌ PERMISSION DENIED"
        echo "   Your user account doesn't have permission to send emails"
        echo "   This endpoint requires TEACHER role"
        echo ""
        echo "   Troubleshooting:"
        echo "   1. Verify your user role in the database:"
        echo "      SELECT id, email, role, school_id FROM users WHERE email = 'your-email@example.com';"
        echo "   2. Check if role is in the JWT token (decode at jwt.io)"
        echo "   3. Verify the authentication dependency extracts role correctly"
        ;;
    422)
        echo "❌ VALIDATION ERROR"
        echo "   Request data is invalid"
        ;;
    429)
        echo "⚠️  RATE LIMIT EXCEEDED"
        echo "   You've hit the rate limit (10 emails per hour for teachers)"
        echo "   This is expected behavior after sending multiple emails"
        ;;
    500)
        echo "❌ SERVER ERROR"
        echo "   Internal server error"
        ;;
    *)
        echo "⚠️  Unexpected HTTP Status: $HTTP_STATUS"
        ;;
esac

echo ""
echo "========================================"
echo ""
echo "To verify your user role and permissions:"
echo ""
echo "1. Decode your JWT token at https://jwt.io"
echo "   Look for 'role' claim in the payload"
echo ""
echo "2. Check database:"
echo "   docker exec -it youspeak-db psql -U youspeak_user -d youspeak_db -c \\"
echo "     \"SELECT id, email, role, school_id FROM users WHERE email = 'your-email';\""
echo ""
