#!/bin/bash
# Test Curriculum Merge Proposal Permissions on Staging
set -e

STAGING_API="https://api-staging.youspeakhq.com/api/v1"

# To get a teacher token, run ./register_teacher_staging.sh first
TEACHER_TOKEN=$1

if [ -z "$TEACHER_TOKEN" ]; then
    echo "Usage: ./test-merge-permissions-staging.sh <TEACHER_TOKEN>"
    exit 1
fi

FAKE_ID="00000000-0000-0000-0000-000000000000"

echo "=== Testing Merge Proposal Permission (Teacher) ==="
RESP=$(curl -s -w "\n%{http_code}" -X POST "${STAGING_API}/curriculums/${FAKE_ID}/merge/propose" \
    -H "Authorization: Bearer $TEACHER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"library_curriculum_id\": \"$FAKE_ID\"
    }")

HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" == "404" ]; then
    echo "✅ Success! Received 404 (Not Found) instead of 403 (Forbidden)."
    echo "This confirms the teacher has permission to hit the endpoint."
elif [ "$HTTP_CODE" == "403" ]; then
    echo "❌ Failed: Received 403 Forbidden. Version 1.0.3 is likely not yet live."
else
    echo "Received HTTP $HTTP_CODE"
    echo "$BODY"
fi
