#!/usr/bin/env bash
# Quick script to create a teacher account on staging
# Usage: ./create_teacher_account.sh

set -e

BASE_URL="https://api-staging.youspeakhq.com"
ADMIN_EMAIL="admin-$(date +%s)@example.com"
ADMIN_PASSWORD="AdminPass123!"
TEACHER_EMAIL="teacher-$(date +%s)@example.com"
TEACHER_PASSWORD="TeacherPass123!"

echo "🎓 Creating Teacher Account on Staging"
echo "======================================"
echo ""

# Step 1: Create school admin account
echo "📝 Step 1: Creating school admin account..."
REG_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "account_type": "school",
    "email": "'"$ADMIN_EMAIL"'",
    "password": "'"$ADMIN_PASSWORD"'",
    "school_name": "Test School",
    "admin_first_name": "Admin",
    "admin_last_name": "User"
  }')

echo "✅ School registered"
echo ""

# Step 2: Login as admin
echo "🔐 Step 2: Logging in as admin..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$ADMIN_EMAIL"'",
    "password": "'"$ADMIN_PASSWORD"'"
  }')

ADMIN_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token // empty')

if [ -z "$ADMIN_TOKEN" ]; then
  echo "❌ Admin login failed:"
  echo "$LOGIN_RESP" | jq '.'
  exit 1
fi

echo "✅ Admin logged in"
echo ""

# Step 3: Create teacher invite
echo "👨‍🏫 Step 3: Creating teacher invite..."
INVITE_RESP=$(curl -s -X POST "$BASE_URL/api/v1/teachers" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$TEACHER_EMAIL"'",
    "first_name": "Teacher",
    "last_name": "Demo"
  }')

ACCESS_CODE=$(echo "$INVITE_RESP" | jq -r '.data.access_code // empty')

if [ -z "$ACCESS_CODE" ]; then
  echo "❌ Teacher invite failed:"
  echo "$INVITE_RESP" | jq '.'
  exit 1
fi

echo "✅ Teacher invite created"
echo "🎫 Access code: $ACCESS_CODE"
echo ""

# Step 4: Register teacher
echo "📝 Step 4: Registering teacher account..."
TEACHER_REG=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/teacher" \
  -H "Content-Type: application/json" \
  -d '{
    "access_code": "'"$ACCESS_CODE"'",
    "email": "'"$TEACHER_EMAIL"'",
    "password": "'"$TEACHER_PASSWORD"'",
    "first_name": "Teacher",
    "last_name": "Demo"
  }')

echo "✅ Teacher account created"
echo ""

# Step 5: Login as teacher (verify it works)
echo "🔐 Step 5: Verifying teacher login..."
TEACHER_LOGIN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$TEACHER_EMAIL"'",
    "password": "'"$TEACHER_PASSWORD"'"
  }')

TEACHER_TOKEN=$(echo "$TEACHER_LOGIN" | jq -r '.data.access_token // empty')

if [ -z "$TEACHER_TOKEN" ]; then
  echo "❌ Teacher login failed:"
  echo "$TEACHER_LOGIN" | jq '.'
  exit 1
fi

echo "✅ Teacher login verified"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✨ SUCCESS! Your teacher account is ready:"
echo ""
echo "📧 Email:    $TEACHER_EMAIL"
echo "🔑 Password: $TEACHER_PASSWORD"
echo "🎫 Token:    ${TEACHER_TOKEN:0:50}..."
echo ""
echo "🔗 Login at: https://staging.youspeakhq.com"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
