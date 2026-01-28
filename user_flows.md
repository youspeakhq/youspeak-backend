# YouSpeak API User Flows - End-to-End Guide

This document outlines the verified steps to interact with the YouSpeak API, covering the complete lifecycle from School Registration to Student Enrollment. These flows match the `tests/e2e_test.py` script.

## 1. School & Admin Onboarding
**Actor**: School Administrator
**Goal**: Register a new school tenant and create the initial admin account.

### Step 1.1: Register School
Creates the School entity, the first Admin user, creates a default "Term 1" semester, and seeds default languages (En, Es, Fr).
- **Endpoint**: `POST /api/v1/auth/register/school`
- **Payload**:
  ```json
  {
    "account_type": "school",
    "email": "admin@school.com",
    "password": "StrongPassword123!",
    "school_name": "My Academy",
    "admin_first_name": "Jane",
    "admin_last_name": "Doe"
  }
  ```
- **Response**: `200 OK` (School ID, Admin ID)

### Step 1.2: Admin Login
- **Endpoint**: `POST /api/v1/auth/login`
- **Payload**:
  ```json
  {
    "email": "admin@school.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response**: `200 OK` (Access Token)

---

## 2. Teacher Onboarding (Invitation System)
**Actor**: Admin invites Teacher -> Teacher registers.
**Goal**: Securely onboard a teacher linked to the correct school.

### Step 2.1: Generate Teacher Invite (Admin)
- **Endpoint**: `POST /api/v1/teachers`
- **Headers**: `Authorization: Bearer <AdminToken>`
- **Payload**:
  ```json
  {
    "first_name": "John",
    "last_name": "Smith",
    "email": "teacher@school.com"
  }
  ```
- **Response**: `200 OK`
  - `data.access_code`: "X82KS9LP" (In production, this would be emailed)

### Step 2.2: Verify Access Code (Public)
Teacher clicks link in email (frontend validates code).
- **Endpoint**: `POST /api/v1/auth/verify-code`
- **Payload**: `{ "access_code": "X82KS9LP" }`
- **Response**: `200 OK` (Valid)

### Step 2.3: Register Teacher
- **Endpoint**: `POST /api/v1/auth/register/teacher`
- **Payload**:
  ```json
  {
    "access_code": "X82KS9LP",
    "email": "teacher@school.com",
    "password": "TeacherPassword1!",
    "first_name": "John",
    "last_name": "Smith"
  }
  ```
- **Response**: `200 OK` (Teacher Account Created)

---

## 3. Classroom Setup
**Actor**: Teacher
**Goal**: Create a class schedule.

### Step 3.1: Login as Teacher
- **Endpoint**: `POST /api/v1/auth/login`
- **Response**: `200 OK` (Access Token - Role: TEACHER)

### Step 3.2: Get Metadata (Semesters)
Teacher needs to know which Semester to attach the class to.
- **Endpoint**: `GET /api/v1/schools/semesters`
- **Headers**: `Authorization: Bearer <TeacherToken>`
- **Response**: List of Semesters. Pick `id` of current one.

### Step 3.3: Create Class
- **Endpoint**: `POST /api/v1/my-classes`
- **Payload**:
  ```json
  {
    "name": "Spanish 101",
    "language_id": 2, 
    "semester_id": "<uuid-from-step-3.2>",
    "schedule": [
        { "day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00" },
        { "day_of_week": "Wed", "start_time": "09:00:00", "end_time": "10:00:00" }
    ]
  }
  ```
- **Response**: `200 OK` (Class ID)

---

## 4. Student Enrollment
**Actor**: Admin
**Goal**: Add a student and enroll them in a specific class.

### Step 4.1: Create & Enroll Student
- **Endpoint**: `POST /api/v1/students`
- **Headers**: `Authorization: Bearer <AdminToken>`
- **Payload**:
  ```json
  {
    "first_name": "Alice",
    "last_name": "Wonder",
    "class_id": "<uuid-from-step-3.3>", 
    "lang_id": 2
  }
  ```
  *(Note: email is auto-generated if omitted)*
- **Response**: `200 OK` (Student ID, User Created, Enrolled)

### Step 4.2: Verify Roster (Teacher)
- **Endpoint**: `GET /api/v1/my-classes/{class_id}/roster`
- **Headers**: `Authorization: Bearer <TeacherToken>`
- **Response**: List of students. Alice should be present.
