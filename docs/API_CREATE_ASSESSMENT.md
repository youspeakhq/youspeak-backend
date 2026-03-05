# Create Assessment Endpoint Documentation

## Important: Assessment vs Assignment Terminology

**"Assessment" and "Assignment" refer to the SAME entity:**
- API routes use `/api/v1/assessments`
- Database model is called `Assignment`
- They are interchangeable terms for the same concept
- **No separate "/assignments" endpoint exists**

**Differentiation is by the `type` field:**
- `type: "oral"` → Oral assessments (speaking/listening)
- `type: "written"` → Written assessments (essays, tests)

---

## Endpoint
```
POST /api/v1/assessments
```

## Authentication
Requires teacher authentication. Include JWT token in Authorization header:
```
Authorization: Bearer <teacher_access_token>
```

---

## Request Format

### JSON Request Body

```json
{
  "title": "French Vocabulary Quiz",
  "type": "written",
  "instructions": "Complete all questions carefully",
  "due_date": "2026-03-20T23:59:59Z",
  "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
  "enable_ai_marking": true,
  "questions": [
    {
      "question_id": "123e4567-e89b-12d3-a456-426614174000",
      "points": 10
    }
  ]
}
```

---

## Field Specifications

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `title` | string | Assessment name/title | "French Vocabulary Quiz" |
| `type` | string | Assessment type: **"oral" or "written"** | "written" |
| `class_ids` | array | Array of class UUIDs (classes to assign this assessment to) | `["uuid1", "uuid2"]` |

### Optional Fields

| Field | Type | Default | Description | Example |
|-------|------|---------|-------------|---------|
| `instructions` | string | null | Task instructions for students | "Answer all questions in complete sentences" |
| `due_date` | datetime | null | Due date/time (ISO 8601 format) | "2026-03-20T23:59:59Z" |
| `enable_ai_marking` | boolean | false | Enable AI-powered grading | true |
| `questions` | array | [] | Array of question objects (from question bank) | See below |

### Type Field Values

The `type` field differentiates the assessment category:

| Value | Description | Use Case |
|-------|-------------|----------|
| `"oral"` | Oral assessment | Speaking exercises, pronunciation tests, oral presentations, listening comprehension |
| `"written"` | Written assessment | Essays, written exams, comprehension tests, written assignments |

### Questions Array Format

Each question object in the `questions` array (optional):

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | UUID | ID of question from the teacher's question bank |
| `points` | integer | Points assigned to this question (default: 1) |

**Example:**
```json
{
  "question_id": "123e4567-e89b-12d3-a456-426614174000",
  "points": 15
}
```

**Note:** Questions must exist in the teacher's question bank. Create questions first using:
- `POST /api/v1/assessments/questions/bank` - Create manually
- `POST /api/v1/assessments/questions/generate` - Generate with AI
- `POST /api/v1/assessments/questions/upload` - Upload from file

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "a8b9c0d1-e2f3-4a5b-6c7d-8e9f0a1b2c3d",
    "title": "French Vocabulary Quiz",
    "type": "written",
    "status": "draft",
    "instructions": "Complete all questions carefully",
    "due_date": "2026-03-20T23:59:59",
    "enable_ai_marking": true
  },
  "message": "Assessment created successfully"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique assessment identifier |
| `title` | string | Assessment title |
| `type` | string | Assessment type ("oral" or "written") |
| `status` | string | Current status ("draft" or "published") |
| `instructions` | string | Task instructions |
| `due_date` | datetime | Due date |
| `enable_ai_marking` | boolean | AI marking enabled |

### Error Responses

#### 400 Bad Request
Invalid data (e.g., invalid class_ids, invalid question_ids):
```json
{
  "detail": "One or more question_ids are invalid or do not belong to you."
}
```

#### 401 Unauthorized
Missing or invalid authentication token:
```json
{
  "detail": "Not authenticated"
}
```

#### 403 Forbidden
User is not a teacher:
```json
{
  "detail": "User is not a teacher"
}
```

#### 422 Unprocessable Entity
Invalid request format or missing required fields:
```json
{
  "detail": [
    {
      "loc": ["body", "type"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Complete Examples

### Example 1: Simple Written Assessment (No Questions)

```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/assessments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Unit 3 Essay",
    "type": "written",
    "instructions": "Write a 500-word essay about French culture",
    "due_date": "2026-03-25T23:59:59Z",
    "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
    "enable_ai_marking": false
  }'
```

### Example 2: Oral Assessment with Due Date

```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/assessments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Oral Presentation - French Culture",
    "type": "oral",
    "instructions": "Present for 5 minutes about your favorite French region",
    "due_date": "2026-04-01T23:59:59Z",
    "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
    "enable_ai_marking": true
  }'
```

### Example 3: Written Quiz with Questions from Bank

First, create questions in your question bank:

```bash
# Create a question
curl -X POST "https://api-staging.youspeakhq.com/api/v1/assessments/questions/bank" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question_text": "What is the capital of France?",
    "type": "multiple_choice",
    "correct_answer": "Paris",
    "options": ["Paris", "Lyon", "Marseille", "Toulouse"]
  }'
```

Then create assessment with questions:

```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/assessments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Geography Quiz",
    "type": "written",
    "instructions": "Answer all multiple choice questions",
    "due_date": "2026-03-30T23:59:59Z",
    "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
    "enable_ai_marking": false,
    "questions": [
      {
        "question_id": "YOUR_QUESTION_ID",
        "points": 10
      }
    ]
  }'
```

### Example 4: Python with requests

```python
import requests
from datetime import datetime, timedelta

# Authentication token
token = "YOUR_ACCESS_TOKEN"
class_id = "YOUR_CLASS_ID"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Create written assessment
payload = {
    "title": "French Comprehension Test",
    "type": "written",  # or "oral" for oral assessments
    "instructions": "Read the passage and answer the questions below.",
    "due_date": (datetime.now() + timedelta(days=7)).isoformat() + "Z",
    "class_ids": [class_id],
    "enable_ai_marking": True
}

response = requests.post(
    "https://api-staging.youspeakhq.com/api/v1/assessments",
    headers=headers,
    json=payload
)

if response.status_code == 200:
    assessment = response.json()["data"]
    print(f"✅ Assessment created with ID: {assessment['id']}")
    print(f"   Type: {assessment['type']}")
    print(f"   Status: {assessment['status']}")
else:
    print(f"❌ Error: {response.json()}")
```

### Example 5: JavaScript/TypeScript with fetch

```typescript
interface AssessmentCreate {
  title: string;
  type: "oral" | "written";
  instructions?: string;
  due_date?: string;
  class_ids: string[];
  enable_ai_marking?: boolean;
  questions?: Array<{
    question_id: string;
    points: number;
  }>;
}

const createAssessment = async (
  token: string,
  data: AssessmentCreate
) => {
  const response = await fetch(
    "https://api-staging.youspeakhq.com/api/v1/assessments",
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    }
  );

  if (response.ok) {
    const result = await response.json();
    console.log("Assessment created:", result.data);
    return result.data;
  } else {
    const error = await response.json();
    console.error("Failed to create assessment:", error);
    throw new Error(error.detail);
  }
};

// Usage - Create oral assessment
await createAssessment(token, {
  title: "Pronunciation Practice",
  type: "oral",
  instructions: "Record yourself reading the passage aloud",
  due_date: "2026-04-05T23:59:59Z",
  class_ids: [classId],
  enable_ai_marking: true
});

// Usage - Create written assessment
await createAssessment(token, {
  title: "Grammar Exercise",
  type: "written",
  instructions: "Complete exercises 1-10",
  class_ids: [classId],
  enable_ai_marking: false
});
```

---

## Workflow

### Complete Assessment Creation Flow

1. **Create Class** (if not exists)
   ```
   POST /api/v1/my-classes
   ```

2. **Create Questions** (optional - can add questions later)
   - Manual: `POST /api/v1/assessments/questions/bank`
   - AI Generate: `POST /api/v1/assessments/questions/generate`
   - Upload: `POST /api/v1/assessments/questions/upload`

3. **Create Assessment** (draft)
   ```
   POST /api/v1/assessments
   ```

4. **Attach/Update Questions** (optional)
   ```
   PUT /api/v1/assessments/{assessment_id}/questions
   ```

5. **Publish Assessment**
   ```
   POST /api/v1/assessments/{assessment_id}/publish
   ```

6. **Monitor Submissions**
   ```
   GET /api/v1/assessments/{assessment_id}/submissions
   ```

7. **Grade Submissions**
   - Manual: `PATCH /api/v1/assessments/{assessment_id}/submissions/{submission_id}/grade`
   - AI: `POST /api/v1/assessments/{assessment_id}/submissions/{submission_id}/grade-with-ai`

---

## Prerequisites

Before creating an assessment, you need:

1. **Teacher Authentication Token**
   - Register as a teacher
   - Login to get access token

2. **Class ID(s)**
   - Create class: `POST /api/v1/my-classes`
   - Or list existing: `GET /api/v1/my-classes`

3. **(Optional) Question Bank**
   - Create questions: `POST /api/v1/assessments/questions/bank`
   - List questions: `GET /api/v1/assessments/questions/bank`

---

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| 400: Invalid class_ids | Class doesn't exist or teacher doesn't have access | Verify class_id from GET /my-classes |
| 400: Invalid question_ids | Question doesn't exist or doesn't belong to teacher | Create questions first in question bank |
| 422: field required (type) | Missing required `type` field | Include type: "oral" or "written" |
| 422: field required (title) | Missing required `title` field | Provide assessment title |
| 422: field required (class_ids) | Missing required `class_ids` array | Provide at least one class_id |
| 422: Invalid type value | type is not "oral" or "written" | Use only "oral" or "written" |
| 401: Not authenticated | Missing/invalid token | Login again to get fresh token |
| 403: Not a teacher | User account is not a teacher | Ensure logged in as teacher |

---

## Assessment Status Lifecycle

| Status | Description | Next Actions |
|--------|-------------|--------------|
| `draft` | Assessment created, not visible to students | Edit, add questions, publish |
| `published` | Assessment published, visible to students | View submissions, grade |

**Status Transitions:**
- Create assessment → status: `draft`
- Publish assessment → status: `published`
- Cannot unpublish once published

---

## Related Endpoints

### Assessment Management
- **List Assessments**: `GET /api/v1/assessments`
- **Get Assessment Details**: `GET /api/v1/assessments/{assessment_id}`
- **Update Assessment**: `PATCH /api/v1/assessments/{assessment_id}`
- **Publish Assessment**: `POST /api/v1/assessments/{assessment_id}/publish`

### Question Bank
- **List Questions**: `GET /api/v1/assessments/questions/bank`
- **Create Question**: `POST /api/v1/assessments/questions/bank`
- **Generate Questions (AI)**: `POST /api/v1/assessments/questions/generate`
- **Upload Questions**: `POST /api/v1/assessments/questions/upload`

### Assessment Questions
- **Get Assessment Questions**: `GET /api/v1/assessments/{assessment_id}/questions`
- **Set Assessment Questions**: `PUT /api/v1/assessments/{assessment_id}/questions`

### Submissions & Grading
- **List Submissions**: `GET /api/v1/assessments/{assessment_id}/submissions`
- **Get Submission**: `GET /api/v1/assessments/{assessment_id}/submissions/{submission_id}`
- **Grade Submission**: `PATCH /api/v1/assessments/{assessment_id}/submissions/{submission_id}/grade`
- **AI Grade Submission**: `POST /api/v1/assessments/{assessment_id}/submissions/{submission_id}/grade-with-ai`

### Analytics
- **Get Analytics Summary**: `GET /api/v1/assessments/analytics/summary`
- **List Topics from Curriculum**: `GET /api/v1/assessments/topics`

---

## Key Differences: Oral vs Written

### Oral Assessments (`type: "oral"`)
- **Purpose**: Speaking, listening, pronunciation practice
- **Submission Format**: Audio recordings
- **Grading**: Can use AI marking for pronunciation/fluency analysis
- **Use Cases**:
  - Oral presentations
  - Reading aloud exercises
  - Conversation practice
  - Pronunciation tests

### Written Assessments (`type: "written"`)
- **Purpose**: Writing, reading comprehension, grammar
- **Submission Format**: Text, PDFs, documents
- **Grading**: Can use AI marking for grammar/content analysis
- **Use Cases**:
  - Essays
  - Grammar exercises
  - Reading comprehension tests
  - Written exams

---

## Notes

- Assessments start in `draft` status - students can't see them until published
- Questions can be added during creation or later using PUT endpoint
- Questions must exist in your question bank before attaching to assessment
- One assessment can be assigned to multiple classes via `class_ids` array
- Due dates are optional but recommended for student deadline management
- AI marking (`enable_ai_marking: true`) works for both oral and written assessments
- The `type` field cannot be changed after creation
- All dates/times use ISO 8601 format with timezone (e.g., "2026-03-20T23:59:59Z")

---

## Testing

Test this endpoint using:

1. **Swagger UI**: `https://api-staging.youspeakhq.com/docs`
2. **ReDoc**: `https://api-staging.youspeakhq.com/redoc`
3. **Test Script**: Use the provided test script:
   ```bash
   ./test_assessment_endpoint.sh
   ```
