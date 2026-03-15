# Deploy Phase 1: Arena Session Configuration

**Quick Start Guide** - Get Phase 1 running in 5 minutes

---

## Prerequisites

- PostgreSQL database running
- `DATABASE_URL` and `SECRET_KEY` set in `.env`
- Virtual environment activated
- Dependencies installed: `pip install -r requirements.txt`

---

## Step 1: Run Migration

```bash
# Apply database schema changes (adds 6 columns to arenas table)
alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade ... -> 001_arena_session_config, Add arena session configuration fields
```

**Verify Migration:**
```bash
# Check that new columns exist
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='arenas' AND column_name IN ('arena_mode', 'judging_mode', 'ai_co_judge_enabled', 'student_selection_mode', 'session_state', 'team_size');"
```

Should return 6 rows.

---

## Step 2: Run Tests

```bash
# Run Phase 1 integration tests
pytest tests/integration/test_arenas_session_config.py -v

# Expected: 26 tests pass
```

**If tests fail:**
- Ensure DATABASE_URL points to a test database
- Ensure database has at least one semester/term created
- Check that SECRET_KEY is set in .env

---

## Step 3: Start Server

```bash
# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start on `http://localhost:8000`

---

## Step 4: Verify Endpoints

### Get API Documentation

Visit: `http://localhost:8000/docs`

You should see 4 new endpoints under "arenas":
- GET `/api/v1/arenas/students/search`
- POST `/api/v1/arenas/{arena_id}/initialize`
- POST `/api/v1/arenas/{arena_id}/students/randomize`
- POST `/api/v1/arenas/{arena_id}/students/hybrid`

---

## Step 5: Quick Smoke Test

### 1. Get Teacher JWT Token

```bash
# Login as teacher (replace with your test credentials)
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teacher@test.com",
    "password": "your_password"
  }'

# Copy the access_token from response
export TOKEN="<paste_token_here>"
```

### 2. Search Students

```bash
# Replace CLASS_ID with your test class
curl -X GET "http://localhost:8000/api/v1/arenas/students/search?class_id=<CLASS_ID>" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 200 with list of students
```

### 3. Create Arena and Initialize

```bash
# Create arena
ARENA_RESPONSE=$(curl -X POST "http://localhost:8000/api/v1/arenas" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": "<CLASS_ID>",
    "title": "Phase 1 Test Arena",
    "criteria": {"Clarity": 50, "Confidence": 50},
    "rules": ["Rule 1"]
  }')

# Extract arena_id from response
ARENA_ID=$(echo $ARENA_RESPONSE | jq -r '.data.id')

# Initialize arena
curl -X POST "http://localhost:8000/api/v1/arenas/$ARENA_ID/initialize" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arena_mode": "competitive",
    "judging_mode": "teacher_only",
    "ai_co_judge_enabled": false,
    "student_selection_mode": "manual",
    "selected_student_ids": ["<STUDENT_UUID_1>", "<STUDENT_UUID_2>"]
  }'

# Expected: 200 with session_id and status="initialized"
```

---

## Troubleshooting

### Migration fails with "column already exists"

**Solution:** Check if migration was already applied:
```bash
alembic current
```

If showing `001_arena_session_config`, migration is already applied.

---

### Tests fail with "Need at least one semester"

**Solution:** Create a semester via admin:
```bash
# Login as admin and create semester
curl -X POST "http://localhost:8000/api/v1/schools/terms" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fall 2026",
    "start_date": "2026-09-01",
    "end_date": "2026-12-31"
  }'
```

---

### Tests fail with UndefinedColumnError

**Solution:** Migration not applied. Run:
```bash
alembic upgrade head
```

---

### 403 Forbidden on student search

**Solution:** Ensure teacher teaches the class:
```bash
# Check teacher's classes
curl -X GET "http://localhost:8000/api/v1/my-classes" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Deployment to Staging/Production

### 1. Update Migration File

Edit `alembic/versions/001_add_arena_session_config_fields.py`:
- Update `down_revision` to reference your last migration ID

### 2. Run Migration in Staging

```bash
# On staging server
cd /path/to/youspeak_backend
source venv/bin/activate
alembic upgrade head
```

### 3. Restart Application

```bash
# Restart uvicorn/gunicorn processes
sudo systemctl restart youspeak-backend
```

### 4. Smoke Test in Staging

```bash
# Test student search endpoint
curl -X GET "https://staging.youspeak.com/api/v1/arenas/students/search?class_id=<CLASS_ID>" \
  -H "Authorization: Bearer <STAGING_TOKEN>"
```

### 5. Deploy to Production

Repeat steps 2-4 for production environment.

---

## Rollback (if needed)

```bash
# Rollback migration
alembic downgrade -1

# This will drop the 6 new columns
```

**Warning:** Rolling back will delete data in `arena_mode`, `judging_mode`, etc. if any arenas have been initialized.

---

## Next Steps (Phase 2)

Phase 2 will add:
- Waiting room table and endpoints
- Join code generation
- Student admission flow

**Timeline:** Ready to start Phase 2 immediately

**Estimated Time:** 1 week

See `docs/prd/ARENA_SYSTEM_COMPLETE_SPEC.md` for Phase 2 specifications.

---

## Support

- **Full specs:** `docs/prd/ARENA_SYSTEM_COMPLETE_SPEC.md`
- **Frontend guide:** `RESPONSE_TO_FRONTEND_DEV.md`
- **Test file:** `tests/integration/test_arenas_session_config.py`
- **Migration:** `alembic/versions/001_add_arena_session_config_fields.py`

---

**Phase 1 Status:** ✅ Ready for Deployment
