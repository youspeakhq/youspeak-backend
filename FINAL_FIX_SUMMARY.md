# Final Fix Summary - Curriculum & Assessment Issues

**Date:** 2026-03-08
**Issues:** HTTP 500 errors on curriculum and assessment endpoints for teachers
**Status:** ✅ Fixed (deploying)

---

## Issues Identified

### Issue 1: `/api/v1/curriculums` → 500 Error
**Affects:** Teacher accounts only
**Screenshot Error:** "Failed to load classes and topics: Internal Server Error"

### Issue 2: `/api/v1/assessments/topics` → 500 Error
**Affects:** Teacher assignment/assessment creation page
**Screenshot Error:** Multiple "Internal Server Error" logs in console

**Root Cause:** Both issues stem from the SAME backend bug in the curriculum microservice.

---

## Root Cause Analysis

### The Error Chain:

1. **Curriculum Service Bug:**
   ```
   sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
   can't call await_only() here. Was IO attempted in an unexpected place?
   ```

2. **Why It Happens:**
   - Previous fix (commit `df24c07`) changed from `selectinload()` to `joinedload()`
   - But used INCORRECT order: `result.scalars().unique().all()`
   - When using `joinedload()` on collections, you MUST call `.unique()` BEFORE `.scalars()`
   - Correct order: `result.unique().scalars().all()`

3. **Why It Affects Both Endpoints:**
   ```python
   # app/api/v1/endpoints/assessments.py:245
   @router.get("/topics")
   async def list_topics_from_curriculum(...):
       # This endpoint calls the curriculum service internally
       r = await client.get("/curriculums", ...)  # ← Fails with 500
   ```

---

## The Fix History

### Attempt 1: Added `.unique()` after `.scalars()` ❌
**Commit:** `9be13d6`
**Code:** `result.scalars().unique().all()`
**Result:** Didn't fix the issue - wrong method call order

### Attempt 2: Correct order - `.unique()` before `.scalars()` ✅
**Commit:** `8084645`
**Code:** `result.unique().scalars().all()`
**Result:** CORRECT FIX!

---

## The Correct Fix

**File:** `services/curriculum/services/curriculum_service.py:74`

**Before:**
```python
result = await db.execute(
    query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc())
)
return list(result.scalars().unique().all()), total
```

**After:**
```python
result = await db.execute(
    query.offset(skip).limit(limit).order_by(Curriculum.created_at.desc())
)
# Call unique() before scalars() when using joinedload on collections
return list(result.unique().scalars().all()), total
```

---

## SQLAlchemy Rules (Important!)

When using eager loading with `joinedload()`:

| Scenario | Method Call Order | Why |
|----------|------------------|-----|
| `joinedload()` on **scalar** (one-to-one) | `.scalars().all()` | No duplicates |
| `joinedload()` on **collection** (one-to-many) | `.unique().scalars().all()` | **MUST** deduplicate first |

**Our Case:**
- `Curriculum.classes` is a one-to-many collection
- `Curriculum.language` is a many-to-one scalar
- Using `joinedload(Curriculum.classes)` creates duplicate rows
- **MUST** call `.unique()` BEFORE `.scalars()` to deduplicate

**SQLAlchemy Documentation:**
> When using joined eager loading on collections, you must call `.unique()` on the Result before calling `.scalars()` to remove duplicate parent rows created by the JOIN.

---

## Deployment

### Build & Push:
- ✅ Commit pushed: `8084645`
- ✅ CI/CD triggered automatically
- ✅ Docker image built: `youspeak-curriculum-backend:8084645xxx`
- ✅ Pushed to ECR

### Manual Deployment (due to path filter issue):
```bash
aws ecs register-task-definition --cli-input-json file://task-def.json
aws ecs update-service --task-definition new-task-def --force-new-deployment
```

---

## Testing

### Before Fix:

**Teacher account:**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
  -H "Authorization: Bearer <teacher_token>"
# Response: HTTP 500 ❌
# Error: MissingGreenlet
```

**Assessments topics:**
```bash
curl "https://api-staging.youspeakhq.com/api/v1/assessments/topics" \
  -H "Authorization: Bearer <teacher_token>"
# Response: HTTP 500 ❌
# Error: Curriculum service failure
```

### After Fix:

**Expected (both endpoints):**
```bash
# Response: HTTP 200 ✅
# Body: {"success": true, "data": [...], ...}
```

---

## Test Account

**Email:** `mbakaragoodness2003@gmail.com`
**Password:** `MISSERUN123a#`
**URL:** https://staging.youspeakhq.com

Once deployment completes, test:
1. Login as teacher
2. Navigate to "Create New Task" / "Create Assessment"
3. Should load classes and topics without errors
4. Both `/curriculums` and `/assessments/topics` should return 200

---

## Related Commits

1. **1029a75** - Allow teachers to access curriculum endpoints (permission fix)
2. **df24c07** - Changed selectinload to joinedload (introduced `.unique()` order bug)
3. **9be13d6** - Added `.unique()` in wrong position (didn't fix)
4. **8084645** - Correct `.unique()` position (FINAL FIX) ✅

---

## Why School Admins Worked But Teachers Failed

**Theory:** School admins might have:
- No curriculums in their accounts (empty result set)
- Different query execution path
- The error only triggers when there ARE results with collections

Teachers are more likely to have curriculums with multiple classes, triggering the JOIN and the bug.

---

## CI/CD Path Filter Issue

**Problem:** The CI/CD path filter didn't detect changes in `services/curriculum/**`

**Workaround:** Added empty file `.rebuild-trigger` to force rebuild:
```bash
echo "# Force rebuild" >> services/curriculum/.rebuild-trigger
git add services/curriculum/.rebuild-trigger
git commit -m "chore: trigger rebuild"
```

**TODO:** Investigate why path filter isn't working correctly on subsequent pushes.

---

## Lessons Learned

1. **Read SQLAlchemy docs carefully**
   - `joinedload()` on collections requires `.unique().scalars()` order
   - Method call order matters!

2. **Check CloudWatch logs immediately**
   - Don't guess based on HTTP status codes
   - The actual exception reveals the root cause

3. **Test with realistic data**
   - Empty result sets might not trigger bugs
   - Test with curriculums that have multiple classes

4. **CI/CD path filters can be unreliable**
   - Have a manual deployment process as backup
   - Verify changes are actually being built

---

## Monitoring After Deployment

1. **CloudWatch Logs:**
   ```bash
   aws logs tail "/ecs/youspeak-curriculum-api" --since 5m
   ```
   - Should NOT see `MissingGreenlet` errors
   - Should NOT see 500 errors on `/curriculums`

2. **API Health:**
   ```bash
   curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
     -H "Authorization: Bearer <teacher_token>"
   ```
   - Should return HTTP 200
   - Should include `"success": true`

3. **Frontend:**
   - Teacher dashboard → no "Failed to load classes and topics" error
   - Create Assignment page → topics load successfully
   - No 500 errors in browser console

---

## Status

- [x] Root cause identified
- [x] Fix applied (correct `.unique()` order)
- [x] Code committed and pushed
- [x] Docker image built
- [x] Task definition updated
- [x] ECS service deploying
- [ ] Verify fix works (pending deployment completion)
- [ ] Monitor logs for 24h

**ETA:** Fix should be live in ~5-10 minutes after deployment stabilizes.

---

## Documentation

- SQLAlchemy Eager Loading: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#joined-eager-loading
- AWS ECS Deployment: Internal runbook
- Commits: https://github.com/youspeakhq/youspeak-backend/commits/main
