#!/bin/bash
# Test Batch Team Creation on Staging
set -e

STAGING_API="https://api-staging.youspeakhq.com/api/v1"

# To get a teacher token, run ./register_teacher_staging.sh first
TEACHER_TOKEN=$1

if [ -z "$TEACHER_TOKEN" ]; then
    echo "Usage: ./test-batch-teams-staging.sh <TEACHER_TOKEN>"
    exit 1
fi

echo "=== Fetching my classes ==="
CLASSES=$(curl -s -H "Authorization: Bearer $TEACHER_TOKEN" "${STAGING_API}/my-classes")
CLASS_ID=$(echo "$CLASSES" | jq -r '.data[0].id')

if [ "$CLASS_ID" == "null" ]; then
    echo "No classes found for this teacher."
    exit 1
fi
echo "Using Class ID: $CLASS_ID"

echo "=== Creating Arena ==="
ARENA_RESP=$(curl -s -X POST "${STAGING_API}/arenas" \
    -H "Authorization: Bearer $TEACHER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"class_id\": \"$CLASS_ID\",
        \"title\": \"Staging Batch Test $(date +%s)\",
        \"criteria\": {\"Participation\": 100}
    }")
ARENA_ID=$(echo "$ARENA_RESP" | jq -r '.data.id')
echo "Created Arena ID: $ARENA_ID"

echo "=== Fetching students for class ==="
STUDENTS=$(curl -s -H "Authorization: Bearer $TEACHER_TOKEN" "${STAGING_API}/students?class_id=${CLASS_ID}")
# Get up to 3 student IDs
STUDENT_IDS=$(echo "$STUDENTS" | jq -r '.data[:3] | .[].id')
ID_ARRAY=($STUDENT_IDS)

if [ ${#ID_ARRAY[@]} -lt 2 ]; then
    echo "Not enough students in class to test teams."
    exit 1
fi

echo "=== Initializing Arena (Collaborative) ==="
curl -s -X POST "${STAGING_API}/arenas/${ARENA_ID}/initialize" \
    -H "Authorization: Bearer $TEACHER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"arena_mode\": \"collaborative\",
        \"judging_mode\": \"teacher_only\",
        \"student_selection_mode\": \"manual\",
        \"selected_student_ids\": $(echo "$STUDENTS" | jq -c '.data[:3] | [.[].id]'),
        \"team_size\": 2
    }" > /dev/null

echo "=== Testing Batch Team Creation (Version 1.0.3 required) ==="
BATCH_RESP=$(curl -s -w "\n%{http_code}" -X POST "${STAGING_API}/arenas/${ARENA_ID}/teams/batch" \
    -H "Authorization: Bearer $TEACHER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"teams\": [
            {\"team_name\": \"Staging Alpha\", \"student_ids\": [\"${ID_ARRAY[0]}\"]},
            {\"team_name\": \"Staging Beta\", \"student_ids\": [\"${ID_ARRAY[1]}\"]}
        ]
    }")

HTTP_CODE=$(echo "$BATCH_RESP" | tail -n1)
BODY=$(echo "$BATCH_RESP" | sed '$d')

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ Batch Team Creation Success!"
    echo "$BODY" | jq .
else
    echo "❌ Batch Team Creation Failed (HTTP $HTTP_CODE)"
    echo "$BODY"
    if [ "$HTTP_CODE" == "404" ]; then
        echo "Note: 404 likely means version 1.0.3 is not yet live on staging."
    fi
fi
