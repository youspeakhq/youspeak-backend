#!/bin/bash
#
# Convert 2 curriculums to library_master type via API
# Run this after commit da6f3d8 is deployed to staging
#

set -e

echo "================================================"
echo "Convert Curriculums to Library Type (via API)"
echo "================================================"
echo

# Get credentials
echo "Getting access token..."
TOKEN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.access_token')

SCHOOL_ID=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.school_id')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "❌ Failed to get access token"
  exit 1
fi

echo "✅ Access token obtained"
echo "✅ School ID: $SCHOOL_ID"
echo

# Get current curriculums
echo "Fetching current curriculums..."
CURRICULUMS=$(curl -s "https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&page_size=5" \
  -H "Authorization: Bearer $TOKEN")

echo "Current curriculums:"
echo "$CURRICULUMS" | jq '.data[] | {id, title, source_type}'
echo

# Extract IDs for first 2 curriculums
ID1=$(echo "$CURRICULUMS" | jq -r '.data[0].id')
ID2=$(echo "$CURRICULUMS" | jq -r '.data[1].id')
TITLE1=$(echo "$CURRICULUMS" | jq -r '.data[0].title')
TITLE2=$(echo "$CURRICULUMS" | jq -r '.data[1].title')

if [ -z "$ID1" ] || [ "$ID1" = "null" ]; then
  echo "❌ No curriculums found to convert"
  exit 1
fi

echo "Converting 2 curriculums to library_master type:"
echo "  1. $TITLE1 (ID: $ID1)"
echo "  2. $TITLE2 (ID: $ID2)"
echo

# Convert curriculum 1
echo "Converting curriculum 1..."
RESULT1=$(curl -s -X PATCH "https://api-staging.youspeakhq.com/api/v1/curriculums/$ID1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-School-Id: $SCHOOL_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"source_type\": \"library_master\",
    \"title\": \"[LIBRARY] $TITLE1\"
  }")

SUCCESS1=$(echo "$RESULT1" | jq -r '.success')
if [ "$SUCCESS1" = "true" ]; then
  echo "✅ Curriculum 1 converted successfully"
  echo "$RESULT1" | jq '{id: .data.id, title: .data.title, source_type: .data.source_type}'
else
  echo "❌ Failed to convert curriculum 1"
  echo "$RESULT1" | jq '.'
fi
echo

# Convert curriculum 2
if [ -n "$ID2" ] && [ "$ID2" != "null" ]; then
  echo "Converting curriculum 2..."
  RESULT2=$(curl -s -X PATCH "https://api-staging.youspeakhq.com/api/v1/curriculums/$ID2" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-School-Id: $SCHOOL_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"source_type\": \"library_master\",
      \"title\": \"[LIBRARY] $TITLE2\"
    }")

  SUCCESS2=$(echo "$RESULT2" | jq -r '.success')
  if [ "$SUCCESS2" = "true" ]; then
    echo "✅ Curriculum 2 converted successfully"
    echo "$RESULT2" | jq '{id: .data.id, title: .data.title, source_type: .data.source_type}'
  else
    echo "❌ Failed to convert curriculum 2"
    echo "$RESULT2" | jq '.'
  fi
  echo
fi

# Verify library curriculums exist
echo "================================================"
echo "Verification: Fetching library curriculums only"
echo "================================================"
echo

LIBRARY_RESULT=$(curl -s "https://api-staging.youspeakhq.com/api/v1/curriculums?source_type=library_master&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN")

LIBRARY_TOTAL=$(echo "$LIBRARY_RESULT" | jq -r '.meta.total')

echo "Library curriculums found: $LIBRARY_TOTAL"
echo

if [ "$LIBRARY_TOTAL" -gt 0 ]; then
  echo "Library curriculums:"
  echo "$LIBRARY_RESULT" | jq '.data[] | {title, source_type, status}'
  echo
  echo "✅ SUCCESS! Library curriculum filter is working!"
  echo
  echo "Frontend can now use:"
  echo "  GET /api/v1/curriculums?source_type=library_master"
else
  echo "⚠️  No library curriculums found. Conversion may have failed."
fi

echo
echo "================================================"
echo "Done!"
echo "================================================"
