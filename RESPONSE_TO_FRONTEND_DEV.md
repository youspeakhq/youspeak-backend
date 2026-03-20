# Response to Frontend Developer Issues

## Issue 1: Create Arena 500 Error ✅ FIXED
**Status**: Fixed and deployed to staging

**Root Cause**:
- Frontend sends timezone-aware ISO 8601 datetime: `2026-03-17T10:55:01.762Z`
- Database column is `TIMESTAMP WITHOUT TIME ZONE` (timezone-naive)
- asyncpg cannot insert timezone-aware datetime into timezone-naive column
- Error: `can't subtract offset-naive and offset-aware datetimes`

**Fix Applied**:
- Added Pydantic validator to strip timezone from `start_time` in `ArenaCreate` and `ArenaUpdate`
- Deployment in progress - should be live in ~5 minutes

---

## Issue 2: Leaderboard 403 Error ❌ INCORRECT ENDPOINT

**Problem**: You're calling the wrong endpoint

**Current (WRONG)**: `/api/v1/admin/leaderboard`
- Requires: `SCHOOL_ADMIN` role
- Returns: 403 Forbidden for teachers

**Correct Endpoint**: `/api/v1/classes/leaderboard`
- Requires: `TEACHER` role ✅
- Returns: Leaderboard for teacher's classes
- Query params: `?timeframe=week|month|all`

**Action Required**: Update frontend to use `/api/v1/classes/leaderboard`

---

## Issue 3: Teachers Cannot View Students List ✅ FIXED

**Problem**: `/api/v1/classrooms/{classroom_id}/students` required admin role only

**Fix Applied**:
- Updated endpoint to allow **both admins and teachers**
- **Admins**: Can view students in any classroom in their school
- **Teachers**: Can view students ONLY in classrooms they teach
- Authorization check: Returns 403 if teacher doesn't teach that classroom

**Endpoint**: `GET /api/v1/classrooms/{classroom_id}/students`
- Deployment in progress - will be live in ~5 minutes

**Alternative for Arena Features**:
If you're building arena student selection, you can also use:
- `GET /api/v1/arenas/students/search?class_id={class_id}`
- Supports pagination and search by name

---

## Summary

| Issue | Status | Action Required |
|-------|--------|----------------|
| Arena create 500 | ✅ Fixed | Deploying now (~5min) |
| Leaderboard 403 | ❌ Wrong endpoint | Change to `/api/v1/classes/leaderboard` |
| Students list 403 | ✅ Fixed | Deploying now (~5min) |

---

## Deployment Status ✅ ALL DEPLOYED

**Deployment 1** (Arena timezone fix):
- ✅ **DEPLOYED TO STAGING** at 12:48 UTC
- ✅ Tests passed, deployed successfully
- ✅ Status: LIVE

**Deployment 2** (Students list permission):
- ✅ **DEPLOYED TO STAGING** at 12:58 UTC
- ✅ Tests passed, deployed successfully
- ✅ Status: LIVE

**Staging Service**:
- ECS deployment updated at: 13:58 UTC
- Status: Healthy and running
- Environment confirmed: staging

---

## Testing Instructions

A test script has been created: `/test-arena-staging.sh`

**To test the arena creation fix:**

```bash
# Get your JWT token from the frontend app (DevTools → Local Storage)
./test-arena-staging.sh YOUR_JWT_TOKEN [CLASS_ID]
```

**Or test manually with curl:**

```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/arenas" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "class_id": "YOUR_CLASS_ID",
    "title": "Test Arena",
    "description": "Testing timezone fix",
    "rules": [],
    "criteria": {"pronunciation": 50, "fluency": 50},
    "start_time": "2026-03-17T15:00:00.000Z",
    "duration_minutes": 30
  }'
```

**Expected result**: `200 OK` with arena created successfully

---

The leaderboard issue requires a **frontend change** - update your endpoint from `/api/v1/admin/leaderboard` to `/api/v1/classes/leaderboard`.

---

## Issue 4: Challenge Pool Empty (Not a Bug) ℹ️

**Status**: Working as designed - clarification needed

**Frontend Developer's Comment**:
> "It's bringing an empty string. I think all arena Challenges that are drafts are supposed to be in the challenge pool pending Scheduling"

### ❌ This is a Misunderstanding

The **Challenge Pool** (`/api/v1/arenas/pool`) is **NOT** for draft arenas or scheduling.

### What is the Challenge Pool?

The Challenge Pool is a **public library of reusable arena templates** that teachers can:
- Browse and search
- Preview and clone
- Reuse in their own classes

### What Shows in the Challenge Pool?

**Only arenas that meet BOTH criteria:**
1. ✅ `is_public = true` (explicitly published to the pool)
2. ✅ `status = "published"` (marked as published)

**NOT included:**
- ❌ Draft arenas
- ❌ Scheduled arenas
- ❌ Live arenas
- ❌ Completed arenas
- ❌ Any arena that hasn't been explicitly published to the pool

### Why is the Pool Empty?

The pool is empty because **no teacher has published any arenas to the pool yet**.

This is expected behavior. Teachers must:
1. Create an arena (status: draft)
2. Complete and test it
3. Explicitly publish it to the challenge pool using: `POST /api/v1/arenas/{arena_id}/publish-to-pool`
4. Only then will it appear in the pool

### ✅ Correct Endpoints for Different Use Cases

| Use Case | Endpoint | What It Shows |
|----------|----------|---------------|
| **Teacher's own arenas** | `GET /api/v1/arenas` | All arenas created by the teacher (draft, scheduled, live, completed) |
| **Create new arena** | `POST /api/v1/arenas` | Creates a new draft arena |
| **Schedule an arena** | `PATCH /api/v1/arenas/{id}` | Set `start_time` to schedule |
| **Browse public challenges** | `GET /api/v1/arenas/pool` | Public library of published challenges |
| **Clone a challenge** | `POST /api/v1/arenas/pool/{id}/clone` | Clone a published challenge to your own class |

### 📋 Action Required

**If you want to show a teacher's OWN arenas (drafts, scheduled, etc.):**
- Use: `GET /api/v1/arenas?class_id={class_id}`
- This returns all arenas for classes the teacher teaches
- Supports filtering by status: `?status=draft` or `?status=scheduled`

**If you want to browse the public challenge pool:**
- Use: `GET /api/v1/arenas/pool`
- This is currently empty (expected)
- Will populate when teachers publish challenges

### Example: Publishing to the Pool

```bash
# Step 1: Create and complete an arena
POST /api/v1/arenas
{ "title": "Debate Challenge", "class_id": "...", ... }

# Step 2: Publish it to the challenge pool
POST /api/v1/arenas/{arena_id}/publish-to-pool

# Now it appears in GET /api/v1/arenas/pool
```

---
