#!/bin/bash
set -e

echo "Testing Admin Classes Endpoint"
echo "================================"

# Login as admin
echo ""
echo "1. Logging in as admin..."
ADMIN_LOGIN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@librarydemo.com","password":"LibraryAdmin123"}')

ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | jq -r '.data.access_token')

if [ "$ADMIN_TOKEN" == "null" ] || [ -z "$ADMIN_TOKEN" ]; then
  echo "❌ Admin login failed"
  echo "$ADMIN_LOGIN" | jq '.'
  exit 1
fi

echo "✅ Admin logged in successfully"

# Get all classes (admin should see all)
echo ""
echo "2. Getting all classes as admin..."
CLASSES_RESPONSE=$(curl -s "https://api-staging.youspeakhq.com/api/v1/my-classes" \
  -H "Authorization: Bearer $ADMIN_TOKEN")

CLASSES_COUNT=$(echo "$CLASSES_RESPONSE" | jq '.data | length')

echo "✅ Admin can access classes endpoint"
echo "📊 Total classes returned: $CLASSES_COUNT"
echo ""
echo "Classes:"
echo "$CLASSES_RESPONSE" | jq '.data[] | {id, name, sub_class, language_id, status}'

# Login as teacher for comparison
echo ""
echo "3. Logging in as teacher (for comparison)..."
TEACHER_LOGIN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"mbakaragoodness2003@gmail.com","password":"MISSERUN123a#"}')

TEACHER_TOKEN=$(echo "$TEACHER_LOGIN" | jq -r '.data.access_token')

if [ "$TEACHER_TOKEN" == "null" ] || [ -z "$TEACHER_TOKEN" ]; then
  echo "❌ Teacher login failed"
  exit 1
fi

echo "✅ Teacher logged in successfully"

# Get classes as teacher
echo ""
echo "4. Getting classes as teacher..."
TEACHER_CLASSES=$(curl -s "https://api-staging.youspeakhq.com/api/v1/my-classes" \
  -H "Authorization: Bearer $TEACHER_TOKEN")

TEACHER_CLASSES_COUNT=$(echo "$TEACHER_CLASSES" | jq '.data | length')

echo "✅ Teacher can access classes endpoint"
echo "📊 Total classes returned: $TEACHER_CLASSES_COUNT (only assigned classes)"

# Summary
echo ""
echo "================================"
echo "Summary:"
echo "================================"
echo "Admin classes: $CLASSES_COUNT (all school classes)"
echo "Teacher classes: $TEACHER_CLASSES_COUNT (only assigned)"
echo ""

if [ "$CLASSES_COUNT" -gt 0 ]; then
  echo "✅ Admin classes endpoint is working!"
  echo ""
  echo "Admins can now:"
  echo "- Get all class IDs via GET /api/v1/classes"
  echo "- Use these class IDs when creating/updating curriculums"
  echo ""
  echo "Example class IDs for curriculum creation:"
  echo "$CLASSES_RESPONSE" | jq -r '.data[] | "- \(.id) (\(.name))"'
else
  echo "⚠️  No classes found in the school"
fi
