# Response to Frontend Developer Feedback

**Date:** 2026-03-28

---

## Issue 1: Teacher Cannot Add Students (403 Error)

### Current Understanding

There are **TWO SEPARATE** concepts in the system:

#### 1. **Classes** (Teacher-managed) - `/my-classes`
- **What:** Teaching classes that teachers create and manage
- **Who manages:** Teachers
- **Endpoint to add students:** `POST /api/v1/my-classes/{class_id}/roster`
- **Authorization:** ✅ Already allows teachers
- **Requirement:** Teacher must be assigned to the class

#### 2. **Classrooms** (Admin-managed) - `/classrooms`
- **What:** Administrative/organizational classrooms for the school
- **Who manages:** School admins (and now teachers for classrooms they teach)
- **Endpoint to add students:** `POST /api/v1/classrooms/{classroom_id}/students`
- **Authorization:** ✅ Fixed today - now allows admins + teachers
- **Requirement:** Teacher must be assigned to teach the classroom

---

## Root Cause Analysis

### The 403 Error You're Seeing Could Be:

**Option A: Wrong Endpoint**
- ❌ Frontend is calling `/api/v1/classrooms/{id}/students` (admin endpoint)
- ✅ Should call `/api/v1/my-classes/{class_id}/roster` (teacher endpoint)

**Option B: Teacher Not Assigned to Class**
- The teacher is trying to add students to a class they don't teach
- Endpoint checks: `teacher_classes = await AcademicService.get_teacher_classes(db, current_user.id)`
- If teacher is not assigned to the class → 403 with "You do not teach this class"

**Option C: Student School Mismatch**
- Student belongs to a different school
- Would return 400 (not 403) with error message

---

## Solution

### Step 1: Verify Which Endpoint Frontend Is Using

**Check your frontend code - which endpoint are you calling?**

#### ✅ **CORRECT Endpoint (for teachers adding students to their class):**
```
POST /api/v1/my-classes/{class_id}/roster
Authorization: Bearer {teacher_token}
Content-Type: application/json

{
  "student_id": "uuid-here",
  "role": "student"  // Options: "student", "leader", "vice_leader"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "student-uuid",
    "email": "student@example.com",
    "full_name": "Student Name",
    // ... full user object
  },
  "message": "Student added to class"
}
```

**Response 403 (teacher doesn't teach this class):**
```json
{
  "detail": "You do not teach this class"
}
```

**Response 400 (student can't be added):**
```json
{
  "detail": "Student already in class" // or other error
}
```

#### ❌ **WRONG Endpoint (this is for admin/classroom management):**
```
POST /api/v1/classrooms/{classroom_id}/students
```

---

### Step 2: Verify Teacher Is Assigned to the Class

**To check if teacher is assigned to a class:**
```
GET /api/v1/my-classes
Authorization: Bearer {teacher_token}
```

This returns all classes the teacher is assigned to. Make sure the `class_id` you're trying to add students to is in this list.

---

### Step 3: Test Flow

1. **Login as teacher** → Get access token
2. **Get teacher's classes:** `GET /api/v1/my-classes`
3. **Pick a class_id** from the response
4. **Get students list:** `GET /api/v1/students` (as admin) or from school roster
5. **Add student to class:** `POST /api/v1/my-classes/{class_id}/roster`

---

## Issue 2: Join Arena Email

### Status: Need to Investigate

You mentioned checking for a "join arena" email. Let me investigate the email system for arena invitations.

**Questions:**
1. What triggers this email? (Student joins arena? Teacher invites student?)
2. What's the expected flow? (Link in email? Arena code?)
3. Is this related to the learning arenas or speaking arenas?

### Email System Check

Let me search for arena-related email templates and sending logic...

---

## Testing Checklist

### For Add Student to Class:

- [ ] Confirm frontend is calling `/api/v1/my-classes/{class_id}/roster` (NOT `/classrooms`)
- [ ] Verify teacher token is valid and has teacher role
- [ ] Confirm teacher is assigned to the class (GET `/my-classes` includes this class_id)
- [ ] Verify student exists and belongs to same school
- [ ] Test with valid payload: `{"student_id": "uuid", "role": "student"}`

### For Arena Email:

- [ ] Identify which arena feature needs email
- [ ] Check if email template exists
- [ ] Verify email sending service is configured in staging
- [ ] Test email delivery (check spam folder too)

---

## Next Steps

**Please provide:**
1. **Exact endpoint URL** your frontend is calling for adding students
2. **Sample request payload** you're sending
3. **Full 403 error response** (including detail message)
4. **Teacher's class list** (response from GET `/my-classes` for this teacher)
5. **More context on "join arena" email:**
   - When should it be sent?
   - Who receives it?
   - What action triggered it?

With this information, I can pinpoint the exact issue and fix it immediately.

---

## API Documentation

### Teacher Class Management Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/my-classes` | List teacher's classes | Teacher |
| POST | `/api/v1/my-classes` | Create new class | Teacher |
| GET | `/api/v1/my-classes/{class_id}` | Get class details | Teacher |
| GET | `/api/v1/my-classes/{class_id}/roster` | List class students | Teacher |
| POST | `/api/v1/my-classes/{class_id}/roster` | **Add student to class** | Teacher |
| POST | `/api/v1/my-classes/{class_id}/roster/import` | Bulk import students (CSV) | Teacher |

### Admin Classroom Management Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/classrooms` | List all classrooms | Admin |
| POST | `/api/v1/classrooms` | Create classroom | Admin |
| GET | `/api/v1/classrooms/{id}` | Get classroom | Admin |
| POST | `/api/v1/classrooms/{id}/students` | Add student to classroom | Admin/Teacher* |
| POST | `/api/v1/classrooms/{id}/teachers` | Assign teacher to classroom | Admin |

*Teacher can only add to classrooms they teach (fixed today)

---

**Ready to debug as soon as you provide the requested information above!**

---

**Fixed by:** Claude Code
**Date:** 2026-03-28
