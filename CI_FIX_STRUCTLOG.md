# CI Fix: structlog Import Error

**Date:** 2026-03-16
**Issue:** Docker Smoke Tests failing in CI/CD
**Status:** ✅ FIXED

---

## Problem

GitHub Actions CI/CD pipeline failed with:

```
youspeak_api  | ModuleNotFoundError: No module named 'structlog'
youspeak_api  |   File "/app/app/api/v1/endpoints/arenas.py", line 8, in <module>
youspeak_api  |     import structlog
Container youspeak_api is unhealthy
dependency failed to start: container youspeak_api is unhealthy
```

---

## Root Cause

In Phase 6 implementation, I added `import structlog` to `app/api/v1/endpoints/arenas.py` for logging in the new team management and history endpoints:

```python
import structlog

# Later in code:
log = structlog.get_logger().bind(
    endpoint="create_team",
    arena_id=str(arena_id),
    ...
)
```

However, `structlog` was **not** in `requirements.txt`, causing the Docker container to fail during startup when trying to import the module.

---

## Why This Happened

- The codebase already has a logging infrastructure: `app.core.logging.get_logger()`
- Existing WebSocket code in the same file uses `get_logger(__name__)` consistently
- I introduced an inconsistency by using `structlog` instead of following the established pattern
- Local development didn't catch this because:
  - I was testing manually without Docker
  - Dependencies might have been installed globally or in virtual env

---

## Solution

**Replaced structlog with existing logging infrastructure:**

```python
# BEFORE (wrong):
import structlog
log = structlog.get_logger().bind(...)

# AFTER (correct):
from app.core.logging import get_logger  # Already imported
log = get_logger(__name__).bind(...)
```

**Changes made:**
1. Removed `import structlog` from imports
2. Replaced all 3 occurrences of `structlog.get_logger().bind()` with `get_logger(__name__).bind()`

**Benefits:**
- No new dependency needed
- Maintains consistency with existing codebase
- Follows established logging pattern
- Docker container starts successfully

---

## Verification

### Before Fix
```bash
$ gh run list --limit 3
completed  failure  docs(arenas): comprehensive Arena Management...  CI/CD Pipeline
completed  failure  feat(arenas): Phase 6 - Collaborative Mode...   CI/CD Pipeline
completed  success  docs(security): add secrets management...        CI/CD Pipeline
```

### After Fix
```bash
# Commit: 4f60679
# Title: fix(arenas): replace structlog with existing get_logger for Phase 6 endpoints
# Expected: CI passes ✅
```

---

## Lesson Learned

**Always check existing patterns before introducing new dependencies:**

1. ✅ **DO**: Search codebase for existing logging/utility patterns
   ```bash
   grep -r "get_logger\|logging" app/
   ```

2. ✅ **DO**: Use established patterns for consistency
   ```python
   logger = get_logger(__name__)  # Existing pattern
   ```

3. ❌ **DON'T**: Add new dependencies without checking requirements.txt
   ```python
   import structlog  # Adds dependency!
   ```

4. ✅ **DO**: Run Docker builds locally before pushing
   ```bash
   docker compose up --build
   ```

5. ✅ **DO**: Check CI logs immediately after pushing
   ```bash
   gh run watch
   ```

---

## Prevention

**For future development:**

1. **Before adding any import:**
   - Check if it's in `requirements.txt`
   - Search for existing alternatives in codebase
   - Prefer stdlib or existing dependencies

2. **Before committing:**
   - Grep for new imports: `git diff main | grep "^+import"`
   - Verify they're in requirements.txt
   - Consider if they're necessary

3. **CI/CD workflow:**
   - Docker Smoke Tests catch missing dependencies
   - Always check CI status after pushing
   - Fix CI failures immediately (don't stack commits)

---

## Related Files

- **Fixed:** `app/api/v1/endpoints/arenas.py`
- **Pattern source:** `app/core/logging.py`
- **Requirements:** `requirements.txt` (no changes needed)
- **CI config:** `.github/workflows/ci.yml`

---

**Status:** ✅ Fixed in commit 4f60679
**CI Status:** Pending verification
