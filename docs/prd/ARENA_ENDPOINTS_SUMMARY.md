# Arena Management - Endpoints Summary

**Quick Reference:** Current implementation status and gaps

---

## ✅ Implemented Endpoints

### 1. List Arenas
```
GET /api/v1/arenas
Auth: Teacher
Query: page, page_size, class_id, status
Returns: Paginated list of arenas
```
**Used By:** Dashboard stats cards, scheduled arenas list

---

### 2. Create Arena
```
POST /api/v1/arenas
Auth: Teacher
Body: class_id, title, description, criteria, rules, start_time, duration_minutes
Returns: Created arena with full details
```
**Used By:** "Create Arena Challenge" form

---

### 3. Get Arena by ID
```
GET /api/v1/arenas/{arena_id}
Auth: Teacher
Returns: Full arena details with criteria and rules
```
**Used By:** Arena preview, edit form initialization

---

### 4. Update Arena
```
PATCH /api/v1/arenas/{arena_id}
Auth: Teacher
Body: Partial update (any fields)
Returns: Updated arena with full details
```
**Used By:** Edit form, status transitions (schedule, start, end)

---

### 5. Admin Leaderboard
```
GET /api/v1/admin/leaderboard
Auth: Admin
Query: timeframe (week | month | all)
Returns: School-wide arena performance data
```
**Used By:** Admin dashboard (out of teacher console scope)

---

## ❌ Missing Endpoints (Prioritized)

### HIGH Priority

#### 1. Arena Moderation Session
```
GET /api/v1/arenas/{arena_id}/session
Auth: Teacher (moderator)
Returns: Live session data, active performers, queue
```
**Needed For:** "Moderate" button functionality

#### 2. Score Performer
```
POST /api/v1/arenas/{arena_id}/score
Auth: Teacher (moderator)
Body: performer_id, criteria_scores
Returns: Calculated total points
```
**Needed For:** Live scoring during arena session

#### 3. Delete Arena
```
DELETE /api/v1/arenas/{arena_id}
Auth: Teacher
Returns: Success confirmation
```
**Needed For:** Arena deletion from dashboard/preview

---

### MEDIUM Priority

#### 4. Arena Analytics
```
GET /api/v1/arenas/analytics
Auth: Teacher
Query: timeframe, class_id (optional)
Returns: {
  participation_rate: { percentage, present_count, absent_count },
  top_challenge_types: [ { type, percentage, count } ],
  total_arenas, total_participants
}
```
**Needed For:** Dashboard "Arena Performance Analytics" section

#### 5. Backend Criteria Weight Validation
**Not an endpoint, but schema validation enhancement**
- Add Pydantic validator to ensure criteria weights sum to 100%
- Currently only validated on frontend

---

### LOW Priority (Nice-to-Have)

#### 6. Challenge Pool - List
```
GET /api/v1/arenas/pool
Auth: Teacher
Query: page, page_size, search, challenge_type, proficiency_level
Returns: Paginated list of public challenges
```
**Needed For:** "YouSpeak Challenge Pool" browse catalog

#### 7. Challenge Pool - Get Details
```
GET /api/v1/arenas/pool/{pool_challenge_id}
Auth: Teacher
Returns: Full challenge details
```
**Needed For:** Challenge preview before cloning

#### 8. Challenge Pool - Publish
```
POST /api/v1/arenas/{arena_id}/publish-to-pool
Auth: Teacher
Body: { is_public: true }
Returns: pool_challenge_id
```
**Needed For:** "Save to YouSpeak challenge pool" option in create form

#### 9. Challenge Pool - Clone
```
POST /api/v1/arenas/from-pool
Auth: Teacher
Body: { pool_challenge_id, class_id, title (optional), description (optional) }
Returns: Newly created arena
```
**Needed For:** "Use this challenge" action in pool

---

## Database Schema Changes Required

### For Challenge Pool (LOW priority)

**Table:** `arenas`
- Add `is_public` BOOLEAN DEFAULT false (marks arena as pool challenge)
- Add `source_pool_challenge_id` UUID NULL (tracks clones)
- Add `usage_count` INTEGER DEFAULT 0 (popularity metric)
- Add index on `is_public` for pool queries

### For Soft Delete (MEDIUM priority)

**Table:** `arenas`
- Add `deleted_at` TIMESTAMP NULL
- Update queries to filter `WHERE deleted_at IS NULL`

---

## Background Jobs Required

### Automatic Status Transitions (MEDIUM priority)

**Job:** Arena Status Updater
**Frequency:** Every 1 minute
**Logic:**
1. Find arenas where `status = SCHEDULED` AND `start_time <= NOW()`
   - Update to `status = LIVE`
2. Find arenas where `status = LIVE` AND `start_time + duration_minutes <= NOW()`
   - Update to `status = COMPLETED`
3. Log all transitions

**Implementation:** Celery Beat or similar scheduler

---

## Frontend Integration Gaps

### Dashboard
- [x] Stats cards data fetching ✅
- [x] Scheduled arenas list ✅
- [ ] Analytics chart (needs analytics endpoint)
- [ ] "Moderate" button action (needs moderation endpoints)

### Create/Edit Form
- [x] Basic form fields ✅
- [x] Criteria and rules management ✅
- [x] Create/update submission ✅
- [ ] "Save to pool" option (needs pool endpoints)
- [ ] Multi-class selection (needs schema change - deferred)

### Preview
- [x] Display arena details ✅
- [x] Status-dependent actions ✅
- [ ] "Delete" action (needs delete endpoint)
- [ ] "Moderate" action (needs moderation endpoints)

### Challenge Pool
- [ ] Entire feature (needs all pool endpoints)

---

## Quick Implementation Plan

### Sprint 1: Critical Gaps
1. Implement DELETE endpoint (2 days)
2. Add backend criteria validation (1 day)
3. Set up automatic status transitions job (2 days)

### Sprint 2: Live Moderation
1. Design moderation session model (1 day)
2. Implement moderation endpoints (3 days)
3. Build frontend moderation UI (4 days)

### Sprint 3: Analytics
1. Design analytics queries (1 day)
2. Implement analytics endpoint (2 days)
3. Integrate frontend charts (2 days)

### Sprint 4 (Optional): Challenge Pool
1. Database schema updates (1 day)
2. Implement pool endpoints (3 days)
3. Build pool browsing UI (3 days)

---

## Testing Checklist

### Integration Tests
- [x] List arenas (with filters)
- [x] Create arena
- [x] Get arena by ID
- [x] Update arena
- [ ] Delete arena
- [ ] Analytics endpoint
- [ ] Moderation endpoints
- [ ] Pool endpoints

### E2E Tests
- [ ] Full arena lifecycle (create → edit → schedule → live → complete)
- [ ] Dashboard loads correctly
- [ ] Teacher authorization boundaries (403 tests)

---

## References

- **Full PRD:** `docs/prd/ARENA_MANAGEMENT_PRD.md` (1588 lines)
- **Existing Figma Docs:** `docs/ARENA_MANAGEMENT_FIGMA.md`
- **Backend Code:**
  - Models: `app/models/arena.py`
  - Endpoints: `app/api/v1/endpoints/arenas.py`
  - Service: `app/services/arena_service.py`
  - Schemas: `app/schemas/communication.py`
  - Tests: `tests/integration/test_arenas.py`
