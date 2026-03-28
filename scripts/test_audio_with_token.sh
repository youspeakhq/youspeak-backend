#!/bin/bash
# Test audio meeting creation with your auth token
# Usage: ./test_audio_with_token.sh YOUR_AUTH_TOKEN ARENA_ID

BASE_URL="https://api-staging.youspeakhq.com/api/v1"

if [ -z "$1" ]; then
    echo "Usage: $0 YOUR_AUTH_TOKEN ARENA_ID"
    echo ""
    echo "Example:"
    echo "  $0 'eyJhbGc...' '4d50f175-7b24-4346-b259-5b364213ad3b'"
    exit 1
fi

AUTH_TOKEN="$1"
ARENA_ID="${2:-4d50f175-7b24-4346-b259-5b364213ad3b}"

echo "=== Testing Audio Token Generation ==="
echo "Arena ID: $ARENA_ID"
echo ""

echo "1. Testing audio token endpoint..."
RESPONSE=$(curl -s -X POST "$BASE_URL/arenas/$ARENA_ID/audio/token" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq '.'
echo ""

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null 2>&1; then
    echo "✓ SUCCESS: Audio token generated!"
    echo ""
    echo "Token details:"
    echo "$RESPONSE" | jq '.data'
else
    echo "✗ FAILED: $(echo $RESPONSE | jq -r '.error.message')"
    echo ""
    echo "Full error:"
    echo "$RESPONSE" | jq '.error'
fi
