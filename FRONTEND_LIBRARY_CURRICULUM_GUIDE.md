# Frontend: How to Fix Library Curriculum Loading

**Issue:** Library Curriculum page takes too long / shows all curriculums instead of just library ones
**Root Cause:** Backend API had no filter for `source_type`
**Status:** ✅ Backend fixed (commit `d4fde5c`), awaiting deployment
**Your Action Required:** Update frontend to use new `source_type` parameter

---

## 1. Update Your API Service

Add `source_type` to your curriculum list parameters:

```typescript
// services/curriculumService.ts (or similar)

export interface ListCurriculumsParams {
  page?: number;
  page_size?: number;
  status?: 'draft' | 'published' | 'archived';
  language_id?: number;
  search?: string;
  source_type?: 'library_master' | 'teacher_upload' | 'merged';  // ← ADD THIS
}

export class CurriculumService {
  async listCurriculums(
    page: number = 1,
    pageSize: number = 10,
    params?: ListCurriculumsParams
  ): Promise<PaginatedResponse<Curriculum>> {
    const queryParams = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    // Add optional parameters
    if (params?.status) queryParams.append('status', params.status);
    if (params?.language_id) queryParams.append('language_id', params.language_id.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.source_type) queryParams.append('source_type', params.source_type);  // ← ADD THIS

    const response = await fetch(`/api/v1/curriculums?${queryParams}`, {
      headers: {
        'Authorization': `Bearer ${this.getToken()}`,
        'X-School-Id': this.getSchoolId(),
      },
    });

    return response.json();
  }
}
```

---

## 2. Update Library Curriculum Page

In your `MergeCurriculumPageNew.tsx` (or wherever you fetch library curriculums):

```typescript
// BEFORE (fetching ALL curriculums - SLOW):
const fetchCurriculums = async () => {
  setLoading(true);
  try {
    const response = await curriculumService.listCurriculums(1, 50, {
      search: searchQuery || undefined,
    });
    setCurriculums(response.data);
    setTotal(response.meta.total);
  } catch (error) {
    console.error('Failed to fetch curriculums:', error);
  } finally {
    setLoading(false);
  }
};

// AFTER (fetching ONLY library curriculums - FAST):
const fetchLibraryCurriculums = async () => {
  setLoading(true);
  try {
    const response = await curriculumService.listCurriculums(1, 50, {
      source_type: 'library_master',  // ← ADD THIS LINE (filters for library only)
      search: searchQuery || undefined,
    });
    setCurriculums(response.data);
    setTotal(response.meta.total);
  } catch (error) {
    console.error('Failed to fetch library curriculums:', error);
  } finally {
    setLoading(false);
  }
};
```

---

## 3. Different Pages, Different Filters

Use different `source_type` values depending on the page:

### Library Curriculum Page
```typescript
// Show ONLY official YouSpeak library content
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'library_master',
});
```

### Teacher's Own Curriculums Page
```typescript
// Show ONLY teacher-uploaded content
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'teacher_upload',
});
```

### All Curriculums Page (Combined View)
```typescript
// Show ALL curriculums (don't specify source_type)
const response = await curriculumService.listCurriculums(1, 50);
```

### Merged Curriculums Only
```typescript
// Show ONLY merged/combined curriculums
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'merged',
});
```

---

## 4. Performance Impact

### Before Fix
- Request: `GET /api/v1/curriculums?page=1&page_size=50`
- Returned: **ALL** curriculums (teacher + library + merged)
- Frontend had to filter manually
- Fetched unnecessary data over network

### After Fix
- Request: `GET /api/v1/curriculums?page=1&page_size=50&source_type=library_master`
- Returns: **ONLY** library curriculums
- Filtered at database level (efficient)
- No unnecessary data transfer

**Expected performance improvement:**
- Faster page load (fewer records to transfer)
- Reduced network bandwidth
- Better user experience

---

## 5. Combining Filters

You can combine `source_type` with other filters:

```typescript
// Example 1: Library curriculums in French only
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'library_master',
  language_id: 2, // French
});

// Example 2: Published library curriculums with search
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'library_master',
  status: 'published',
  search: 'beginner',
});

// Example 3: Teacher uploads that are drafts
const response = await curriculumService.listCurriculums(1, 50, {
  source_type: 'teacher_upload',
  status: 'draft',
});
```

---

## 6. API Response Format

The response will look the same, but filtered:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "title": "French for Beginners",
      "description": "...",
      "source_type": "library_master",  // ← Only library_master when filtered
      "status": "published",
      "language_name": "French",
      "classes": [...],
      "topics": [...]
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 50,
    "total": 10,  // ← Reduced count (only library curriculums)
    "total_pages": 1
  }
}
```

---

## 7. Deployment Timeline

**Backend Status:**
- ✅ Code merged to `main` (commit `d4fde5c`)
- ⏳ CI/CD building Docker image (~8 minutes from 17:34 UTC)
- ⏳ Deploy to ECS staging
- ⏳ Deploy to production

**Frontend Action:**
- **Now:** Update your code with `source_type` parameter
- **After backend deploys:** Test on staging
- **Then:** Deploy frontend to production

---

## 8. Backward Compatibility

The new `source_type` parameter is **optional**:

```typescript
// This still works (returns ALL curriculums)
await curriculumService.listCurriculums(1, 50);

// This is new (returns filtered curriculums)
await curriculumService.listCurriculums(1, 50, {
  source_type: 'library_master'
});
```

Your frontend code won't break when the backend deploys, but you'll need to add `source_type` to get the filtering benefit.

---

## 9. TypeScript Types (Optional but Recommended)

Add proper types for better IDE support:

```typescript
// types/curriculum.ts

export type CurriculumSourceType = 'library_master' | 'teacher_upload' | 'merged';
export type CurriculumStatus = 'draft' | 'published' | 'archived';

export interface Curriculum {
  id: string;
  title: string;
  description?: string;
  source_type: CurriculumSourceType;  // ← Now filterable
  status: CurriculumStatus;
  language_name?: string;
  classes: Array<{id: string; name: string}>;
  topics: Topic[];
  created_at: string;
  file_url?: string;
}

export interface ListCurriculumsParams {
  page?: number;
  page_size?: number;
  status?: CurriculumStatus;
  language_id?: number;
  search?: string;
  source_type?: CurriculumSourceType;  // ← Add this
}
```

---

## 10. Testing Checklist

After backend deploys, test these scenarios:

- [ ] **Test 1:** Fetch library curriculums only
  ```typescript
  const response = await curriculumService.listCurriculums(1, 50, {
    source_type: 'library_master'
  });
  console.log('All should be library_master:', response.data.map(c => c.source_type));
  ```

- [ ] **Test 2:** Fetch teacher uploads only
  ```typescript
  const response = await curriculumService.listCurriculums(1, 50, {
    source_type: 'teacher_upload'
  });
  console.log('All should be teacher_upload:', response.data.map(c => c.source_type));
  ```

- [ ] **Test 3:** Fetch all (no filter)
  ```typescript
  const response = await curriculumService.listCurriculums(1, 50);
  console.log('Should have mixed types:', response.data.map(c => c.source_type));
  ```

- [ ] **Test 4:** Combine with search
  ```typescript
  const response = await curriculumService.listCurriculums(1, 50, {
    source_type: 'library_master',
    search: 'french'
  });
  ```

- [ ] **Test 5:** Verify page loads fast (< 1 second expected)

---

## Summary

**What Changed (Backend):**
- ✅ Added `source_type` query parameter to `GET /api/v1/curriculums`
- ✅ Values: `library_master`, `teacher_upload`, `merged`
- ✅ Filters at database level (efficient)

**What to Do (Frontend):**
1. Add `source_type` parameter to your curriculum API service
2. Update Library Curriculum page to use `source_type: 'library_master'`
3. Test after backend deployment
4. Deploy frontend changes

**Result:**
- Library Curriculum page loads only library content
- Faster page load, no manual filtering needed
- Better user experience

---

**Questions?** Check the API docs or test on staging once deployed!
