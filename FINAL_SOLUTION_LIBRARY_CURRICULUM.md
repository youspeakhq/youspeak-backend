# Final Solution: Library Curriculum Filter + Data Creation

**Date:** 2026-03-09
**Status:** ✅ Backend filter deployed | ⏳ Awaiting data creation deployment
**Commits:** `d4fde5c` (filter), `af60193` (admin endpoint), `da6f3d8` (update schema)

---

## Complete Solution Overview

### Problem
- Frontend "Library Curriculum" page couldn't filter library content from teacher uploads
- Backend had no `source_type` filter parameter
- No library curriculum test data existed

### Solution Delivered (3 Parts)

####1. ✅ Backend Filter (Deployed - Commit `d4fde5c`)
- Added `source_type` query parameter to `GET /curriculums`
- Filters: `library_master`, `teacher_upload`, `merged`
- Usage: `GET /curriculums?source_type=library_master`

#### 2. ✅ Data Conversion via API (Deploying - Commit `da6f3d8`)
- Added `source_type` to `CurriculumUpdate` schema
- Enables updating curriculums via `PATCH /curriculums/:id`
- Can convert existing curriculums to library type

#### 3. ⏳ Admin Endpoint (For Future Use - Commit `af60193`)
- Created `/curriculums/admin/migrate-to-library` endpoint
- Not currently routed through main API (requires ALB/routing config)
- Alternative: Use PATCH endpoint instead

---

## How to Create Library Curriculum Data (Option 1 - API Method)

Once the latest deployment completes (commit `da6f3d8`), run this script:

```bash
#!/bin/bash
# Convert 2 curriculums to library_master type via API

TOKEN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.access_token')

SCHOOL_ID=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.school_id')

# IDs of curriculums to convert (from earlier query)
CURRICULUM_IDS=(
  "92eec828-37eb-4bfd-8c0c-17df63c4ea56"  # Non Disclosure
  "629e9acc-1afe-415b-bbd2-a9113d1e5965"  # Postman Documentation
)

echo "Converting curriculums to library_master type..."

for ID in "${CURRICULUM_IDS[@]}"; do
  echo "Converting curriculum $ID..."
  curl -s -X PATCH "https://api-staging.youspeakhq.com/api/v1/curriculums/$ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-School-Id: $SCHOOL_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"source_type\": \"library_master\",
      \"title\": \"[LIBRARY] Postman Documentation\",
      \"description\": \"Official YouSpeak Library Content\"
    }" | jq '{success, data: {id: .data.id, title: .data.title, source_type: .data.source_type}}'
done

echo "✅ Done! Verifying..."

# Verify library curriculums exist
curl -s "https://api-staging.youspeakhq.com/api/v1/curriculums?source_type=library_master" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '{total: .meta.total, curriculums: .data | map({title, source_type})}'
```

---

## Current Deployment Status

### ✅ Deployed (Working)
1. **`source_type` filter** (commit `d4fde5c`) - ✅ Deployed, tested, working

### ⏳ Deploying Now
2. **`source_type` in update schema** (commit `da6f3d8`) - Building in CI/CD

### Pipeline Status
```bash
# Check build status
gh run list --limit 1
```

---

## Verification After Deployment

### Step 1: Wait for CI/CD
```bash
# Monitor deployment
gh run list --limit 1 --json status,conclusion,updatedAt
```

### Step 2: Update Task Definition (When CI/CD Completes)
```bash
# Get new commit hash
COMMIT_HASH=$(git log -1 --format="%H")

# Check image exists in ECR
aws ecr describe-images --repository-name youspeak-curriculum-backend \
  --image-ids imageTag=$COMMIT_HASH --query 'imageDetails[0].imagePushedAt'

# Deploy to ECS (update task def JSON and register/update service)
```

### Step 3: Convert Curriculums
```bash
# Use the API script above to convert 2 curriculums
./convert_via_api.sh
```

### Step 4: Test Filter
```bash
TOKEN=$(curl -s -X POST "https://api-staging.youspeakhq.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "mbakaragoodness2003@gmail.com", "password": "MISSERUN123a#"}' \
  | jq -r '.data.access_token')

# Should return 2 library curriculums
curl -s "https://api-staging.youspeakhq.com/api/v1/curriculums?source_type=library_master" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '{total: .meta.total, types: [.data[].source_type] | unique}'
```

**Expected Output:**
```json
{
  "total": 2,
  "types": ["library_master"]
}
```

---

## Frontend Integration (Ready to Use)

Once library data exists, the frontend can filter library curriculums:

```typescript
// In MergeCurriculumPageNew.tsx or similar
const fetchLibraryCurriculums = async () => {
  const response = await curriculumService.listCurriculums(1, 50, {
    source_type: 'library_master',  // ← Filters library only
    search: searchQuery || undefined,
  });

  setLibraryCurriculums(response.data);
  setTotal(response.meta.total);
};
```

**Benefits:**
- Fast loading (only fetches library content)
- Clean separation between library and teacher content
- Works with all other filters (search, language, status)

---

## Summary

### What Was Done
1. ✅ Added `source_type` filter to curriculum API
2. ✅ Deployed filter to staging and tested (working)
3. ✅ Added `source_type` to update schema (enables API-based conversion)
4. ⏳ Awaiting deployment of update schema change
5. ⏳ Will convert 2 curriculums to library type once deployed

### What's Next
1. Wait for CI/CD to complete (commit `da6f3d8`)
2. Deploy new image to ECS staging
3. Run API script to convert 2 curriculums to library type
4. Verify library filter returns data
5. Update frontend to use `source_type` parameter
6. Test end-to-end

### Timeline
- Backend filter: ✅ Complete
- Data conversion capability: ⏳ ~10 minutes (building now)
- Create library data: ⏳ ~2 minutes (after deployment)
- Frontend update: ⏳ Depends on frontend team

---

**Status: 90% Complete - Just waiting for final deployment and data conversion!**
