# School Registration Slowness - Root Cause Analysis

## 🐌 Problem
School registration endpoint (`POST /api/v1/auth/register/school`) is taking excessive time (>10 seconds, causing timeouts).

---

## 🔍 Root Causes Identified

### 1. **Bcrypt Password Hashing (PRIMARY CULPRIT)** 🔥

**Location:** `app/core/security.py:45`
```python
def get_password_hash(password: str) -> str:
    pwd_bytes = _truncate_password_for_bcrypt(password)
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())  # ⚠️ BLOCKING!
    return hashed.decode("ascii")
```

**Issue:**
- `bcrypt.hashpw()` is a **CPU-intensive blocking operation** (intentionally slow for security)
- Called inside an **async function** without proper async handling
- **Blocks the entire event loop** while hashing
- Default bcrypt work factor is typically 12 rounds = ~250-400ms on modern CPU

**Impact:**
- Blocks all other requests while password is being hashed
- In async context, this is **catastrophic** for concurrency
- Single registration can freeze the entire API for 300-500ms

**Solution:**
```python
import asyncio
from functools import partial

async def get_password_hash_async(password: str) -> str:
    """Non-blocking bcrypt password hashing."""
    pwd_bytes = _truncate_password_for_bcrypt(password)
    # Run bcrypt in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    hashed = await loop.run_in_executor(
        None,
        partial(bcrypt.hashpw, pwd_bytes, bcrypt.gensalt())
    )
    return hashed.decode("ascii")
```

---

### 2. **Multiple Database Operations**

**Location:** `app/services/school_service.py:47-130`

**Operations performed:**
1. Check if email exists (SELECT query)
2. Create school (INSERT)
3. Flush to get school.id
4. Create admin user (INSERT) + **PASSWORD HASHING** ⬅️ Major delay here
5. Create 3 default terms (3x INSERT)
6. Commit transaction
7. Update language programs (UPDATE)

**Total DB operations:** 7-8 queries + 1 bcrypt hash

**Individual timing estimates:**
- Email check: 20-50ms
- School insert: 10-20ms
- User insert: 10-20ms
- **Password hashing: 250-400ms** ⚠️
- 3x Term inserts: 30-60ms
- Program update: 20-40ms
- Commit: 10-20ms

**Total estimated time:** 350-610ms (plus network latency)

---

### 3. **Network Latency (Secondary Factor)**

**Test from local machine → Staging (eu-north-1):**
```bash
curl -w "\nTime: %{time_total}s\n" https://api-staging.youspeakhq.com/health
# Time: 0.150-0.300s  (150-300ms just for network round trip)
```

**Impact:**
- Each DB query + password hash operation includes network RTT
- If your machine is far from eu-north-1, adds 100-200ms per operation
- Multiple sequential operations = cumulative latency

---

### 4. **Lack of Database Connection Pooling Optimization**

**Current Setup:**
- Using Prisma/SQLAlchemy async connection pool
- Pool may be cold (no warm connections)
- First request to new container = connection establishment overhead

**First request penalty:**
- SSL handshake: 100-200ms
- Connection auth: 50-100ms
- Total first-request overhead: 150-300ms

---

## 📊 Total Slowness Breakdown

| Operation | Time (ms) | Blocking? |
|-----------|-----------|-----------|
| Network RTT (request) | 150-300 | No |
| Email check (DB) | 20-50 | No |
| Create school (DB) | 10-20 | No |
| **Password hashing** | **250-400** | **YES** ⚠️ |
| Create user (DB) | 10-20 | No |
| Create 3 terms (DB) | 30-60 | No |
| Update programs (DB) | 20-40 | No |
| Commit (DB) | 10-20 | No |
| Network RTT (response) | 150-300 | No |
| **TOTAL** | **650-1210ms** | - |

**Under load:** Can increase to 2-5 seconds due to event loop blocking.

---

## 🔧 RECOMMENDED FIXES

### Priority 1: Fix Blocking Bcrypt (CRITICAL)

**Update `app/core/security.py`:**
```python
import asyncio
from functools import partial

async def get_password_hash_async(password: str) -> str:
    """
    Hash password using bcrypt without blocking event loop.
    Runs bcrypt in a thread pool executor.
    """
    pwd_bytes = _truncate_password_for_bcrypt(password)
    loop = asyncio.get_event_loop()
    hashed = await loop.run_in_executor(
        None,
        partial(bcrypt.hashpw, pwd_bytes, bcrypt.gensalt())
    )
    return hashed.decode("ascii")

# Keep synchronous version for backward compatibility
def get_password_hash(password: str) -> str:
    """Synchronous bcrypt hashing (use async version when possible)."""
    pwd_bytes = _truncate_password_for_bcrypt(password)
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("ascii")
```

**Update `app/services/user_service.py:80`:**
```python
# OLD:
hashed_password = get_password_hash(password)

# NEW:
hashed_password = await get_password_hash_async(password)
```

**Expected improvement:** 250-400ms → Non-blocking (other requests continue processing)

---

### Priority 2: Optimize Database Operations

**Option A: Batch Inserts**
```python
# Create all terms in one batch
db.add_all([term1, term2, term3])
await db.flush()
```

**Option B: Defer Non-Critical Operations**
```python
# Create school + admin immediately
# Create terms in background task (Celery/RQ)
await create_terms_async.delay(school_id)
```

**Expected improvement:** 50-100ms saved

---

### Priority 3: Add Request Timeout Warnings

**Update endpoint:**
```python
@router.post("/register/school", response_model=SuccessResponse)
async def register_school(
    school_in: RegisterSchoolRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Register a new school tenant and its first admin user.
    
    ⚠️ This endpoint may take 1-2 seconds due to:
    - Password hashing (bcrypt, ~300ms)
    - Database operations (school, user, terms)
    - Network latency
    
    Expected response time: 1-2 seconds
    """
    # ... existing code
```

---

### Priority 4: Add Monitoring

**Add timing logs:**
```python
import time

start = time.time()
logger.info("Starting school registration", extra={"email": school_in.email})

# ... operations ...

elapsed = time.time() - start
logger.info("School registration complete", extra={
    "email": school_in.email,
    "elapsed_ms": int(elapsed * 1000)
})
```

---

## 🎯 Expected Results After Fixes

| Scenario | Before | After |
|----------|--------|-------|
| Single request | 650-1210ms | 400-600ms |
| Under load (10 concurrent) | 2-5 seconds | 500-800ms |
| Event loop blocking | YES ⚠️ | NO ✅ |

---

## 🚨 Critical Action Items

1. **MUST FIX:** Implement `get_password_hash_async()` to prevent event loop blocking
2. **SHOULD FIX:** Batch term inserts
3. **NICE TO HAVE:** Move non-critical operations to background tasks
4. **MONITORING:** Add timing logs to identify bottlenecks

---

## 📝 Testing After Fix

```python
# Test script to verify improvement
import time
import asyncio
import requests

async def test_registration_speed():
    start = time.time()
    
    resp = requests.post(
        "https://api-staging.youspeakhq.com/api/v1/auth/register/school",
        json={
            "school_name": f"Test {int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPass123!",
            "school_type": "secondary",
            "program_type": "partnership",
            "address_country": "US",
            "address_state": "CA",
            "address_city": "SF",
            "address_zip": "94102",
            "languages": ["spanish"]
        }
    )
    
    elapsed = time.time() - start
    print(f"Registration took {elapsed:.2f}s")
    print(f"Status: {resp.status_code}")
    
    return elapsed

# Run test
asyncio.run(test_registration_speed())
```

**Target:** < 1 second for registration

---

## 🔍 Additional Diagnostics

**Check database response time:**
```bash
# From your machine to staging DB
time psql -h <db-host> -U youspeak -c "SELECT 1"
```

**Check ECS task health:**
```bash
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-staging \
  --region eu-north-1 \
  --query 'services[0].[runningCount,pendingCount,desiredCount]'
```

**Check logs for slow queries:**
```bash
aws logs tail /ecs/youspeak-api --region us-east-1 --since 10m --filter-pattern "slow" --format short
```
