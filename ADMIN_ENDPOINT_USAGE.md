# Admin Endpoint - Convert Curriculums to Library Type

**Endpoint:** `POST /curriculums/admin/migrate-to-library`
**Purpose:** Convert existing teacher_upload curriculums to library_master type for testing
**Status:** Deployed in commit `af60193`

---

## Usage

### Via cURL

```bash
# Get access token
TOKEN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.access_token')

# Get school ID
SCHOOL_ID=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.school_id')

# Convert 2 curriculums to library_master type
curl -X POST "https://api-staging.youspeakhq.com/api/v1/curriculums/admin/migrate-to-library?count=2" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-School-Id: $SCHOOL_ID" \
  | jq '.'
```

### Query Parameters

- `count` (optional, default: 2) - Number of curriculums to convert

### Example Request

```bash
POST /curriculums/admin/migrate-to-library?count=3
Authorization: Bearer <token>
X-School-Id: <school_id>
```

### Example Response

```json
{
  "success": true,
  "message": "Converted 2 curriculums to library_master",
  "converted": [
    {
      "id": "uuid-1",
      "title": "[LIBRARY] Postman Documentation",
      "source_type": "library_master",
      "status": "published"
    },
    {
      "id": "uuid-2",
      "title": "[LIBRARY] Introduction to French",
      "source_type": "library_master",
      "status": "published"
    }
  ],
  "totals": {
    "library_master": 2,
    "teacher_upload": 3
  }
}
```

---

## What It Does

1. **Selects** `count` curriculums with `source_type = 'teacher_upload'`
2. **Updates** them to:
   - `source_type = 'library_master'`
   - Prepends `[LIBRARY]` to title (if not already present)
   - Updates description to indicate it's official library content
   - Sets `status = 'published'`
3. **Returns** list of converted curriculums and updated totals

---

## SQL Executed

```sql
UPDATE curriculums
SET
  source_type = 'library_master',
  title = CASE
    WHEN title NOT LIKE '[LIBRARY]%' THEN '[LIBRARY] ' || title
    ELSE title
  END,
  description = CASE
    WHEN COALESCE(description, '') NOT LIKE 'Official YouSpeak Library%'
    THEN 'Official YouSpeak Library Content - ' || COALESCE(description, '')
    ELSE description
  END,
  status = 'published'
WHERE id IN (
  SELECT id
  FROM curriculums
  WHERE source_type = 'teacher_upload'
  LIMIT :count
)
RETURNING id, title, source_type, status;
```

---

## Verification

After running the endpoint, verify the changes:

```bash
# Check library curriculums only
curl -s "https://api-staging.youspeakhq.com/api/v1/curriculums?source_type=library_master" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data[] | {title, source_type}'

# Expected output:
[
  {
    "title": "[LIBRARY] Postman Documentation",
    "source_type": "library_master"
  },
  {
    "title": "[LIBRARY] Introduction to French",
    "source_type": "library_master"
  }
]
```

---

## Safety Notes

⚠️ **WARNING:** This endpoint modifies curriculum data permanently.

- Only use on staging/test environments
- Cannot be undone (no rollback mechanism)
- Modifies existing curriculum titles and descriptions
- Sets all converted curriculums to `published` status

---

## Production Considerations

For production, you should:

1. **Create new library curriculums** instead of converting existing ones
2. **Use a proper seeding/migration script** with version control
3. **Add authentication** to this admin endpoint (currently open)
4. **Add audit logging** to track who ran migrations and when
5. **Consider removing** this endpoint after initial data setup

---

## Alternative Approaches

### Option 1: Direct SQL (Production)
Run SQL directly in RDS Query Editor or via ECS exec:

```sql
-- Create new library curriculums (better than converting)
INSERT INTO curriculums (id, school_id, title, description, language_id, source_type, status)
VALUES
  (gen_random_uuid(), '<school_id>', 'French for Beginners', 'Official library content', 1, 'library_master', 'published'),
  (gen_random_uuid(), '<school_id>', 'Spanish Basics', 'Official library content', 2, 'library_master', 'published');
```

### Option 2: Data Seeding Script
Use the Python scripts provided:
- `generate_library_curriculums.py` - Creates 5 new library curriculums
- `create_library_curriculums.sql` - SQL insert statements

---

## Summary

**Purpose:** Quick utility to create library curriculum test data
**Method:** Converts existing teacher_upload to library_master
**Usage:** POST to `/curriculums/admin/migrate-to-library?count=N`
**Deployed:** Staging (commit `af60193`)
**Status:** Ready to use after deployment completes

Once deployed, run the endpoint to create library curriculums, then test the frontend `source_type` filter!
