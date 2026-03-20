#!/bin/bash

# Test script for arena creation with timezone-aware datetime on staging
# Usage: ./test-arena-staging.sh YOUR_JWT_TOKEN CLASS_ID

if [ -z "$1" ]; then
    echo "❌ Error: JWT token required"
    echo "Usage: ./test-arena-staging.sh YOUR_JWT_TOKEN [CLASS_ID]"
    echo ""
    echo "Get your JWT token from:"
    echo "  1. Login to the frontend app (staging)"
    echo "  2. Open browser DevTools → Application/Storage → Local Storage"
    echo "  3. Copy the JWT token"
    exit 1
fi

JWT_TOKEN="$1"
CLASS_ID="${2:-a4d704c8-e76e-44c5-8dce-e6d3703b613d}"

echo "🧪 Testing Arena Creation on Staging"
echo "===================================="
echo "Endpoint: https://api-staging.youspeakhq.com/api/v1/arenas"
echo "Class ID: $CLASS_ID"
echo ""

# Test with timezone-aware datetime (the format that was failing)
RESPONSE=$(curl -X POST "https://api-staging.youspeakhq.com/api/v1/arenas" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "class_id": "'"$CLASS_ID"'",
    "title": "Test Arena - Timezone Fix Verification",
    "description": "Testing timezone-aware datetime (2026-03-17T10:55:01.762Z)",
    "rules": ["Rule 1: Speak clearly", "Rule 2: Be respectful"],
    "criteria": {
      "pronunciation": 40,
      "fluency": 30,
      "engagement": 30
    },
    "start_time": "2026-03-17T15:00:00.000Z",
    "duration_minutes": 45
  }' \
  -w "\nHTTP_STATUS:%{http_code}" \
  -s)

# Extract HTTP status
HTTP_STATUS=$(echo "$RESPONSE" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed 's/HTTP_STATUS:[0-9]*//')

echo "📥 Response:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Check result
if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "201" ]; then
    echo "✅ SUCCESS! Arena created with timezone-aware datetime"
    echo ""
    echo "Verified:"
    echo "  • Frontend sent: 2026-03-17T15:00:00.000Z (timezone-aware)"
    echo "  • Backend accepted and stripped timezone"
    echo "  • Database insert successful"
    echo ""

    # Extract arena ID if present
    ARENA_ID=$(echo "$BODY" | jq -r '.data.id // empty' 2>/dev/null)
    if [ ! -z "$ARENA_ID" ]; then
        echo "🎯 Created Arena ID: $ARENA_ID"
        echo ""
        echo "Verify in database:"
        echo "  SELECT id, title, start_time FROM arenas WHERE id = '$ARENA_ID';"
    fi
elif [ "$HTTP_STATUS" = "401" ]; then
    echo "❌ AUTHENTICATION FAILED"
    echo "Your JWT token is invalid or expired"
    echo "Please get a fresh token from the frontend app"
elif [ "$HTTP_STATUS" = "403" ]; then
    echo "❌ PERMISSION DENIED"
    echo "The user must be a TEACHER role"
    echo "Class ID might also be invalid: $CLASS_ID"
elif [ "$HTTP_STATUS" = "500" ]; then
    echo "❌ SERVER ERROR (500)"
    echo "The timezone fix might not be deployed yet, or there's another issue"
    echo ""
    echo "Check logs:"
    echo "  aws logs tail /ecs/youspeak-api --region us-east-1 --since 5m --format short | grep -i error"
else
    echo "⚠️  HTTP $HTTP_STATUS"
    echo "Response: $BODY"
fi

echo ""
echo "===================================="
