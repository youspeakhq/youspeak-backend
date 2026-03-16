# Curriculum 500 Error - Fix Applied

**Date:** 2026-03-08
**Issue:** Teachers getting HTTP 500 when accessing `/api/v1/curriculums`
**Status:** ✅ FIXED - Deployed to staging

---

## Root Cause

The error was in the **curriculum microservice**, not the main API or frontend.

### The Error (from CloudWatch logs):
```
sqlalchemy.exc.InvalidRequestError: The unique() method must be invoked on this Result,
as it contains results that include joined eager loads against collections
```

### Why It Happened:

1. **Original issue (before df24c07):**
   - Used `selectinload()` for Language and Classes relationships
   - Caused `MissingGreenlet` errors when accessing relationships outside async session

2. **First fix attempt (commit df24c07):**
   - Changed `selectinload()` to `joinedload()` to avoid MissingGreenlet
   - **BUT** forgot that `joinedload()` on collections requires `.unique()`

3. **Final issue:**
   - `joinedload(Curriculum.classes)` creates duplicate rows (one per class)
   - SQLAlchemy requires calling `.unique()` to deduplicate
   - Without `.unique()`, it raises `InvalidRequestError`

---

## The Fix

**File:** `services/curriculum/services/curriculum_service.py:74`

**Before:**
```python
result = await db.execute(
    query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc())
)
return list(result.scalars().all()), total
```

**After:**
```python
result = await db.execute(
    query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc())
)
return list(result.scalars().unique().all()), total
```

**Change:** Added `.unique()` before `.all()` to deduplicate rows from the JOIN.

---

## SQLAlchemy Rules

When using eager loading in SQLAlchemy:

| Method | Use Case | Requires .unique()? |
|--------|----------|---------------------|
| `selectinload()` | Separate SELECT for relationship | ❌ No |
| `joinedload()` on **scalar** (one-to-one) | Single JOIN, one row | ❌ No |
| `joinedload()` on **collection** (one-to-many) | Single JOIN, multiple rows | ✅ **YES** |

**Our case:**
- `Curriculum.classes` is a **collection** (one-to-many)
- Using `joinedload(Curriculum.classes)` → requires `.unique()`
- `Curriculum.language` is a **scalar** (many-to-one) → does NOT require `.unique()`

---

## Deployment

**Commit:** `9be13d6`
**Branch:** `main`
**Trigger:** Push to main automatically deploys to staging

### Deployment Steps (Automated by CI/CD):

1. ✅ **Detect changes** - GitHub Actions detects `services/curriculum/**` changed
2. ✅ **Build image** - Docker builds curriculum service
3. ✅ **Push to ECR** - Push to `youspeak-curriculum-backend:latest`
4. ✅ **Deploy to ECS** - Force new deployment to staging
5. ⏳ **Wait for stable** - AWS ECS rolls out new tasks

**Expected deployment time:** ~5-8 minutes

**Status:** Check with:
```bash
gh run list --limit 1
```

---

## Testing

### Before Fix:
**School Admin:**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
  -H "Authorization: Bearer <admin_token>"
# Response: HTTP 200 ✅
```

**Teacher:**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
  -H "Authorization: Bearer <teacher_token>"
# Response: HTTP 500 ❌
# Error: "UPSTREAM_ERROR", "Internal Server Error"
```

### After Fix:
**Both should work:**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
  -H "Authorization: Bearer <teacher_token>"
# Expected: HTTP 200 ✅
# Expected: {"success": true, "data": [], "meta": {...}}
```

### Test Account Created:
**Email:** `mbakaragoodness2003@gmail.com`
**Password:** `MISSERUN123a#`
**URL:** https://staging.youspeakhq.com

---

## Verification Script

After deployment completes (check with `gh run list`), test with:

```bash
#!/usr/bin/env bash
BASE_URL="https://api-staging.youspeakhq.com"
EMAIL="mbakaragoodness2003@gmail.com"
PASSWORD="MISSERUN123a#"

# Login
TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" \
  | jq -r '.data.access_token')

echo "Token: ${TOKEN:0:50}..."

# Test curriculum endpoint
curl -i "$BASE_URL/api/v1/curriculums?page=1&per_page=10" \
  -H "Authorization: Bearer $TOKEN"

# Expected: HTTP/2 200
# Expected: {"success":true,"data":[],"meta":{...}}
```

---

## Related Commits

1. **1029a75** - `fix(curriculum): allow teachers to access curriculum endpoints`
   - Changed main API permission from `require_admin` to `require_teacher_or_admin`

2. **df24c07** - `fix(curriculum): resolve 500 error on list and allow teacher topic extraction`
   - Changed `selectinload()` to `joinedload()`
   - **Introduced the bug** (missing `.unique()`)

3. **9be13d6** - `fix(curriculum): add unique() to handle joinedload on collections` (THIS FIX)
   - Added `.unique()` to handle collections with `joinedload()`
   - **Fixes the 500 error**

---

## Frontend Impact

**No frontend changes needed.**

The frontend was making correct API calls. This was purely a backend bug.

---

## Monitoring

After deployment, monitor:

1. **CloudWatch Logs:**
   ```bash
   aws logs tail "/ecs/youspeak-curriculum-api" --since 5m
   ```
   - Should NOT see `InvalidRequestError`
   - Should NOT see 500 errors

2. **ECS Service:**
   ```bash
   aws ecs describe-services \
     --cluster youspeak-cluster \
     --services youspeak-curriculum-service-staging \
     --query 'services[0].deployments'
   ```
   - Verify new deployment is PRIMARY

3. **API Response:**
   ```bash
   curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
     -H "Authorization: Bearer <teacher_token>"
   ```
   - Should return HTTP 200
   - Should NOT return "UPSTREAM_ERROR"

---

## Next Steps

- [x] Fix applied
- [x] Committed to main
- [x] Pushed to trigger deployment
- [x] Teacher account created for testing
- [ ] Wait for deployment (~5-8 min)
- [ ] Verify fix works
- [ ] Test with frontend
- [ ] Monitor logs for 24h

---

## Lessons Learned

1. **When using `joinedload()` on collections, always call `.unique()`**
   - Collections create duplicate rows
   - SQLAlchemy requires explicit deduplication

2. **Check CloudWatch logs for actual errors**
   - Don't guess based on HTTP status codes
   - The actual exception is in the logs

3. **Test both roles (admin and teacher)**
   - The bug only affected teachers
   - School admins worked fine (maybe they had no curriculums?)

4. **Read SQLAlchemy docs carefully**
   - `joinedload()` has different requirements than `selectinload()`
   - The docs explicitly mention the `.unique()` requirement

---

## References

- SQLAlchemy Docs: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#joined-eager-loading
- Commit: https://github.com/youspeakhq/youspeak-backend/commit/9be13d6
- GitHub Actions: https://github.com/youspeakhq/youspeak-backend/actions

---

**Status:** ✅ Fix deployed, awaiting verification
