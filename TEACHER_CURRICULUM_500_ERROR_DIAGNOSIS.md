# Teacher Curriculum 500 Error Diagnosis

**Date:** 2026-03-08
**Issue:** Teachers get HTTP 500 when accessing `/api/v1/curriculums`, but school_admins get HTTP 200

---

## Problem Confirmed

### Test Results

**School Admin (✅ Works):**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&per_page=100" \
  -H "Authorization: Bearer <admin_token>"

# Response: HTTP 200
{
  "success": true,
  "data": [],
  "meta": { "page": 1, "page_size": 10, "total": 0, "total_pages": 0 }
}
```

**Teacher (❌ Fails):**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&per_page=100" \
  -H "Authorization: Bearer <teacher_token>"

# Response: HTTP 500
{
  "success": false,
  "error": {
    "code": "UPSTREAM_ERROR",
    "message": "Internal Server Error"
  }
}
```

### Teacher Account Used for Testing
- **Email:** `teacher-1772973798@example.com`
- **Role:** `teacher`
- **School ID:** `f5750076-8653-4b96-9719-f7eb0e272d4f`
- **Token:** Valid (15-minute expiry, freshly generated)

---

## Root Cause Analysis

### 1. The Main API (Gateway) is Correct
**File:** `app/api/v1/endpoints/curriculums.py:79`
```python
@router.get("", response_model=PaginatedResponse[Any])
async def list_curriculums(
    ...
    current_user: User = Depends(deps.require_teacher_or_admin),  # ✅ Allows teachers
) -> Any:
    ...
    r = await client.get(
        "/curriculums",
        params=params,
        headers=_headers(current_user.school_id),  # ✅ Passes school_id
    )
```

**Analysis:**
- ✅ The main API correctly allows both teachers and school_admins
- ✅ The `require_teacher_or_admin` dependency is working properly
- ✅ The `school_id` is being passed in the `X-School-Id` header
- ✅ Teachers have valid school_id values

### 2. The Curriculum Microservice is Failing
**Architecture:**
```
Frontend → Main API (port 8000) → Curriculum Microservice (port 8001)
```

**What happens:**
1. Teacher makes request to main API `/api/v1/curriculums`
2. Main API validates teacher role ✅
3. Main API proxies request to curriculum microservice with `X-School-Id` header
4. **Curriculum microservice returns 500 error** ❌
5. Main API returns `UPSTREAM_ERROR` to frontend

**File:** `services/curriculum/api/routes.py:64-73`
```python
@router.get("", response_model=PaginatedResponse[CurriculumResponse])
async def list_curriculums(
    ...
    school_id: uuid.UUID = Depends(get_school_id),  # Extracts from X-School-Id
    db: AsyncSession = Depends(get_db),
) -> Any:
    ...
    curriculums, total = await CurriculumService.get_curriculums(
        db,
        school_id,
        ...
    )
```

### 3. Possible Causes of 500 Error in Curriculum Microservice

#### Theory 1: Database Connection Issue (Most Likely)
The curriculum microservice may be:
- Not connecting to the correct database
- Missing database credentials
- Using a different database than the main API
- Having permission issues with the `languages` table join

**Evidence:**
- Line 48 in `services/curriculum/services/curriculum_service.py` joins to `Language` table:
```python
.options(
    joinedload(Curriculum.classes),
    joinedload(Curriculum.language),  # ← This might fail
)
```

#### Theory 2: School ID Not Found
The teacher's school_id might not exist in the curriculum service's database.

**Evidence:**
- The query filters by `Curriculum.school_id == school_id`
- If the school doesn't exist in the curriculum DB, it should return empty results, not 500
- But if there's a foreign key constraint error, it could 500

#### Theory 3: Deployment Issue
The curriculum microservice might not be deployed with the latest fixes.

**Evidence:**
- There are commits specifically for fixing this:
  - `df24c07`: "fix(curriculum): resolve 500 error on list and allow teacher topic extraction"
  - `1029a75`: "fix(curriculum): allow teachers to access curriculum endpoints"
- These fixes might not be deployed to staging

---

## NOT a Frontend Issue

### The Frontend is Correct
**From the screenshot:**
```javascript
GET https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&per_page=100
Authorization: Bearer <valid_token>
```

**Analysis:**
- ✅ Correct endpoint
- ✅ Correct Authorization header format
- ✅ Valid token (not expired)
- ✅ Correct pagination parameters
- ✅ Teacher role is correct

### The Frontend Should NOT Change
The frontend is making a valid API call. The 500 error is a backend bug, not a frontend bug.

**What the frontend document suggested (INCORRECT):**
- "Use role-based logic" - NOT NEEDED, the backend should handle this
- "Fix TopNavbar" - UNRELATED, TopNavbar issues are separate
- "Check token expiration" - NOT THE ISSUE, token is valid

---

## Solution: Backend Fix Required

### Step 1: Check Curriculum Service Deployment
```bash
# Check if curriculum service is running on staging
curl "https://api-staging.youspeakhq.com/health" | jq '.curriculum_service_url'

# Or check environment variables
echo $CURRICULUM_SERVICE_URL
```

### Step 2: Check Curriculum Service Logs
```bash
# SSH to staging server
ssh staging

# Check curriculum service logs
docker logs -f youspeak-curriculum-service

# Look for errors when teacher makes request
```

### Step 3: Verify Database Connection
The curriculum service needs access to the same database as the main API, specifically:
- `curriculums` table
- `languages` table
- `curriculum_classes` join table
- `classes` table

**Check:**
```sql
-- As main API database user
SELECT * FROM curriculums WHERE school_id = 'f5750076-8653-4b96-9719-f7eb0e272d4f';
SELECT * FROM languages;

-- As curriculum service database user (might be different)
SELECT * FROM curriculums WHERE school_id = 'f5750076-8653-4b96-9719-f7eb0e272d4f';
SELECT * FROM languages;
```

### Step 4: Deploy Curriculum Service Fixes
If the fixes aren't deployed, deploy them:
```bash
./scripts/build-and-deploy-curriculum.sh staging
```

### Step 5: Add Better Error Logging
Update `services/curriculum/api/routes.py` to catch and log errors:
```python
@router.get("", response_model=PaginatedResponse[CurriculumResponse])
async def list_curriculums(...) -> Any:
    try:
        curriculums, total = await CurriculumService.get_curriculums(...)
        ...
    except Exception as e:
        import logging
        logging.error(f"Error listing curriculums for school {school_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
```

---

## Test Plan After Fix

```bash
# 1. Create teacher account
./create_teacher_account.sh

# 2. Test curriculum endpoint as teacher
TEACHER_TOKEN="<token_from_step_1>"
curl -i "https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&per_page=100" \
  -H "Authorization: Bearer $TEACHER_TOKEN"

# Expected: HTTP 200 (not 500)
# Expected body: {"success": true, "data": [], "meta": {...}}

# 3. Test curriculum endpoint as admin (should still work)
ADMIN_TOKEN="<admin_token>"
curl -i "https://api-staging.youspeakhq.com/api/v1/curriculums?page=1&per_page=100" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Expected: HTTP 200
# Expected body: {"success": true, "data": [], "meta": {...}}
```

---

## Summary

| Component | Status | Issue |
|-----------|--------|-------|
| Frontend | ✅ Correct | No changes needed |
| Main API (Gateway) | ✅ Correct | Properly allows teachers |
| Curriculum Microservice | ❌ Broken | Returns 500 for teachers |
| Database | ❓ Unknown | May be missing data or connections |
| Deployment | ❓ Unknown | Fixes may not be deployed |

**Next Steps:**
1. Check curriculum service logs for actual error
2. Verify curriculum service is deployed with latest fixes
3. Verify database connection and permissions
4. Add better error logging to curriculum service
5. Re-test after fixes are deployed

**Estimated Fix Time:** 1-2 hours (depending on root cause)
**Risk Level:** Medium (involves microservice deployment)
**Breaking Changes:** None (only fixes broken behavior)
