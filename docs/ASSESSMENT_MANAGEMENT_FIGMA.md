# Assessment Management – Figma → Backend Alignment

Source: Figma file **"Indiigoo Labs _You Speak_ AI language assistant"**, page **Websites**, section **Assessment management** (node `3743:5415`). Fetched via Figma MCP (`get_design_context`, `get_node`).

---

## 1. Figma screens (summary)

| Screen / Frame | Purpose |
|----------------|--------|
| **Task Management** (`3714:12153`) | Dashboard: stats (Total assessments, Total assignments, Average completion rate), filters (search by class/task name, Current Term), table (Class Name, Active Students, Task Topic, Type, Average Score, View by student), Add New Task. |
| **Create Assessment** (`4190:6236`) | Create New Task: Basic info (Assessment Title, Detailed instruction, Associated class(es), Due date, Assessment type); Content and questions (Select question topics, Add more topics, Generate with AI / Upload questions manually / Upload marking scheme); Enable AI marking; Create Assessment. |
| **Review generated questions** (`3729:5693`) | Review/edit AI-generated questions before creating assessment. |
| **Select class** (`3729:5790`) | Classes dropdown (for filters / assignment association). |
| **Assessment type** (`3729:5797`) | Assessment type dropdown (oral/written). |
| **Class students list for analytics** (`4031:6310`) | Students Performance: Switch Task, Switch class, search student; table (Student Name, Status, Score By %, View Analytics); pagination; Download. |
| **Per student task performance** (`4031:6248`) | Per-student metrics/charts. |

---

## 2. Data fields (from Figma)

**Create Assessment form**

- **Basic information:** Assessment Title (text), Detailed instruction (textarea), Associated class(es) (multi-select), Due date (date), Assessment type (oral | written).
- **Content and questions:** Question topics (expandable list, optional “Detected from [class]”), Add more topics; then one of: Generate with AI, Upload questions manually (file), Upload marking scheme (file).
- **Enable AI marking** (toggle).

**Task Management table (per row)**

- Class Name, Active Students (count), Task Topic, Type (Assessment | Assignment), Average Score, More Actions (View by student).

**Class students list (per row)**

- Student Name, Status (Submitted | Pending), Score By %, More Actions (View Analytics).

---

## 3. Backend endpoint map

| Figma need | Endpoint | Method | Notes |
|------------|----------|--------|--------|
| List teacher’s classes (dropdowns) | `/api/v1/my-classes` | GET | Existing. |
| List tasks/assessments (dashboard) | `/api/v1/assessments` | GET | Query: `class_id`, `type`, `search`, `page`, `page_size`. |
| Task Performance Analytics stats | `/api/v1/assessments/analytics/summary` | GET | Optional: `class_id`, term. Returns total_assessments, total_assignments, average_completion_rate. |
| Task table rows (by class/task) | `/api/v1/assessments` | GET | Response includes class name, active students, topic/summary, type, average score. |
| Create assessment | `/api/v1/assessments` | POST | Body: title, instructions, type, due_date, class_ids, optional question_ids + points. |
| Get one assessment | `/api/v1/assessments/{id}` | GET | For edit / review. |
| Update assessment | `/api/v1/assessments/{id}` | PATCH | Draft only or allow publish. |
| Publish assessment | `/api/v1/assessments/{id}/publish` | POST | Optional. |
| List questions for assignment | `/api/v1/assessments/{id}/questions` | GET | For “Review generated questions”. |
| Set questions on assignment | `/api/v1/assessments/{id}/questions` | PUT | question_ids + points. |
| Question bank (teacher) | `/api/v1/assessments/questions` | GET, POST | List/Create questions for reuse. |
| Submissions by assignment | `/api/v1/assessments/{id}/submissions` | GET | Query: `page`, `page_size`, `status`, `search` (student name). For “Class students list”. |
| Get one submission | `/api/v1/assessments/{assignment_id}/submissions/{submission_id}` | GET | For View Analytics. |
| Grade submission | `/api/v1/assessments/{assignment_id}/submissions/{submission_id}/grade` | PATCH | teacher_score, grade_score, status. |
| Students Performance (by class + task) | `/api/v1/assessments/{id}/submissions` | GET | Same as submissions list; filter by assignment = task. |

---

## 4. Model alignment

- **assignments** ↔ Figma “Assessment” / “Task” (title, instructions, type, due_date, status, class_ids).
- **questions** ↔ Question bank; **assignment_questions** (with points) ↔ questions attached to an assessment.
- **student_submissions** ↔ Status (Submitted/Pending), Score By % (grade_score or ai_score); teacher override via teacher_score/grade_score.

Topics for “Select question topics” / “Detected from [class]” can be supplied later by curriculum service or a dedicated topics endpoint; not required for minimal alignment.

---

## 5. Implemented vs to-do

- **Implemented in this pass:** Router `assessments`, GET/POST/PATCH assessments, GET/POST questions (bank), GET/PUT assignment questions, GET/PATCH submissions (list + grade), GET analytics summary. See `app/api/v1/endpoints/assessments.py` and `app/services/assessment_service.py`.
- **Optional later:** Publish endpoint, file upload for “Upload questions manually” / “Upload marking scheme”, AI generate (separate service), topics from curriculum.
