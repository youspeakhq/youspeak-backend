# User Update Functionality - Key Findings

## ✅ Test Results

I tested the user update endpoint on staging and found:

**What Works:**
- ✅ Updating email
- ✅ Updating password
- ✅ Authentication and permissions
- ✅ Updated credentials work after change

**What Doesn't Work:**
- ❌ Updating `full_name` (schema/model mismatch)

## 🐛 Bug Found: full_name Update Not Working

### The Issue

When you try to update `full_name`, it doesn't actually update in the database:

```bash
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Smith"}'

# Response shows: "full_name": null  ❌
```

### Root Cause

**Schema vs Model Mismatch:**

1. **UserUpdate schema** ([app/schemas/user.py:33-38](app/schemas/user.py#L33-L38)):
   ```python
   class UserUpdate(BaseModel):
       email: Optional[EmailStr] = None
       full_name: Optional[str] = None  # ← Accepts full_name
       password: Optional[str] = None
   ```

2. **User model** ([app/models/user.py:23-24,77-79](app/models/user.py#L23-L24)):
   ```python
   class User(BaseModel):
       first_name = Column(String(255), nullable=False)  # ← DB has first_name
       last_name = Column(String(255), nullable=False)   # ← DB has last_name

       @property
       def full_name(self) -> str:  # ← Read-only computed property
           return f"{self.first_name} {self.last_name}"
   ```

3. **Service logic** ([app/services/user_service.py:225-226](app/services/user_service.py#L225-L226)):
   ```python
   for field, value in update_data.items():
       setattr(db_user, field, value)  # ← Tries to set full_name (fails silently)
   ```

**Problem:** The schema accepts `full_name`, but the model only has `first_name` and `last_name` as writable fields. `full_name` is a read-only computed property, so `setattr()` fails silently.

## 💡 Solutions

### Option 1: Frontend Workaround (Immediate)

**Update first_name and last_name separately** (not currently supported by UserUpdate schema):

This won't work until we fix the schema:
```javascript
// This would work IF the schema accepted first_name/last_name
await updateUser(userId, {
  first_name: "John",
  last_name: "Smith"
});
```

### Option 2: Backend Fix (Recommended)

**Update the UserUpdate schema** to match the model:

```python
# app/schemas/user.py
class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None  # ← Add this
    last_name: Optional[str] = None   # ← Add this
    password: Optional[str] = Field(None, min_length=8)

    # Remove full_name or add logic to split it
```

### Option 3: Service Layer Fix (Alternative)

**Add logic to split full_name** in the service:

```python
# app/services/user_service.py
async def update_user(...):
    update_data = user_update.model_dump(exclude_unset=True)

    # Handle full_name → first_name/last_name split
    if "full_name" in update_data:
        full_name = update_data.pop("full_name")
        if full_name:
            parts = full_name.strip().split(None, 1)  # Split on first space
            update_data["first_name"] = parts[0]
            update_data["last_name"] = parts[1] if len(parts) > 1 else ""

    # ... rest of logic
```

## 🔧 How It Currently Works

### What You Can Update (Working ✅):

1. **Email:**
   ```bash
   curl -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"email":"newemail@example.com"}'
   ```

2. **Password:**
   ```bash
   curl -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"password":"NewPassword123"}'
   ```

3. **Multiple fields at once:**
   ```bash
   curl -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "email":"newemail@example.com",
       "password":"NewPassword123"
     }'
   ```

### What Doesn't Work (Bug 🐛):

**Updating name:**
```bash
curl -X PUT "$BASE_URL/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"John Smith"}'  # ← Won't work
```

## 📊 Test Results Summary

| Test | Status | Details |
|------|--------|---------|
| Register account | ✅ Pass | HTTP 200 |
| Login | ✅ Pass | Token received |
| Get user info | ✅ Pass | User data returned |
| Update email | ✅ Pass | Email changed successfully |
| Update password | ✅ Pass | Password changed successfully |
| **Update full_name** | ❌ **Fail** | **Returns null (bug)** |
| Verify new credentials | ✅ Pass | Can login with new email/password |
| Permission check | ✅ Pass | 403 for unauthorized update |

## 🎯 Recommendations

### For Frontend Team:

1. **Current workaround:** Don't use the name update feature until backend fixes it
2. **Alternative:** Users can update email and password (these work correctly)

### For Backend Team:

1. **Fix the schema/model mismatch**:
   - Either change UserUpdate to accept `first_name`/`last_name`
   - Or add service logic to split `full_name` into components

2. **Add validation:**
   - Ensure full_name split logic handles edge cases (single name, multiple spaces, etc.)

3. **Add tests:**
   - Write integration test for name updates
   - Current tests don't catch this bug

## 📖 Documentation Created

I've created comprehensive guides:

1. **[USER_UPDATE_GUIDE.md](USER_UPDATE_GUIDE.md)** - Complete guide with examples
2. **[test_user_update.sh](test_user_update.sh)** - Test script (executable)
3. **[STAGING_CURRICULUM_TEST_RESULTS.md](STAGING_CURRICULUM_TEST_RESULTS.md)** - Curriculum testing results

## 🔍 Code References

- User Update Endpoint: [app/api/v1/endpoints/users.py:100-124](app/api/v1/endpoints/users.py#L100-L124)
- User Update Schema: [app/schemas/user.py:33-38](app/schemas/user.py#L33-L38)
- User Model: [app/models/user.py:11-79](app/models/user.py#L11-L79)
- User Service: [app/services/user_service.py:199-231](app/services/user_service.py#L199-L231)

## ✅ Summary for Your Team Member

**Question:** "This update user, how does it work"

**Answer:**

The user update endpoint works like this:

1. **Endpoint:** `PUT /api/v1/users/{user_id}`
2. **Auth:** Requires Bearer token
3. **Permission:** Users can update their own profile, admins can update anyone
4. **Fields:** Can update email, password (full_name has a bug)
5. **Usage:** Send JSON with fields to update (all optional)

**Example:**
```bash
# Get token from login
TOKEN="your_access_token"
USER_ID="your_user_id"

# Update email
curl -X PUT "https://api-staging.youspeakhq.com/api/v1/users/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"newemail@example.com"}'
```

**Or use Swagger UI:** https://api-staging.youspeakhq.com/docs

**Note:** There's currently a bug with updating `full_name` - it doesn't work because the database uses `first_name` and `last_name` separately. Email and password updates work perfectly.

For detailed examples and testing, check the [USER_UPDATE_GUIDE.md](USER_UPDATE_GUIDE.md) file! 🚀
