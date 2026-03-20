# Active Students & Task Topic Calculation Explanation

Based on the screenshot showing the assessment/task API response with `"active_students": 0` and `"task_topic": "string"`.

---

## Current Implementation Status

### 📊 Field: `active_students`

**Location**: `app/schemas/content.py:241` - `AssessmentListRow` schema

**Current Value**: `None` (defaults to null/0 in response)

**What it SHOULD represent**:
- Number of students actively working on or assigned to this task/assessment
- Students who have started but not yet completed the assignment

**Current Implementation**:
```python
# File: app/api/v1/endpoints/assessments.py:313

def _assignment_to_list_row(a, class_name=None, active_students=None, average_score=None):
    return {
        ...
        "active_students": active_students,  # Passed as parameter
        ...
    }

# Called at line 313:
items = [_assignment_to_list_row(a) for a in assignments]  # ❌ No active_students passed!
```

**Result**: Always returns `None` → Frontend shows `0`

---

### 📝 Field: `task_topic`

**Location**: `app/schemas/content.py:242` - `AssessmentListRow` schema

**Current Value**: `None` (hardcoded)

**What it SHOULD represent**:
- The topic/subject matter of the task (e.g., "Present Tense Verbs", "Business Vocabulary")
- Could be a free-text field or linked to a curriculum taxonomy

**Current Implementation**:
```python
# File: app/api/v1/endpoints/assessments.py:58

def _assignment_to_list_row(...):
    return {
        ...
        "task_topic": None,  # ❌ Hardcoded to None!
        ...
    }
```

**Result**: Always returns `None`

---

## How to Fix This

### Option 1: Calculate `active_students` from Submissions

Count students who have submissions in progress (started but not completed):

```python
# In AssessmentService.list_assignments():

from sqlalchemy import select, func, and_
from app.models.assessment import Assignment, Submission

# For each assignment, count active students
active_students_subquery = (
    select(
        Submission.assignment_id,
        func.count(func.distinct(Submission.student_id)).label('active_count')
    )
    .where(
        and_(
            Submission.assignment_id == Assignment.id,
            Submission.submitted_at.is_(None),  # Not yet submitted
            Submission.started_at.isnot(None)    # But has started
        )
    )
    .group_by(Submission.assignment_id)
    .subquery()
)

# Join to main query
query = (
    select(
        Assignment,
        Class.name.label('class_name'),
        func.coalesce(active_students_subquery.c.active_count, 0).label('active_students')
    )
    .outerjoin(active_students_subquery, Assignment.id == active_students_subquery.c.assignment_id)
    .join(Class, Assignment.class_id == Class.id)
    # ... rest of query
)
```

Then update the endpoint:

```python
# app/api/v1/endpoints/assessments.py:313

items = [
    _assignment_to_list_row(
        a,
        class_name=class_name,
        active_students=active_students,  # ✅ Pass calculated value
        average_score=avg_score
    )
    for a, class_name, active_students in assignments  # Unpack tuple
]
```

---

### Option 2: Add `task_topic` to Assignment Model

**Step 1**: Add field to database model

```python
# app/models/assessment.py

class Assignment(BaseModel):
    __tablename__ = "assignments"

    # ... existing fields ...
    task_topic = Column(String(255), nullable=True)  # ✅ Add this field
```

**Step 2**: Create migration

```bash
alembic revision -m "add_task_topic_to_assignments"
```

```python
# In migration file:
def upgrade():
    op.add_column('assignments', sa.Column('task_topic', sa.String(255), nullable=True))

def downgrade():
    op.drop_column('assignments', 'task_topic')
```

**Step 3**: Update schema to accept task_topic

```python
# app/schemas/content.py

class AssessmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    task_topic: Optional[str] = None  # ✅ Add this
    # ... rest of fields
```

**Step 4**: Update the response builder

```python
# app/api/v1/endpoints/assessments.py:58

def _assignment_to_list_row(...):
    return {
        ...
        "task_topic": a.task_topic,  # ✅ Get from model instead of hardcoding None
        ...
    }
```

---

## Quick Fix (If These Fields Are Not Needed)

If the frontend doesn't actually use these fields, you can:

**Option A**: Remove from schema (breaking change)

```python
# app/schemas/content.py - Remove these lines:
# active_students: Optional[int] = None
# task_topic: Optional[str] = None
```

**Option B**: Document as "Not Implemented"

Add comments to clarify:

```python
class AssessmentListRow(BaseModel):
    # ... fields ...
    active_students: Optional[int] = None  # TODO: Implement - count in-progress submissions
    task_topic: Optional[str] = None       # TODO: Implement - add to Assignment model
```

---

## Summary

| Field | Current Status | Why It's 0/null | How to Fix |
|-------|---------------|-----------------|------------|
| `active_students` | ❌ Not calculated | Function called without parameter | Add subquery to count in-progress submissions |
| `task_topic` | ❌ Hardcoded `None` | Line 58 returns `None` | Add field to Assignment model + migration |

---

## Recommendation

1. **Decide if these fields are needed** - Check with frontend/product team
2. **If needed**: Implement active_students calculation (Option 1)
3. **If needed**: Add task_topic to database (Option 2)
4. **If not needed**: Remove from schema or mark as deprecated

---

## Files to Modify

- `app/schemas/content.py` - Schema definition
- `app/api/v1/endpoints/assessments.py` - Response builder
- `app/services/assessment_service.py` - Data fetching logic
- `app/models/assessment.py` - Database model (if adding task_topic)
- `alembic/versions/` - Migration file (if adding task_topic)

---

**Questions?** Let me know which approach you'd like to take and I can implement it!
