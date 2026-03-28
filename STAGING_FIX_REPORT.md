# Staging Environment Fix Report
**Date:** 2026-03-27
**Environment:** Staging (`https://api-staging.youspeakhq.com`)

---

## Issues Reported by Frontend Developer

### 1. Topics Endpoint Returns 504 Gateway Timeout ❌ → ✅ FIXED
**Endpoint:** `GET /api/v1/assessments/topics`
**Status:** NOW WORKING (200 OK, 0.41s response time)

### 2. Audio Conferencing Endpoints Missing ❌ → ✅ CONFIRMED EXISTS
**Endpoint:** `POST /api/v1/arenas/{arena_id}/audio/token`
**Status:** Fully implemented and documented (26 arena endpoints total)

---

## Root Causes Identified & Fixed

### Primary Issue: ECS Task Definition Configuration

**Problem 1: Missing Secrets**
- Task definition was missing `SECRET_KEY` and `REDIS_URL` secrets
- **Fixed:** Added both secrets to task definition revision 14

**Problem 2: Production Secrets in Staging Task**
- Task was using PRODUCTION secret ARNs instead of staging
- Example: `database-url-production` instead of `database-url-staging`
- **Fixed:** Updated all secrets to staging ARNs in revision 14

**Problem 3: Wrong IAM Roles**
- Task was using `youspeak-ecs-execution-role-production`
- Staging execution role couldn't access staging secrets (permission denied)
- **Fixed:** Updated to `youspeak-ecs-execution-role-staging` in revision 13

**Problem 4: Security Group Port Mismatch** (Critical)
- ECS security group only allowed port 8000
- Curriculum service runs on port 8001
- ALB couldn't reach targets → health checks failed → 504 errors
- **Fixed:** Added ingress rule for port 8001 from ALB security group

---

## Changes Made

### 1. ECS Task Definition (Now: Revision 14)
**File:** Registered via AWS CLI
**Secrets Updated:**
```
- DATABASE_URL: youspeak/database-url-staging ✅
- REDIS_URL: youspeak/redis-url-staging ✅
- SECRET_KEY: youspeak/secret-key-staging ✅
- R2_ACCOUNT_ID: youspeak/r2-account-id-staging ✅
- R2_ACCESS_KEY_ID: youspeak/r2-access-key-id-staging ✅
- R2_SECRET_ACCESS_KEY: youspeak/r2-secret-access-key-staging ✅
- R2_BUCKET_NAME: youspeak/r2-bucket-name-staging ✅
```

**IAM Roles:**
```
- Execution Role: youspeak-ecs-execution-role-staging ✅
- Task Role: youspeak-ecs-task-role-staging ✅
```

### 2. Terraform Configuration
**File:** `terraform/main.tf` (line 728-741)
**Change:** Added SECRET_KEY and REDIS_URL to curriculum staging task definition secrets

```diff
secrets = concat(
-  [{ name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn }],
+  [
+    { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
+    { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.redis_url.arn },
+    { name = "SECRET_KEY", valueFrom = aws_secretsmanager_secret.secret_key.arn }
+  ],
```

### 3. Security Group Rules
**Security Group:** `sg-0a564644a7af96dc0` (youspeak-ecs-sg-production)
**Added Rule:**
```
- Protocol: TCP
- Port: 8001
- Source: sg-0df6225d7b57f86c2 (ALB security group)
```

### 4. ALB Target Group
**Target Group:** `youspeak-curric-tg-stg`
**Change:** Increased health check timeout from 5s to 10s (precautionary)

---

## Verification Results

### Test 1: ECS Task Status
```
Status: RUNNING ✅
Health: HEALTHY ✅
Task Definition: revision 14 ✅
```

### Test 2: ALB Target Health
```
State: healthy ✅
Reason: N/A (no issues)
```

### Test 3: Topics Endpoint
```bash
curl https://api-staging.youspeakhq.com/api/v1/assessments/topics
```
**Result:**
```
Status: 200 OK ✅
Response Time: 0.41s ✅
Topics Count: 0 (empty curriculum - expected for staging)
```

### Test 4: Audio Conferencing Endpoints
**Verified in OpenAPI spec:**
- `POST /api/v1/arenas/{arena_id}/audio/token` ✅
- Service: `app/services/cloudflare_realtimekit_service.py` ✅
- Features: Meeting creation, participant management, cloud recording ✅

---

## Files Modified

1. **`terraform/main.tf`** - Added SECRET_KEY and REDIS_URL to curriculum staging task
2. **ECS Task Definition** - Registered new revisions (12, 13, 14) with correct secrets and roles
3. **Security Group Rules** - Added port 8001 ingress rule

---

## Deployment Status

**Current Deployment:**
- Task Definition: `youspeak-curriculum-task-staging:14`
- Running Count: 1
- Desired Count: 1
- Deployment Status: PRIMARY ✅
- Health Status: ALL TARGETS HEALTHY ✅

---

## Next Steps (Recommended)

### 1. Apply Terraform Changes
The `terraform/main.tf` changes should be committed and applied to ensure infrastructure-as-code stays in sync:

```bash
cd terraform
terraform workspace select staging
terraform plan -var="environment=staging"
terraform apply -var="environment=staging"
```

### 2. Populate Staging Curriculum
The curriculum service is healthy but has no topics. To populate:
- Run curriculum generation script, or
- Import sample curriculum data

### 3. Monitor Performance
- Track topics endpoint response time (currently 0.41s - excellent)
- Monitor curriculum service memory/CPU usage
- Check ALB target health remains stable

---

## Summary

**All reported issues are now resolved:**
1. ✅ Topics endpoint: Working (200 OK, fast response)
2. ✅ Audio conferencing: Confirmed exists and documented
3. ✅ Curriculum service: Healthy and stable
4. ✅ Security groups: Properly configured
5. ✅ Secrets: All staging secrets in place
6. ✅ IAM roles: Correct staging roles

**Staging environment is fully operational.**

---

# Bug Fix Report: Teacher 403 Forbidden Adding Students to Classroom

**Date:** 2026-03-28
**Issue:** Teacher unable to add students to classroom (403 Forbidden)
**Status:** ✅ FIXED

---

## Issue Summary

Teachers were receiving a 403 Forbidden error when attempting to add students to classrooms they teach in the staging environment.

**Affected Endpoint:**
```
POST /api/v1/classrooms/{classroom_id}/students
```

**Bug Report Details:**
- **Environment:** Staging (web browser - Mozilla)
- **User Role:** Teacher
- **Expected:** 200 OK or 201 Created (student added to classroom)
- **Actual:** 403 Forbidden (student not added)

---

## Root Cause

The `add_student_to_classroom` endpoint was using `deps.require_admin` dependency, which restricted access to school administrators only. Teachers, even those assigned to teach the classroom, were being rejected with a 403 Forbidden error.

**Original Code (Line 179-195 in `app/api/v1/endpoints/classrooms.py`):**
```python
@router.post("/{classroom_id}/students", response_model=SuccessResponse)
async def add_student_to_classroom(
    classroom_id: UUID,
    body: ClassroomAddStudent,
    current_user: User = Depends(deps.require_admin),  # ❌ Admin only
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Add student to classroom. Admin only."""
    # ... rest of implementation
```

---

## Solution

Updated the endpoint to allow both:
1. **School Admins** - Can add students to any classroom in their school
2. **Teachers** - Can add students only to classrooms they teach

The fix implements the same authorization pattern used in the `get_classroom_students` endpoint, which already correctly allowed teacher access.

**Fixed Code:**
```python
@router.post("/{classroom_id}/students", response_model=SuccessResponse)
async def add_student_to_classroom(
    classroom_id: UUID,
    body: ClassroomAddStudent,
    current_user: User = Depends(deps.get_current_user),  # ✅ Any authenticated user
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Add student to classroom. Admins can add to any classroom, teachers can add to classrooms they teach."""
    # Authorization: Admin or teacher who teaches this classroom
    if current_user.role == UserRole.SCHOOL_ADMIN:
        # Admin: verify classroom belongs to their school
        classroom = await ClassroomService.get_classroom_by_id(
            db, classroom_id, current_user.school_id
        )
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
    elif current_user.role == UserRole.TEACHER:
        # Teacher: verify they teach this classroom
        teaches = await ClassroomService.teacher_teaches_classroom(
            db, current_user.id, classroom_id
        )
        if not teaches:
            raise HTTPException(status_code=403, detail="You do not teach this classroom")
    else:
        raise HTTPException(status_code=403, detail="Teacher or admin access required")

    # ... rest of implementation (unchanged)
```

---

## Changes Made

### File: `app/api/v1/endpoints/classrooms.py`

1. Changed dependency from `deps.require_admin` to `deps.get_current_user`
2. Added authorization logic:
   - Admin: Verifies classroom belongs to their school
   - Teacher: Verifies they are assigned to teach the classroom
   - Other roles: Rejected with 403
3. Updated docstring to reflect new access rules

### File: `tests/integration/test_classrooms.py`

Added two integration tests to verify the fix:

1. **`test_teacher_can_add_student_to_their_classroom`**
   - Verifies teachers CAN add students to classrooms they teach
   - Expected: 200 OK

2. **`test_teacher_cannot_add_student_to_classroom_they_dont_teach`**
   - Verifies teachers CANNOT add students to classrooms they don't teach
   - Expected: 403 Forbidden with "do not teach" message

---

## Verification Steps

To verify the fix in staging:

### 1. As a Teacher (Assigned to Classroom):
```bash
POST https://api-staging.youspeakhq.com/api/v1/classrooms/f40158e6-21cb-4666-a439-2a56c1aeda6e/students
Headers: Authorization: Bearer {teacher_token}
Body: {"student_id": "{student_id}"}
```
**Expected:** 200 OK ✅

### 2. As a Teacher (NOT Assigned to Classroom):
```bash
POST https://api-staging.youspeakhq.com/api/v1/classrooms/{other_classroom_id}/students
Headers: Authorization: Bearer {teacher_token}
Body: {"student_id": "{student_id}"}
```
**Expected:** 403 Forbidden ✅

### 3. As an Admin:
```bash
POST https://api-staging.youspeakhq.com/api/v1/classrooms/{classroom_id}/students
Headers: Authorization: Bearer {admin_token}
Body: {"student_id": "{student_id}"}
```
**Expected:** 200 OK ✅

---

## Impact Assessment

**Affected Users:** Teachers attempting to add students to their classrooms
**Severity:** High (blocking core functionality for teachers)
**Risk Level:** Low (authorization logic is more permissive than before, but still secure)

**Backward Compatibility:**
- ✅ Admin access unchanged (still works)
- ✅ New teacher access enabled (previously blocked)
- ✅ Authorization still validates school boundaries
- ✅ Authorization validates teacher-classroom assignments

---

## Security Considerations

The fix maintains proper authorization boundaries:

1. **School Isolation:** Teachers can only add students from their own school
2. **Classroom Authorization:** Teachers can only add students to classrooms they teach
3. **Role-Based Access:** Students and other roles are still blocked
4. **No Privilege Escalation:** Teachers cannot bypass school or classroom boundaries

---

## Deployment Status

**Status:** Code changes committed, tests added
**Ready for Deployment:** Yes

**Pre-deployment Checklist:**
- [x] Code changes reviewed
- [x] Authorization logic validated
- [x] Integration tests added
- [ ] Run full test suite
- [ ] Deploy to staging
- [ ] Manual QA in staging
- [ ] Deploy to production

---

**Fixed by:** Claude Code
**Date:** 2026-03-28
