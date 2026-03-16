# SQLAlchemy Async Eager Loading Research

**Date:** 2026-03-08
**Issue:** MissingGreenlet error in FastAPI + SQLAlchemy AsyncSession
**Resolution:** Use `selectinload()` not `joinedload()` for async ORM

---

## Problem Statement

FastAPI application using SQLAlchemy AsyncSession was getting:
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**When:** Accessing relationships (like `curriculum.classes` or `curriculum.language.name`) after async session closed.

---

## Root Cause (from SQLAlchemy Docs)

### What is MissingGreenlet?

From SQLAlchemy 2.1 documentation:

> "A call to the async DBAPI was initiated outside the greenlet spawn context usually setup by the SQLAlchemy AsyncIO proxy classes. Usually this error happens when an IO was attempted in an unexpected place, using a calling pattern that does not directly provide for use of the `await` keyword. **When using the ORM this is nearly always due to the use of lazy loading**, which is not directly supported under asyncio without additional steps and/or alternate loader patterns in order to use successfully."

### Why It Happens:

1. **Lazy Loading in Async Context:**
   - SQLAlchemy's default behavior is lazy loading for relationships
   - In sync ORM, relationships are loaded automatically when accessed
   - In async ORM, lazy loading requires `await` context
   - Accessing relationships outside async session → MissingGreenlet error

2. **Even "Eager Loading" Can Fail:**
   - Using `joinedload()` doesn't guarantee the relationship is fully loaded
   - Relationship access can still trigger lazy loading mechanics
   - In async context, this fails with MissingGreenlet

---

## The Official Solution (from SQLAlchemy Docs)

### Use `selectinload()` for Async Eager Loading

**All official SQLAlchemy async examples use `selectinload()`:**

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import async_sessionmaker

# Configure session with expire_on_commit=False
async_session = async_sessionmaker(engine, expire_on_commit=False)

async with async_session() as session:
    # Use selectinload for relationships
    stmt = select(Curriculum).options(
        selectinload(Curriculum.classes),
        selectinload(Curriculum.language)
    )

    result = await session.scalars(stmt)
    curriculums = result.all()

    # After session closes, relationships are accessible!
    for curr in curriculums:
        print(curr.language.name)  # ✅ Works!
        for cls in curr.classes:    # ✅ Works!
            print(cls.name)
```

### Why `selectinload()` Works:

1. **Separate SELECT Queries:**
   - Loads relationships in separate SELECT IN queries
   - Executes within the async session context
   - Fully populates relationship collections

2. **No Lazy Loading:**
   - Relationships are fully loaded during the query
   - No lazy loading triggers when accessing after session closes

3. **Async-Safe:**
   - All database IO happens within `await session.execute()`
   - No greenlet context issues

---

## Why `joinedload()` Fails in Async

### What `joinedload()` Does:

- Creates SQL JOIN to load relationships in single query
- Optimizes for fewer database round-trips
- **Designed primarily for synchronous ORM**

### Why It Fails:

From the documentation examples:

```python
# SQLAlchemy async docs DON'T show joinedload being used
# All examples use selectinload instead!

# joinedload in async → MissingGreenlet
stmt = select(A).options(joinedload(A.bs))  # ❌ Async issues
result = await session.scalars(stmt)
for a in result:
    for b in a.bs:  # May trigger lazy loading → MissingGreenlet
        print(b)

# selectinload in async → Works perfectly
stmt = select(A).options(selectinload(A.bs))  # ✅ Async-safe
result = await session.scalars(stmt)
for a in result:
    for b in a.bs:  # Fully loaded, no lazy loading
        print(b)
```

### Technical Reasons:

1. **JOIN Creates Duplicate Rows:**
   - One-to-many joins create multiple parent rows
   - Requires deduplication logic
   - Can trigger lazy loading for relationship access

2. **Greenlet Context:**
   - Even with `.unique()`, relationship access may not be in greenlet context
   - AsyncPG driver requires greenlet spawn for all IO
   - `joinedload()` doesn't guarantee all IO happens in one greenlet

3. **Not Officially Supported:**
   - SQLAlchemy async docs don't show `joinedload()` usage
   - All examples consistently use `selectinload()`
   - This is intentional - `joinedload()` isn't the async pattern

---

## Configuration Requirements

### 1. Session Configuration:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # ✅ Required!
    autocommit=False,
    autoflush=False,
)
```

**Why `expire_on_commit=False`:**
- Prevents attributes from being expired after commit
- Allows access to loaded data after session closes
- Essential for returning data from service layer

### 2. Model Configuration (Optional but Recommended):

```python
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass
```

**What `AsyncAttrs` provides:**
- Allows lazy loading with `await obj.awaitable_attrs.relationship`
- Not needed if using proper eager loading
- Useful for edge cases

---

## Comparison: selectinload vs joinedload

| Feature | selectinload() | joinedload() |
|---------|---------------|--------------|
| **SQL Queries** | Multiple SELECT IN | Single JOIN |
| **Async Safe?** | ✅ Yes | ❌ No (causes MissingGreenlet) |
| **Deduplication** | Automatic | Requires `.unique()` |
| **Official Async Docs** | ✅ All examples | ❌ Not shown |
| **Performance** | Slightly more queries | Single query (but broken in async) |
| **Use Case** | **Async ORM (recommended)** | Sync ORM only |

---

## Our Implementation

### Before (Broken - commit df24c07):
```python
# services/curriculum/services/curriculum_service.py
query = (
    select(Curriculum)
    .where(Curriculum.school_id == school_id)
    .options(
        joinedload(Curriculum.classes),  # ❌ Async issues
        joinedload(Curriculum.language),
    )
)
result = await db.execute(query)
return list(result.scalars().all()), total  # MissingGreenlet!
```

### After (Fixed - commit 457ec43):
```python
# services/curriculum/services/curriculum_service.py
query = (
    select(Curriculum)
    .where(Curriculum.school_id == school_id)
    .options(
        selectinload(Curriculum.classes),  # ✅ Async-safe
        selectinload(Curriculum.language),
    )
)
result = await db.execute(query)
return list(result.scalars().all()), total  # Works!
```

---

## Official SQLAlchemy Documentation References

### 1. Async ORM Examples:
- **Source:** https://docs.sqlalchemy.org/en/21/_modules/examples/asyncio/async_orm
- **Key Point:** All examples use `selectinload()`, never `joinedload()`

```python
# From official docs:
stmt = select(A).options(selectinload(A.bs))
result = await session.scalars(stmt)
```

### 2. MissingGreenlet Error:
- **Source:** https://docs.sqlalchemy.org/en/21/errors
- **Key Point:** "nearly always due to the use of lazy loading"

### 3. AsyncIO Patterns:
- **Source:** https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio
- **Key Point:** Use eager loading to prevent lazy load issues

---

## Performance Considerations

### selectinload() Performance:

**Queries Generated:**
```sql
-- First query: Get parent rows
SELECT * FROM curriculums WHERE school_id = ?

-- Second query: Get related classes (SELECT IN)
SELECT * FROM classes WHERE curriculum_id IN (?, ?, ?)

-- Third query: Get related languages (if many)
SELECT * FROM languages WHERE id IN (?, ?, ?)
```

**Performance:**
- Slightly more queries than joinedload
- But queries are more efficient (no cartesian product)
- PostgreSQL optimizes SELECT IN very well
- **No MissingGreenlet errors!**

### joinedload() Performance:

**Queries Generated:**
```sql
-- Single query with JOINs
SELECT * FROM curriculums
LEFT JOIN classes ON ...
LEFT JOIN languages ON ...
WHERE school_id = ?
```

**Problems:**
- Creates duplicate parent rows (one per child)
- Requires deduplication in application
- Can cause MissingGreenlet in async
- **Not worth the "optimization" if it doesn't work!**

---

## Best Practices for SQLAlchemy Async

### 1. Always Use selectinload():
```python
# ✅ Correct
stmt = select(Model).options(selectinload(Model.relationship))

# ❌ Avoid in async
stmt = select(Model).options(joinedload(Model.relationship))
```

### 2. Configure Session Properly:
```python
async_sessionmaker(engine, expire_on_commit=False)
```

### 3. Eager Load All Needed Relationships:
```python
# Load everything you'll access after session closes
stmt = select(Curriculum).options(
    selectinload(Curriculum.classes),
    selectinload(Curriculum.language),
    selectinload(Curriculum.topics),  # If needed
)
```

### 4. Don't Access Unloaded Relationships:
```python
# If you forgot to eager load:
curriculum = await session.scalars(select(Curriculum)).first()

# ❌ This will fail:
print(curriculum.classes)

# ✅ Use AsyncAttrs:
for cls in await curriculum.awaitable_attrs.classes:
    print(cls)
```

---

## Testing the Fix

### Test Script:
```bash
TOKEN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@example.com", "password": "password"}' \
  | jq -r '.data.access_token')

curl "https://api-staging.youspeakhq.com/api/v1/curriculums" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
```

### Expected Response:
```json
{
  "success": true,
  "data": [
    {
      "id": "...",
      "title": "Curriculum Title",
      "language_name": "English",  // ✅ Loaded via selectinload
      "classes": [                  // ✅ Loaded via selectinload
        {"id": "...", "name": "Class 1"},
        {"id": "...", "name": "Class 2"}
      ]
    }
  ]
}
```

---

## Lessons Learned

### 1. Read the Official Docs First
- SQLAlchemy async docs clearly show `selectinload()` usage
- If docs don't show a pattern, there's usually a reason
- Don't assume sync patterns work in async

### 2. Trust the Framework's Patterns
- If all examples use one approach, follow it
- Framework authors know the edge cases
- "Optimization" that breaks isn't an optimization

### 3. MissingGreenlet = Lazy Loading
- This error almost always means lazy loading
- Use eager loading (selectinload) to prevent it
- Set `expire_on_commit=False` to access after session

### 4. Async is Different
- Patterns from sync ORM don't always translate
- Test with realistic data (empty results might not trigger bugs)
- Check CloudWatch/logs for actual errors

---

## Summary

**Problem:** `joinedload()` causes MissingGreenlet errors in async ORM
**Solution:** Use `selectinload()` as shown in all SQLAlchemy async documentation
**Why:** selectinload loads relationships within async context, no lazy loading
**Status:** ✅ Fixed in commit `457ec43`

**Key Takeaway:** When using SQLAlchemy with AsyncSession, always use `selectinload()` for eager loading, never `joinedload()`. This is the official, documented pattern from SQLAlchemy.
