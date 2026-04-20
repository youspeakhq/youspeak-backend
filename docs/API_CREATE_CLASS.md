# Create Class Endpoint Documentation

## Endpoint
```
POST /api/v1/my-classes
```

## Authentication
Requires teacher authentication. Include JWT token in Authorization header:
```
Authorization: Bearer <teacher_access_token>
```

## Content Types

### Option 1: JSON (Simple)
```
Content-Type: application/json
```

### Option 2: Multipart Form-Data (With CSV Roster)
```
Content-Type: multipart/form-data
```

---

## Request Format

### JSON Request Body

```json
{
  "name": "French 101",
  "description": "Beginner French class",
  "timeline": "Spring 2026",
  "schedule": [
    {
      "day_of_week": "Mon",
      "start_time": "09:00:00",
      "end_time": "10:00:00"
    },
    {
      "day_of_week": "Wed",
      "start_time": "09:00:00",
      "end_time": "10:00:00"
    }
  ],
  "language_id": 1,
  "semester_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "active"
}
```

### Multipart Form-Data Request

When uploading a CSV roster file along with class creation:

**Form Fields:**
- `data`: JSON string containing the class data (same structure as JSON request)
- `file`: CSV file with roster data

**CSV File Format:**
```csv
first_name,last_name,email
Alice,Smith,alice@example.com
Bob,Jones,bob@example.com
```

**Example cURL:**
```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/my-classes" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F 'data={"name":"French 101","schedule":[{"day_of_week":"Mon","start_time":"09:00:00","end_time":"10:00:00"}],"language_id":1,"semester_id":"YOUR_SEMESTER_ID"}' \
  -F 'file=@roster.csv;type=text/csv'
```

---

## Field Specifications

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Class name | "French 101" |
| `schedule` | array | Array of schedule objects (see below) | See schedule format |
| `language_id` | integer | Language identifier (1=French, 2=Spanish, etc.) | 1 |
| `semester_id` | UUID | Semester UUID (from GET /schools/semesters) | "123e4567-e89b-12d3-a456-426614174000" |

### Optional Fields

| Field | Type | Default | Description | Example |
|-------|------|---------|-------------|---------|
| `description` | string | null | Class description | "Beginner French class" |
| `timeline` | string | null | Timeline text | "Jan 2026 - May 2026" |
| `sub_class` | string | null | Sub-class name | "Section A" |
| `level` | string | null | Proficiency level | "beginner" |
| `class_id` | UUID | null | Class UUID | "456e7890-e89b-12d3-a456-426614174111" |
| `status` | string | "active" | Class status: "active", "inactive", or "archived" | "active" |

### Schedule Object Format

Each schedule object in the `schedule` array must have:

| Field | Type | Description | Valid Values |
|-------|------|-------------|--------------|
| `day_of_week` | string | Day of the week | "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun" |
| `start_time` | string | Class start time (24-hour format) | "09:00:00", "14:30:00" |
| `end_time` | string | Class end time (24-hour format) | "10:00:00", "16:00:00" |

**Example:**
```json
{
  "day_of_week": "Mon",
  "start_time": "09:00:00",
  "end_time": "10:00:00"
}
```

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "e40e3a50-fd22-47de-907f-0cdada6b1845",
    "name": "French 101",
    "description": "Beginner French class",
    "timeline": "Spring 2026",
    "status": "active",
    "school_id": "61981545-179f-41b0-a910-e4d680f5bcb6",
    "semester_id": "bbf3c6e4-c26d-4389-a6f2-3c9e1d125369",
    "language_id": 1,
    "class_id": null,
    "sub_class": null,
    "schedules": [
      {
        "day_of_week": "Mon",
        "start_time": "09:00:00",
        "end_time": "10:00:00"
      }
    ],
    "roster_import": {
      "enrolled": 2,
      "created": 1,
      "errors": []
    }
  },
  "message": "Class created successfully"
}
```

**Note:** The `roster_import` field only appears if a CSV file was provided.

### Error Responses

#### 400 Bad Request
Invalid data provided (e.g., nonexistent semester_id or language_id):
```json
{
  "detail": "Invalid data provided, e.g., nonexistent semester_id or language_id."
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
      "loc": ["body", "schedule"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Complete Examples

### Example 1: Simple Class Creation (JSON)

**Request:**
```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/my-classes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGc..." \
  -d '{
    "name": "Spanish 202",
    "description": "Intermediate Spanish",
    "timeline": "Fall 2026",
    "schedule": [
      {
        "day_of_week": "Tue",
        "start_time": "10:00:00",
        "end_time": "11:30:00"
      },
      {
        "day_of_week": "Thu",
        "start_time": "10:00:00",
        "end_time": "11:30:00"
      }
    ],
    "language_id": 2,
    "semester_id": "bbf3c6e4-c26d-4389-a6f2-3c9e1d125369"
  }'
```

### Example 2: Class Creation with CSV Roster

**roster.csv:**
```csv
first_name,last_name,email
Emma,Wilson,emma@example.com
Liam,Brown,liam@example.com
Olivia,Davis,olivia@example.com
```

**Request:**
```bash
curl -X POST "https://api-staging.youspeakhq.com/api/v1/my-classes" \
  -H "Authorization: Bearer eyJhbGc..." \
  -F 'data={"name":"German 101","description":"Beginner German","schedule":[{"day_of_week":"Mon","start_time":"13:00:00","end_time":"14:30:00"}],"language_id":3,"semester_id":"bbf3c6e4-c26d-4389-a6f2-3c9e1d125369"}' \
  -F 'file=@roster.csv;type=text/csv'
```

### Example 3: Python with requests

```python
import requests

# Get your token first (login endpoint)
token = "YOUR_ACCESS_TOKEN"
semester_id = "YOUR_SEMESTER_ID"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "name": "Italian 101",
    "description": "Introduction to Italian",
    "timeline": "Spring 2026",
    "schedule": [
        {
            "day_of_week": "Wed",
            "start_time": "15:00:00",
            "end_time": "16:30:00"
        }
    ],
    "language_id": 4,
    "semester_id": semester_id
}

response = requests.post(
    "https://api-staging.youspeakhq.com/api/v1/my-classes",
    headers=headers,
    json=payload
)

if response.status_code == 200:
    class_data = response.json()["data"]
    print(f"Class created with ID: {class_data['id']}")
else:
    print(f"Error: {response.json()}")
```

### Example 4: JavaScript/TypeScript with fetch

```typescript
const createClass = async (token: string, semesterId: string) => {
  const response = await fetch(
    "https://api-staging.youspeakhq.com/api/v1/my-classes",
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        name: "Mandarin 101",
        description: "Introduction to Mandarin Chinese",
        timeline: "Summer 2026",
        schedule: [
          {
            day_of_week: "Mon",
            start_time: "08:00:00",
            end_time: "09:30:00"
          },
          {
            day_of_week: "Wed",
            start_time: "08:00:00",
            end_time: "09:30:00"
          },
          {
            day_of_week: "Fri",
            start_time: "08:00:00",
            end_time: "09:30:00"
          }
        ],
        language_id: 5,
        semester_id: semesterId,
        status: "active"
      })
    }
  );

  if (response.ok) {
    const result = await response.json();
    console.log("Class created:", result.data);
    return result.data;
  } else {
    const error = await response.json();
    console.error("Failed to create class:", error);
    throw new Error(error.detail);
  }
};
```

---

## Prerequisites

Before creating a class, you need:

1. **Teacher Authentication Token**
   - Register a teacher account via school admin
   - Login to get access token

2. **Semester ID**
   - Fetch available semesters: `GET /api/v1/schools/semesters`
   - Use the `id` of the desired semester

3. **Language ID**
   - Standard language IDs (these may vary by deployment):
     - 1 = French
     - 2 = Spanish
     - 3 = German
     - etc.

4. **(Optional) Class ID**
   - If assigning to a class: `GET /api/v1/my-classes`
   - Use the `id` of the desired class

---

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| 400: Invalid semester_id | Semester doesn't exist or is inactive | Get valid semester from /schools/semesters |
| 400: Invalid language_id | Language ID doesn't exist | Verify language_id with your admin |
| 422: field required | Missing required field | Check all required fields are present |
| 422: Invalid time format | Wrong time format | Use "HH:MM:SS" format (e.g., "09:00:00") |
| 422: Invalid day_of_week | Invalid day string | Use: Mon, Tue, Wed, Thu, Fri, Sat, Sun |
| 401: Not authenticated | Missing/invalid token | Login again to get fresh token |
| 403: Not a teacher | User account is not a teacher | Ensure you're logged in as a teacher |

---

## Testing

You can test this endpoint using:

1. **Swagger UI**: Visit `https://api-staging.youspeakhq.com/docs`
2. **ReDoc**: Visit `https://api-staging.youspeakhq.com/redoc`
3. **Test Script**: Use the provided test script in the repository:
   ```bash
   ./test_create_class_endpoint.sh
   ```

---

## Related Endpoints

- **List My Classes**: `GET /api/v1/my-classes`
- **Get Class Details**: `GET /api/v1/my-classes/{class_id}`
- **Update Class**: `PATCH /api/v1/my-classes/{class_id}`
- **Get Class Roster**: `GET /api/v1/my-classes/{class_id}/roster`
- **Add Student to Class**: `POST /api/v1/my-classes/{class_id}/roster`
- **List Semesters**: `GET /api/v1/schools/semesters`
- **List Classes**: `GET /api/v1/my-classes`

---

## Notes

- A class can have multiple schedule entries (e.g., Mon/Wed/Fri)
- Times must be in 24-hour format
- All dates/times are stored in UTC but displayed in the school's timezone
- When using multipart form-data, the CSV roster is imported after the class is created
- CSV import is idempotent - students with existing emails will be enrolled, new students will be created
- The `roster_import` response field shows: `enrolled` (total), `created` (new students), `errors` (list of issues)
