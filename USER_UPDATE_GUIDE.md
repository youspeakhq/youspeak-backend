# User Update Functionality Guide

## Overview

The user update endpoint allows users to update their profile information including email, full name, and password.

**Endpoint:** `PUT /api/v1/users/{user_id}`

## How It Works

### 1. Authentication & Permissions

**Two scenarios are allowed:**
1. **Users updating their own profile** - Any authenticated user can update their own data
2. **Admins updating any user** - School admins can update any user in their school

**Permission Logic:**
```python
# From app/api/v1/endpoints/users.py:111-115
if current_user.id != user_id and current_user.role != UserRole.SCHOOL_ADMIN:
    raise HTTPException(
        status_code=403,
        detail="Not enough permissions"
    )
```

### 2. Updatable Fields

**Schema:** `UserUpdate` (defined in [app/schemas/user.py:33-38](app/schemas/user.py#L33-L38))

```python
class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
```

**Fields:**
- `email` - New email address (optional)
- `full_name` - New full name (optional)
- `password` - New password (optional, min 8 characters)

**Important:** All fields are optional - you only need to send the fields you want to update.

### 3. Update Process

**Service Logic:** `UserService.update_user()` ([app/services/user_service.py:199-229](app/services/user_service.py#L199-L229))

```python
async def update_user(db: AsyncSession, user_id: UUID, user_update: UserUpdate):
    # 1. Get the user
    db_user = await UserService.get_user_by_id(db, user_id)
    if not db_user:
        return None

    # 2. Extract only provided fields
    update_data = user_update.model_dump(exclude_unset=True)

    # 3. Hash password if provided
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # 4. Apply updates
    for field, value in update_data.items():
        setattr(db_user, field, value)

    # 5. Save to database
    await db.commit()
    await db.refresh(db_user)

    return db_user
```

**Key Features:**
- Only updates fields that are explicitly provided (partial updates)
- Automatically hashes passwords before storing
- Returns the updated user object
- Returns HTTP 404 if user doesn't exist

## Usage Examples

### Example 1: Update Your Own Profile

#### Using curl

```bash
# Get your access token first
TOKEN="your_access_token_here"
USER_ID="your_user_id_here"

# Update full name only
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith"
  }'
```

**Response:**
```json
{
  "id": "62d5ec3d-0ab0-40bc-bfa2-b45c3ffbe5e0",
  "email": "test@example.com",
  "full_name": "John Smith",
  "is_active": true,
  "is_superuser": false,
  "role": "school_admin",
  "school_id": "3d29724c-ce8b-47c8-b37e-e1101f966d71",
  "profile_picture_url": null,
  "student_number": null,
  "is_verified": true,
  "created_at": "2026-03-07T08:51:15.123456",
  "updated_at": "2026-03-07T09:30:45.123456",
  "last_login": null,
  "classrooms": []
}
```

#### Using JavaScript/Frontend

```javascript
const updateUser = async (userId, updates) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `https://api-staging.youspeakhq.com/api/v1/users/${userId}`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updates)
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Update failed');
  }

  return await response.json();
};

// Usage examples:

// Update name only
await updateUser(userId, {
  full_name: "Jane Doe"
});

// Update email only
await updateUser(userId, {
  email: "newemail@example.com"
});

// Update password only
await updateUser(userId, {
  password: "NewSecurePassword123"
});

// Update multiple fields
await updateUser(userId, {
  full_name: "Jane Doe",
  email: "jane.doe@example.com",
  password: "NewSecurePassword123"
});
```

### Example 2: Update Email

```bash
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newemail@example.com"
  }'
```

### Example 3: Update Password

```bash
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "NewSecurePassword123"
  }'
```

**Important:** Password must be at least 8 characters.

### Example 4: Update Multiple Fields

```bash
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "password": "NewSecurePassword123"
  }'
```

### Example 5: Admin Updating Another User

```bash
# Admin token (school_admin role)
ADMIN_TOKEN="admin_access_token_here"
OTHER_USER_ID="uuid-of-another-user"

curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$OTHER_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Updated by Admin",
    "email": "updated@example.com"
  }'
```

## Using Swagger UI

**Interactive Testing:** https://api-staging.youspeakhq.com/docs

### Steps:

1. **Authenticate:**
   - Click "Authorize" button (top right)
   - Enter your access token: `Bearer your_token_here`
   - Click "Authorize" then "Close"

2. **Find the Endpoint:**
   - Scroll to "users" section
   - Find `PUT /api/v1/users/{user_id}`

3. **Try it out:**
   - Click "Try it out"
   - Enter the `user_id` (your user ID)
   - Enter the request body with fields to update:
     ```json
     {
       "full_name": "New Name"
     }
     ```
   - Click "Execute"

4. **View Response:**
   - See the updated user object in the response
   - HTTP 200 = Success
   - HTTP 403 = Permission denied
   - HTTP 404 = User not found

## Error Handling

### Common Errors

#### 1. Unauthorized (401)
```json
{
  "detail": "Not authenticated"
}
```
**Cause:** Missing or invalid access token
**Solution:** Login and get a fresh access token

#### 2. Forbidden (403)
```json
{
  "detail": "Not enough permissions"
}
```
**Cause:** Trying to update another user's profile without admin role
**Solution:** Only update your own profile, or login as admin

#### 3. Not Found (404)
```json
{
  "detail": "User not found"
}
```
**Cause:** Invalid user_id
**Solution:** Verify the user_id exists

#### 4. Validation Error (422)
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": {"min_length": 8}
    }
  ]
}
```
**Cause:** Invalid data (e.g., password too short, invalid email)
**Solution:** Fix the data according to validation rules

## Complete Test Script

Save this as `test_user_update.sh`:

```bash
#!/usr/bin/env bash
# Test user update functionality
# Usage: ./test_user_update.sh [EMAIL] [PASSWORD]

set -e

BASE_URL="https://api-staging.youspeakhq.com"
EMAIL="${1:-test-$(date +%s)@example.com}"
PASSWORD="${2:-TestPassword123}"

echo "🔧 Testing User Update Functionality"
echo "====================================="
echo ""

# Step 1: Register
echo "📝 Step 1: Registering..."
REG_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/register/school" \
  -H "Content-Type: application/json" \
  -d '{
    "account_type": "school",
    "email": "'"$EMAIL"'",
    "password": "'"$PASSWORD"'",
    "school_name": "Test School",
    "admin_first_name": "Test",
    "admin_last_name": "User"
  }')
echo "$REG_RESP" | jq '.'
echo ""

# Step 2: Login
echo "🔐 Step 2: Logging in..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$EMAIL"'","password":"'"$PASSWORD"'"}')

TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token')
USER_ID=$(echo "$LOGIN_RESP" | jq -r '.data.user_id')

echo "✅ Logged in"
echo "User ID: $USER_ID"
echo "Token: ${TOKEN:0:30}..."
echo ""

# Step 3: Get current user info
echo "👤 Step 3: Getting current user info..."
curl -s -X GET "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Step 4: Update full name
echo "✏️  Step 4: Updating full name..."
curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Smith"}' | jq '.'
echo ""

# Step 5: Update email
echo "📧 Step 5: Updating email..."
NEW_EMAIL="updated-$(date +%s)@example.com"
curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'"}' | jq '.'
echo ""

# Step 6: Update password
echo "🔑 Step 6: Updating password..."
NEW_PASSWORD="NewPassword456"
curl -s -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"'"$NEW_PASSWORD"'"}' | jq '.'
echo ""

# Step 7: Verify new credentials work
echo "✅ Step 7: Verifying new credentials..."
LOGIN_RESP2=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$NEW_EMAIL"'","password":"'"$NEW_PASSWORD"'"}')

if echo "$LOGIN_RESP2" | jq -e '.success' > /dev/null; then
  echo "✅ New credentials work!"
else
  echo "❌ New credentials failed:"
  echo "$LOGIN_RESP2" | jq '.'
fi
echo ""

# Step 8: Try to update without permission
echo "🚫 Step 8: Testing permission check (should fail)..."
FAKE_USER_ID="00000000-0000-0000-0000-000000000000"
FAIL_RESP=$(curl -s -w "\nHTTP: %{http_code}" \
  -X PUT "$BASE_URL/api/v1/users/$FAKE_USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Should Fail"}')
echo "$FAIL_RESP"
echo ""

echo "✅ All tests complete!"
```

## Related Endpoints

### Change Password (Alternative Method)
If you want to change password with current password verification:

**Endpoint:** `POST /api/v1/users/change-password`

```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/users/change-password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPassword123",
    "new_password": "NewPassword456"
  }'
```

**Difference:**
- `PUT /users/{user_id}` - Update password without verification (admin can reset)
- `POST /users/change-password` - Requires current password verification (safer for self-service)

### Get User Info
**Endpoint:** `GET /api/v1/users/{user_id}`

```bash
curl -X GET "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### List All Users (Admin Only)
**Endpoint:** `GET /api/v1/users`

```bash
curl -X GET "https://api-staging.youspeakhq.com/api/v1/users?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Security Notes

1. **Password Hashing:** Passwords are automatically hashed using bcrypt before storage
2. **Partial Updates:** Only send fields you want to update - others remain unchanged
3. **Permission Check:** Users can only update their own data (unless admin)
4. **Token Required:** All requests must include a valid Bearer token
5. **Token Expiration:** Access tokens expire in 15 minutes - refresh if needed

## Summary

**How the user update works:**

1. ✅ **Authenticate** - Get access token via login
2. ✅ **Call endpoint** - `PUT /api/v1/users/{user_id}` with token
3. ✅ **Send updates** - JSON body with fields to update (all optional)
4. ✅ **Get response** - Updated user object returned
5. ✅ **Permissions** - You can update your own profile, admins can update anyone

**Key Points:**
- All fields are optional - partial updates supported
- Passwords are automatically hashed
- Permission check ensures users can only update themselves (unless admin)
- Works both via curl and in browser (Swagger UI)

Need help? Check the [Swagger docs](https://api-staging.youspeakhq.com/docs) for interactive testing! 🚀
