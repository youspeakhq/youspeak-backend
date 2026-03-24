#!/bin/bash

# Test script for email sending API on staging
# Usage: ./test-email-staging.sh [JWT_TOKEN]

STAGING_URL="https://api-staging.youspeakhq.com"
API_PREFIX="/api/v1"

echo "🧪 Testing Email Sending API on Staging"
echo "========================================"
echo ""

# If JWT token provided as argument, use it
if [ ! -z "$1" ]; then
    JWT_TOKEN="$1"
    echo "✓ Using provided JWT token"
else
    echo "📝 No JWT token provided, need to register/login first"
    echo ""
    echo "Option 1: Register a new teacher account"
    echo "Option 2: Login with existing account"
    echo ""
    read -p "Choose option (1 or 2): " OPTION

    if [ "$OPTION" = "1" ]; then
        # Register new teacher
        echo ""
        echo "Registering new teacher account..."
        TIMESTAMP=$(date +%s)
        REGISTER_RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/auth/register" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "teacher-test-'"$TIMESTAMP"'@example.com",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "Teacher",
                "role": "teacher",
                "school_code": "TEST_SCHOOL"
            }' \
            -w "\nHTTP_STATUS:%{http_code}" \
            -s)

        HTTP_STATUS=$(echo "$REGISTER_RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
        BODY=$(echo "$REGISTER_RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

        if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "201" ]; then
            echo "✅ Registration successful!"
            JWT_TOKEN=$(echo "$BODY" | jq -r '.data.access_token // .access_token // empty')
            USER_EMAIL=$(echo "$BODY" | jq -r '.data.email // .email // empty')
            echo "Email: $USER_EMAIL"
        else
            echo "❌ Registration failed (HTTP $HTTP_STATUS)"
            echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
            exit 1
        fi

    elif [ "$OPTION" = "2" ]; then
        # Login with existing account
        echo ""
        read -p "Email: " LOGIN_EMAIL
        read -sp "Password: " LOGIN_PASSWORD
        echo ""

        LOGIN_RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/auth/login" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "'"$LOGIN_EMAIL"'",
                "password": "'"$LOGIN_PASSWORD"'"
            }' \
            -w "\nHTTP_STATUS:%{http_code}" \
            -s)

        HTTP_STATUS=$(echo "$LOGIN_RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
        BODY=$(echo "$LOGIN_RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

        if [ "$HTTP_STATUS" = "200" ]; then
            echo "✅ Login successful!"
            JWT_TOKEN=$(echo "$BODY" | jq -r '.data.access_token // .access_token // empty')
        else
            echo "❌ Login failed (HTTP $HTTP_STATUS)"
            echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
            exit 1
        fi
    else
        echo "❌ Invalid option"
        exit 1
    fi
    echo ""
fi

if [ -z "$JWT_TOKEN" ]; then
    echo "❌ No JWT token available"
    exit 1
fi

echo "🔑 JWT Token obtained (first 20 chars): ${JWT_TOKEN:0:20}..."
echo ""

# Test 1: Send email to single recipient
echo "📧 Test 1: Sending email to single recipient"
echo "--------------------------------------------"
TEST1_RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/emails/send" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d '{
        "recipients": ["student1@example.com"],
        "subject": "Test Email from Staging",
        "html_body": "<html><body><h1>Hello!</h1><p>This is a test email from staging.</p></body></html>"
    }' \
    -w "\nHTTP_STATUS:%{http_code}" \
    -s)

HTTP_STATUS=$(echo "$TEST1_RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
BODY=$(echo "$TEST1_RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

echo "Status: $HTTP_STATUS"
echo "Response:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Test 1 PASSED: Single recipient email sent successfully"
    EMAIL_LOG_ID=$(echo "$BODY" | jq -r '.data.email_log_id // empty')
    echo "   Email Log ID: $EMAIL_LOG_ID"
elif [ "$HTTP_STATUS" = "429" ]; then
    echo "⚠️  Test 1 SKIPPED: Rate limit reached (this is expected behavior)"
elif [ "$HTTP_STATUS" = "403" ]; then
    echo "❌ Test 1 FAILED: Permission denied (user might not be a teacher)"
elif [ "$HTTP_STATUS" = "401" ]; then
    echo "❌ Test 1 FAILED: Authentication failed (invalid or expired token)"
else
    echo "❌ Test 1 FAILED: Unexpected status code"
fi
echo ""

# Test 2: Send email to multiple recipients
echo "📧 Test 2: Sending email to multiple recipients"
echo "------------------------------------------------"
TEST2_RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/emails/send" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d '{
        "recipients": [
            "student1@example.com",
            "student2@example.com",
            "student3@example.com"
        ],
        "subject": "Group Announcement",
        "html_body": "<html><body><h1>Important Update</h1><p>Please check your assignments.</p></body></html>",
        "reply_to": "teacher@school.com"
    }' \
    -w "\nHTTP_STATUS:%{http_code}" \
    -s)

HTTP_STATUS=$(echo "$TEST2_RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
BODY=$(echo "$TEST2_RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

echo "Status: $HTTP_STATUS"
echo "Response:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Test 2 PASSED: Multiple recipients email sent successfully"
    TOTAL=$(echo "$BODY" | jq -r '.data.total_recipients // 0')
    SUCCESS=$(echo "$BODY" | jq -r '.data.successful_sends // 0')
    FAILED=$(echo "$BODY" | jq -r '.data.failed_sends // 0')
    echo "   Total: $TOTAL, Success: $SUCCESS, Failed: $FAILED"
elif [ "$HTTP_STATUS" = "429" ]; then
    echo "⚠️  Test 2 SKIPPED: Rate limit reached (this is expected behavior)"
elif [ "$HTTP_STATUS" = "403" ]; then
    echo "❌ Test 2 FAILED: Permission denied"
elif [ "$HTTP_STATUS" = "401" ]; then
    echo "❌ Test 2 FAILED: Authentication failed"
else
    echo "❌ Test 2 FAILED: Unexpected status code"
fi
echo ""

# Test 3: Validation error test (empty recipients)
echo "📧 Test 3: Validation error (empty recipients)"
echo "-----------------------------------------------"
TEST3_RESPONSE=$(curl -X POST "${STAGING_URL}${API_PREFIX}/emails/send" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d '{
        "recipients": [],
        "subject": "Test",
        "html_body": "<html><body>Test</body></html>"
    }' \
    -w "\nHTTP_STATUS:%{http_code}" \
    -s)

HTTP_STATUS=$(echo "$TEST3_RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)

if [ "$HTTP_STATUS" = "422" ]; then
    echo "✅ Test 3 PASSED: Validation error correctly returned (422)"
else
    echo "❌ Test 3 FAILED: Expected 422, got $HTTP_STATUS"
fi
echo ""

echo "========================================"
echo "🎯 Test Summary"
echo "========================================"
echo ""
echo "Staging URL: ${STAGING_URL}"
echo "Endpoint: ${API_PREFIX}/emails/send"
echo ""
echo "To test manually with this token:"
echo ""
echo 'curl -X POST "'"${STAGING_URL}${API_PREFIX}"'/emails/send" \'
echo '  -H "Content-Type: application/json" \'
echo '  -H "Authorization: Bearer '"$JWT_TOKEN"'" \'
echo "  -d '{"
echo '    "recipients": ["test@example.com"],'
echo '    "subject": "Test Email",'
echo '    "html_body": "<html><body><h1>Test</h1></body></html>"'
echo "  }'"
echo ""
