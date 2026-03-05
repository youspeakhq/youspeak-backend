# Assessment vs Assignment - Figma vs Backend Clarification

## Critical Finding: Terminology Mismatch

### Figma Design Expectation
According to [docs/ASSESSMENT_MANAGEMENT_FIGMA.md](docs/ASSESSMENT_MANAGEMENT_FIGMA.md), line 33:

**Task Management table shows:**
- **Type column**: `"Assessment | Assignment"` (two distinct categories)
- **Assessment type field**: `"oral | written"` (applies to assessments)

This suggests Figma treats "Assessment" and "Assignment" as **two different entity types**.

### Backend Implementation Reality

**Database Model:** `Assignment` (in `app/models/assessment.py`)
- Single entity type called "Assignment"
- No separate "Assessment" model exists

**API Endpoint:** `/api/v1/assessments`
- Creates an `Assignment` record
- "Assessment" (API) = "Assignment" (Database) — **same thing**

**Differentiation:** `type` field with `AssignmentType` enum
- `"oral"` → Oral assessments
- `"written"` → Written assessments

---

## The Discrepancy

| Aspect | Figma Expectation | Backend Reality |
|--------|-------------------|-----------------|
| **Entity Types** | Assessment AND Assignment (separate) | Only Assignment (single entity) |
| **Type Field in Table** | "Assessment" or "Assignment" | Not implemented |
| **Assessment Type Field** | "oral" or "written" | ✅ Implemented as `type` field |
| **Terminology** | Assessment ≠ Assignment | Assessment = Assignment |

---

## Two Possible Interpretations

### Interpretation 1: Figma Design Intent (NOT Current Backend)
Figma might intend **two separate entity types:**

1. **Assessment** (formal evaluations)
   - Type: oral or written
   - Has questions, grading, submissions
   - Shows up as "Assessment" in Type column

2. **Assignment** (homework/tasks)
   - Type: general task
   - May not have structured questions
   - Shows up as "Assignment" in Type column

### Interpretation 2: Figma Labeling Issue (Matches Current Backend)
Figma's "Type (Assessment | Assignment)" might be a **labeling error** and should be:
- "Type (Oral | Written)"

This would match the current backend where:
- Everything is an `Assignment` entity
- Differentiation is by `type: "oral" | "written"`

---

## Current Backend Behavior ✅

**What works NOW:**

1. **Create Assessment/Assignment** (same thing)
   ```bash
   POST /api/v1/assessments
   {
     "title": "French Quiz",
     "type": "written",  # or "oral"
     "class_ids": ["..."],
     ...
   }
   ```

2. **List Assessments/Assignments** (returns all assignments)
   ```bash
   GET /api/v1/assessments?type=written  # Filter by oral/written
   ```

3. **Response includes:**
   - `type`: "oral" or "written"
   - NO separate field for "Assessment" vs "Assignment" distinction

---

## Frontend Impact

### If Figma is Correct (Two Entity Types)

The frontend would need:
- Backend to add a new enum field (e.g., `entity_category: "assessment" | "assignment"`)
- Update `Assignment` model with new field
- Migration to add column
- Update API schemas

### If Backend is Correct (Single Entity)

The frontend should:
- Use `type` field with values "oral" or "written"
- Display as:
  - "Oral Assessment" (when type = "oral")
  - "Written Assessment" (when type = "written")
- OR simplify to just show "oral" or "written"

---

## Recommended Clarification

**Questions for Product/Design Team:**

1. **Are "Assessment" and "Assignment" meant to be:**
   - ✅ **The same thing** with oral/written variants? (matches current backend)
   - ❌ **Two separate entity types**? (would require backend changes)

2. **In the Task Management table "Type" column, should it show:**
   - Option A: "Oral" or "Written" (matches current backend)
   - Option B: "Assessment" or "Assignment" (requires new field)
   - Option C: Both? e.g., "Written Assessment" / "Oral Assignment"

3. **Is there a semantic difference between:**
   - **Assessment**: Formal evaluation with grading?
   - **Assignment**: General homework/task?

---

## What the Backend Supports RIGHT NOW

### ✅ Fully Implemented

- Single unified entity (`Assignment` model)
- Differentiation by `type: "oral" | "written"`
- All CRUD operations
- Question bank
- AI generation
- Submissions and grading
- Analytics

### ❌ NOT Implemented (if Figma needs it)

- Separate "Assessment" vs "Assignment" entity categories
- A field to distinguish between formal assessments vs general assignments

---

## API Response Example (Current Backend)

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "French Vocabulary Quiz",
    "type": "written",  // ← This is what exists
    // NO "category" or "entity_type" field exists
    "status": "draft",
    "instructions": "...",
    "due_date": "2026-03-20T23:59:59Z",
    "enable_ai_marking": true
  }
}
```

### What Figma Might Expect (if two entity types)

```json
{
  "data": {
    "id": "uuid",
    "title": "French Vocabulary Quiz",
    "entity_type": "assessment",  // ← Doesn't exist in backend
    "assessment_type": "written", // ← Currently just called "type"
    ...
  }
}
```

---

## Migration Path (if Figma needs two entity types)

### Option 1: Add Entity Category Field

1. Add enum:
   ```python
   class EntityCategory(str, enum.Enum):
       ASSESSMENT = "assessment"
       ASSIGNMENT = "assignment"
   ```

2. Add field to `Assignment` model:
   ```python
   category = Column(
       ENUM(EntityCategory),
       default=EntityCategory.ASSESSMENT,
       nullable=False
   )
   ```

3. Update schemas and API

4. Run migration

### Option 2: Keep Current Design (Simpler)

- Frontend uses `type` field ("oral" | "written")
- Display logic in frontend:
  - "Oral Assessment" when `type === "oral"`
  - "Written Assessment" when `type === "written"`
- Update Figma documentation to match backend

---

## Recommendation

**BEFORE making backend changes:**

1. ✅ **Confirm with Product/Design:** What does "Type (Assessment | Assignment)" mean in Figma?
2. ✅ **Check Frontend Code:** What is the frontend actually sending/expecting?
3. ✅ **Test Current API:** Verify if current implementation meets frontend needs

**Most likely scenario:**
- Figma labeling is unclear/ambiguous
- Current backend (single entity with oral/written types) is sufficient
- Frontend can display as "Written Assessment", "Oral Assessment" using the `type` field

---

## Testing the Current Implementation

Run the test script to verify current behavior:
```bash
./test_assessment_endpoint.sh
```

Check what the API currently returns and confirm with frontend expectations.

---

## Summary

| Item | Status |
|------|--------|
| **Backend Model** | Single `Assignment` entity ✅ |
| **API Endpoint** | `/api/v1/assessments` ✅ |
| **Type Field** | `"oral"` or `"written"` ✅ |
| **Separate Assessment/Assignment Entities** | ❌ Not implemented |
| **Figma Alignment** | ⚠️ Needs clarification |

**Bottom Line:** The backend treats "Assessment" and "Assignment" as the **same thing**, differentiated only by `type: "oral" | "written"`. If Figma expects them to be separate entity types, backend changes are needed.
