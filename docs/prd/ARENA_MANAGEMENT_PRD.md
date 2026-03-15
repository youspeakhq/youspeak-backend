# Arena Management - Product Requirements Document (PRD)

**Version:** 1.0
**Date:** 2026-03-15
**Status:** Implementation In Progress
**Context:** Teacher Console - Arena Management Module

---

## Table of Contents

1. [Overview](#overview)
2. [Figma Design Reference](#figma-design-reference)
3. [User Stories](#user-stories)
4. [Data Models](#data-models)
5. [API Endpoints](#api-endpoints)
6. [Screen Specifications](#screen-specifications)
7. [Gap Analysis](#gap-analysis)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Overview

Arena Management is a gamification feature that enables teachers to create, schedule, and moderate live speaking challenges for their classes. The system provides:

- **Challenge Creation**: Design custom speaking activities with criteria and rules
- **Scheduling**: Plan arena sessions with specific start times and durations
- **Performance Analytics**: Track participation rates and popular challenge types
- **Challenge Pool**: Browse and reuse pre-made challenges from YouSpeak catalog
- **Live Moderation**: Monitor and manage active arena sessions

**Target Users:** Teachers (authenticated)
**Authentication Required:** Teacher role via JWT
**Scope:** Teacher-owned classes only

---

## Figma Design Reference

**File:** "Indiigoo Labs _You Speak_ AI language assistant"
**Page:** Websites
**Section:** Arena management (Node: `3967:6382`)

### Identified Screens

| Screen Name | Figma Node ID | Purpose |
|------------|---------------|---------|
| **ArenaManagement Dashboard** | `3967:6383` | Main dashboard with stats, analytics, scheduled arenas list, and quick access |
| **Schedule an Arena** | `4008:8612` | Create/edit arena challenge form |
| **Arena Challenge Pool** | `4017:6276` | Browse pre-made challenges catalog |
| **Arena Preview** | `4018:6877` | Preview arena details before editing/moderating |
| **Learning Room** | `4031:6547` | Learning room entry (navigation) |
| **Add More Rules** | `4204:6295` | Rules input component |
| **Time Frame Dropdown** | `4008:8603` | Time period selector for analytics |

---

## User Stories

### Epic: Arena Challenge Creation
- **US-1:** As a teacher, I want to create custom speaking challenges so students can practice in a competitive environment
- **US-2:** As a teacher, I want to define judging criteria with percentage weights so scoring is objective
- **US-3:** As a teacher, I want to add multiple rules so students understand expectations
- **US-4:** As a teacher, I want to schedule arena start times so challenges happen at planned intervals

### Epic: Arena Management Dashboard
- **US-5:** As a teacher, I want to see active/upcoming/draft counts so I understand my arena pipeline
- **US-6:** As a teacher, I want to view participation analytics so I can optimize future challenges
- **US-7:** As a teacher, I want to see top-performing challenge types so I know what engages students
- **US-8:** As a teacher, I want to list all scheduled arenas so I can edit or moderate them

### Epic: Arena Moderation
- **US-9:** As a teacher, I want to moderate live arenas so I can provide real-time feedback
- **US-10:** As a teacher, I want to edit scheduled arenas so I can adjust details before they go live

### Epic: Challenge Pool (Future)
- **US-11:** As a teacher, I want to browse YouSpeak challenge pool so I can reuse proven challenges
- **US-12:** As a teacher, I want to publish my challenges to the pool so other teachers can benefit
- **US-13:** As a teacher, I want to clone challenges from the pool so I can customize them for my class

---

## Data Models

### Arena (Main Entity)

**Table:** `arenas`

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `id` | UUID | PK, auto | Unique identifier |
| `class_id` | UUID | FK(classes.id), NOT NULL, indexed | Associated class |
| `title` | String(255) | NOT NULL | Challenge title |
| `description` | Text | nullable | Challenge description |
| `status` | Enum(ArenaStatus) | NOT NULL, indexed, default=DRAFT | Current status |
| `start_time` | DateTime | nullable | Scheduled start time |
| `duration_minutes` | Integer | nullable | Challenge duration |
| `created_at` | DateTime | auto | Creation timestamp |
| `updated_at` | DateTime | auto | Last update timestamp |

**Relationships:**
- `class_` → Class (many-to-one)
- `criteria` → ArenaCriteria[] (one-to-many, cascade delete)
- `rules` → ArenaRule[] (one-to-many, cascade delete)
- `performers` → ArenaPerformer[] (one-to-many, cascade delete)
- `moderators` → User[] (many-to-many via arena_moderators)

---

### ArenaCriteria (Scoring Dimensions)

**Table:** `arena_criteria`

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `id` | UUID | PK, auto | Unique identifier |
| `arena_id` | UUID | FK(arenas.id), NOT NULL, indexed | Parent arena |
| `name` | String(255) | NOT NULL | Criterion name (e.g., "Pronunciation") |
| `weight_percentage` | Integer | NOT NULL | Weight in scoring (e.g., 40 for 40%) |

**Business Rules:**
- Total weights across all criteria for an arena should sum to 100%
- Frontend should validate this constraint before submission

---

### ArenaRule (Challenge Guidelines)

**Table:** `arena_rules`

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `id` | UUID | PK, auto | Unique identifier |
| `arena_id` | UUID | FK(arenas.id), NOT NULL, indexed | Parent arena |
| `description` | Text | NOT NULL | Rule text |

**Example Rules:**
- "Participants must speak for at least two minutes"
- "No reading from notes allowed"
- "Focus on natural pronunciation"

---

### ArenaPerformer (Student Participation)

**Table:** `arena_performers`

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `id` | UUID | PK, auto | Unique identifier |
| `arena_id` | UUID | FK(arenas.id), NOT NULL, indexed | Parent arena |
| `user_id` | UUID | FK(users.id), NOT NULL, indexed | Student participant |
| `total_points` | Numeric(10,2) | NOT NULL, default=0.0 | Performance score |

---

### arena_moderators (Association Table)

**Table:** `arena_moderators`

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `arena_id` | UUID | FK(arenas.id), PK | Arena reference |
| `user_id` | UUID | FK(users.id), PK | Moderator (teacher) reference |

**Business Rules:**
- Arena creator is automatically added as moderator
- Teachers can only moderate arenas for classes they teach

---

### ArenaStatus Enum

```python
class ArenaStatus(str, enum.Enum):
    DRAFT = "draft"           # Created, not scheduled
    SCHEDULED = "scheduled"   # Scheduled with start_time
    LIVE = "live"            # Currently active
    COMPLETED = "completed"   # Finished
```

**Status Transitions:**
- DRAFT → SCHEDULED (when start_time set)
- SCHEDULED → LIVE (manual or automatic at start_time)
- LIVE → COMPLETED (manual or automatic after duration)

---

## API Endpoints

### Base Path: `/api/v1/arenas`

All endpoints require `Teacher` role authentication.

---

### 1. List Arenas

**Endpoint:** `GET /api/v1/arenas`

**Purpose:** Fetch paginated list of arenas for teacher's classes

**Authentication:** Required (Teacher)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | Integer | No | 1 | Page number (≥1) |
| `page_size` | Integer | No | 20 | Items per page (1-100) |
| `class_id` | UUID | No | null | Filter by specific class |
| `status` | ArenaStatus | No | null | Filter by status |

**Response:** `PaginatedResponse<ArenaListRow>`

```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Beginner Debate: Climate change",
      "status": "scheduled",
      "class_id": "uuid",
      "class_name": "Class 5A",
      "start_time": "2026-03-16T09:30:00Z",
      "duration_minutes": 45
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 42,
    "total_pages": 3
  }
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not a teacher

**Business Logic:**
- Only returns arenas for classes the teacher teaches
- Results sorted by: `start_time DESC NULLSLAST`, then `created_at DESC`
- Teacher access enforced via `teacher_assignments` join

**Frontend Usage:**
- Dashboard scheduled arenas list
- Arena list page with filters
- Stats cards calculation (count by status)

---

### 2. Create Arena

**Endpoint:** `POST /api/v1/arenas`

**Purpose:** Create new arena challenge for teacher's class

**Authentication:** Required (Teacher)

**Request Body:** `ArenaCreate`

```json
{
  "class_id": "uuid",
  "title": "Debate Challenge: Climate Change",
  "description": "A structured debate on climate change impacts",
  "criteria": {
    "Pronunciation": 30,
    "Vocabulary": 40,
    "Fluency": 30
  },
  "rules": [
    "Participants must speak for at least two minutes",
    "No reading from notes allowed"
  ],
  "start_time": "2026-03-20T14:00:00Z",
  "duration_minutes": 45
}
```

**Field Validation:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `class_id` | UUID | Yes | Must be a class teacher teaches |
| `title` | String | Yes | Max 255 chars |
| `description` | String | No | Nullable |
| `criteria` | Dict<string, int> | Yes | Weights should sum to 100% (frontend validates) |
| `rules` | String[] | No | Array of rule strings |
| `start_time` | DateTime | No | ISO 8601 format |
| `duration_minutes` | Integer | No | Positive integer |

**Response:** `SuccessResponse<ArenaResponse>`

```json
{
  "success": true,
  "message": "Arena created successfully",
  "data": {
    "id": "uuid",
    "class_id": "uuid",
    "title": "Debate Challenge: Climate Change",
    "description": "A structured debate on climate change impacts",
    "status": "draft",
    "start_time": "2026-03-20T14:00:00Z",
    "duration_minutes": 45,
    "criteria": [
      {"name": "Pronunciation", "weight_percentage": 30},
      {"name": "Vocabulary", "weight_percentage": 40},
      {"name": "Fluency", "weight_percentage": 30}
    ],
    "rules": [
      "Participants must speak for at least two minutes",
      "No reading from notes allowed"
    ]
  }
}
```

**Status Codes:**
- `200 OK` - Arena created
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Teacher doesn't teach this class
- `422 Unprocessable Entity` - Validation error

**Business Logic:**
- Arena status initialized as `DRAFT`
- Teacher automatically added as moderator
- Criteria and rules stored as child records
- Transaction: all-or-nothing creation

**Frontend Usage:**
- "Create Arena Challenge" form submission
- Returns complete arena for immediate display/editing

---

### 3. Get Arena by ID

**Endpoint:** `GET /api/v1/arenas/{arena_id}`

**Purpose:** Fetch full arena details for preview/edit

**Authentication:** Required (Teacher)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `arena_id` | UUID | Arena unique identifier |

**Response:** `SuccessResponse<ArenaResponse>`

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "class_id": "uuid",
    "title": "Debate Challenge: Climate Change",
    "description": "A structured debate on climate change impacts",
    "status": "scheduled",
    "start_time": "2026-03-20T14:00:00Z",
    "duration_minutes": 45,
    "criteria": [
      {"name": "Pronunciation", "weight_percentage": 30},
      {"name": "Vocabulary", "weight_percentage": 40},
      {"name": "Fluency", "weight_percentage": 30}
    ],
    "rules": [
      "Participants must speak for at least two minutes",
      "No reading from notes allowed"
    ]
  }
}
```

**Status Codes:**
- `200 OK` - Arena found
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Teacher doesn't teach arena's class
- `404 Not Found` - Arena doesn't exist or no access

**Business Logic:**
- Teacher access enforced via `teacher_assignments` join
- Eager loads criteria and rules for complete response
- Returns null if arena not found or teacher lacks access

**Frontend Usage:**
- Arena preview modal
- Edit form initialization
- Moderate arena entry

---

### 4. Update Arena

**Endpoint:** `PATCH /api/v1/arenas/{arena_id}`

**Purpose:** Update arena details (partial update)

**Authentication:** Required (Teacher)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `arena_id` | UUID | Arena unique identifier |

**Request Body:** `ArenaUpdate` (all fields optional)

```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "status": "scheduled",
  "criteria": {
    "Pronunciation": 25,
    "Vocabulary": 45,
    "Fluency": 30
  },
  "rules": [
    "New rule 1",
    "New rule 2"
  ],
  "start_time": "2026-03-21T15:00:00Z",
  "duration_minutes": 60
}
```

**Field Validation:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | String | No | Max 255 chars |
| `description` | String | No | Nullable |
| `status` | ArenaStatus | No | Valid enum value |
| `criteria` | Dict<string, int> | No | If provided, replaces all criteria |
| `rules` | String[] | No | If provided, replaces all rules |
| `start_time` | DateTime | No | ISO 8601 format |
| `duration_minutes` | Integer | No | Positive integer |

**Response:** `SuccessResponse<ArenaResponse>`

```json
{
  "success": true,
  "message": "Arena updated successfully",
  "data": {
    // ... full ArenaResponse object
  }
}
```

**Status Codes:**
- `200 OK` - Arena updated
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Teacher doesn't teach arena's class
- `404 Not Found` - Arena doesn't exist or no access
- `422 Unprocessable Entity` - Validation error

**Business Logic:**
- Partial update: only provided fields modified
- Criteria/rules replacement: deletes existing and recreates (not merge)
- Teacher access enforced via `teacher_assignments` join
- Transaction: all-or-nothing update

**Frontend Usage:**
- Arena edit form submission
- Status transitions (draft → scheduled, scheduled → live)
- Quick updates from dashboard (e.g., change start time)

---

### 5. Admin Leaderboard (Cross-Arena Analytics)

**Endpoint:** `GET /api/v1/admin/leaderboard`

**Purpose:** School-wide arena performance leaderboard

**Authentication:** Required (Admin)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `timeframe` | Enum | No | "all" | Filter: "week" \| "month" \| "all" |

**Response:** (Schema to be defined - see admin endpoints)

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not an admin

**Frontend Usage:**
- Admin dashboard for school-wide arena insights
- Top performers and classes by arena points

**Note:** This is an existing endpoint documented here for completeness. Implementation details in `app/api/v1/endpoints/admin.py:leaderboard`

---

## Screen Specifications

### Screen 1: Arena Management Dashboard

**Figma Node:** `3967:6383`
**Route:** `/teacher/arena-management` (frontend)
**Purpose:** Main hub for arena overview and management

#### UI Components

##### Header Section
- **Title:** "Arena Management"
- **Subtitle:** "Manage class-mode speaking challenges"
- **Primary CTA:** "Create new challenge" button
  - Action: Navigate to Schedule Arena form
  - API: N/A (navigation only)

##### Stats Cards Row

Three summary cards displayed horizontally:

1. **Active Arenas**
   - Label: "Active Arena"
   - Value: Count of arenas with `status = LIVE`
   - Sub-label: "Live now"
   - Icon: Live indicator (pulsing dot)
   - **Data Source:** `GET /arenas?status=live` → count `meta.total`

2. **Upcoming Arenas**
   - Label: "Upcoming arena"
   - Value: Count of arenas with `status = SCHEDULED`
   - Icon: Calendar
   - **Data Source:** `GET /arenas?status=scheduled` → count `meta.total`

3. **Draft Arenas**
   - Label: "Drafts"
   - Value: Count of arenas with `status = DRAFT`
   - Icon: Document
   - **Data Source:** `GET /arenas?status=draft` → count `meta.total`

**Frontend Implementation:**
```javascript
// Fetch all three counts in parallel
const [active, upcoming, drafts] = await Promise.all([
  fetch('/api/v1/arenas?status=live&page_size=1'),
  fetch('/api/v1/arenas?status=scheduled&page_size=1'),
  fetch('/api/v1/arenas?status=draft&page_size=1'),
])
const stats = {
  active: active.meta.total,
  upcoming: upcoming.meta.total,
  drafts: drafts.meta.total,
}
```

##### Arena Performance Analytics Section

**Header:**
- Title: "Arena Performance Analytics"
- Subtitle: "Insight from past challenges and students engagement"
- Timeframe selector: Dropdown "Last 30 Days"
  - Options: Last 7 Days, Last 30 Days, Last 90 Days, All Time

**Participation Rate Chart:**
- Metric: 80% (example)
- Type: Bar chart with legend
- Legend: Present (green) / Absent (gray)
- **Data Source:** NOT YET IMPLEMENTED (see Gap Analysis)

**Top Challenges Bar Graph:**
- Shows top 2 challenge types with engagement percentage
- Example: "Debate 45%", "Role play 25%"
- Horizontal progress bars
- **Data Source:** NOT YET IMPLEMENTED (see Gap Analysis)

**Gap:** This section requires a new analytics endpoint (see Section 7: Gap Analysis)

##### Scheduled Arena List

**Header:** "Scheduled Arena"

**List Item Structure:** (Cards displayed vertically)

Each card contains:
- **Date/Time Badge:**
  - Top-left: "Today" or date (e.g., "Mar 16")
  - Time: "09:30 PM" or "AM"
- **Title:** Arena title (e.g., "Beginner Debate: Climate change")
- **Status Badge:**
  - "Live now" (green) if `status = LIVE`
  - "Scheduled" (blue) if `status = SCHEDULED`
- **Action Button:**
  - "Moderate" button if `status = LIVE`
    - Action: Open moderation interface (NOT YET IMPLEMENTED)
  - "Edit" button if `status = SCHEDULED` or `status = DRAFT`
    - Action: Navigate to edit form (`GET /arenas/{id}` → populate form)

**Data Source:**
```javascript
GET /api/v1/arenas?page=1&page_size=10
// Optionally filter by status for "Scheduled Arena" section:
GET /api/v1/arenas?status=scheduled&status=live&page=1&page_size=10
```

**Frontend Data Transformation:**
```javascript
// Format time display
const formatTime = (isoString) => {
  const date = new Date(isoString)
  const isToday = date.toDateString() === new Date().toDateString()
  return {
    dateLabel: isToday ? 'Today' : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    timeLabel: date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
  }
}
```

##### Quick Access Section

**Header:** "Quick Access"

Three navigation cards:
1. **Learning Room**
   - Icon: Book/learning icon
   - Action: Navigate to learning room (separate feature)
   - API: N/A (navigation only)

2. **Practice Room**
   - Icon: Microphone icon
   - Action: Navigate to practice room (separate feature)
   - API: N/A (navigation only)

3. **YouSpeak Challenge Pool**
   - Label: "Browse Catalog"
   - Icon: Grid/catalog icon
   - Action: Navigate to Challenge Pool (see Screen 3)
   - API: N/A (navigation only)

#### API Integration Summary

**On Page Load:**
1. Fetch stats for cards (3 parallel requests)
2. Fetch scheduled arenas list (1 request)
3. Fetch analytics data (NOT YET IMPLEMENTED)

**Total API Calls:** 4 (5 when analytics implemented)

---

### Screen 2: Schedule an Arena (Create/Edit Form)

**Figma Node:** `4008:8612`
**Route:** `/teacher/arena-management/create` or `/teacher/arena-management/edit/:id`
**Purpose:** Form to create new arena or edit existing

#### Form Structure

##### Header
- **Title:** "Create Arena Challenge" (or "Edit Arena Challenge")
- **Subtitle:** "Design a new speaking activity for your students, define the rules, format and criteria"

##### Section 1: Basic Information

**Fields:**

1. **Challenge Title**
   - Type: Text input
   - Required: Yes
   - Max length: 255 characters
   - Placeholder: "Enter challenge title"
   - API Field: `title`

2. **Description**
   - Type: Textarea (multiline)
   - Required: No
   - Placeholder: "Describe the challenge objectives and context"
   - API Field: `description`

3. **Associated Class(es)**
   - Type: Dropdown (single select currently, see Gap Analysis for multi-select)
   - Required: Yes
   - Options: List of classes the teacher teaches
   - Data Source: `GET /api/v1/classes` (teacher's classes)
   - API Field: `class_id`

**Note:** Figma shows three dropdown slots, suggesting multi-class support. Current backend supports single `class_id` only. See Gap Analysis.

##### Section 2: Rules and Criteria

**Judging Criteria** (Dynamic list with add/remove):

- **Structure:** List of criterion rows
- **Each Row Contains:**
  - **Criterion Name:** Text input (e.g., "Pronunciation")
  - **Weight %:** Number input (0-100)
  - **Remove Button:** Delete this criterion

- **Add Button:** "Add criterion" to insert new row
- **Validation:**
  - Total weights must sum to 100%
  - Frontend shows running total
  - Show error if sum ≠ 100% on submit

**Example Display:**
```
Pronunciation [_____] 30 %  [X]
Vocabulary    [_____] 40 %  [X]
Fluency       [_____] 30 %  [X]
                Total: 100%
```

**API Field:** `criteria` (Dict<string, int>)
```json
{
  "Pronunciation": 30,
  "Vocabulary": 40,
  "Fluency": 30
}
```

---

**General Rules** (Dynamic list with add/remove):

- **Structure:** List of rule text inputs
- **Each Row Contains:**
  - **Rule Text:** Textarea (multiline)
  - **Remove Button:** Delete this rule

- **Add Button:** "Add more rules" (see Figma node `4204:6295`)
- **No Validation:** Rules are optional

**Example Display:**
```
Rule 1: [Participants must speak for at least two minutes]  [X]
Rule 2: [No reading from notes allowed]                      [X]
[+ Add more rules]
```

**API Field:** `rules` (string[])
```json
[
  "Participants must speak for at least two minutes",
  "No reading from notes allowed"
]
```

##### Section 3: Scheduling (Optional)

**Fields:**

1. **Start Time**
   - Type: DateTime picker
   - Required: No
   - Format: ISO 8601 (e.g., "2026-03-20T14:00:00Z")
   - API Field: `start_time`

2. **Duration**
   - Type: Number input
   - Unit: Minutes
   - Required: No
   - API Field: `duration_minutes`

##### Section 4: Challenge Pool Option

**Save to YouSpeak Challenge Pool:**
- Type: Radio button or checkbox
- Label: "Making this challenge public allows other teachers to use it in their classes."
- **API Field:** NOT YET IMPLEMENTED (see Gap Analysis)

**Gap:** Backend does not have `is_public` or pool-related fields yet.

##### Form Actions

1. **Primary Button:** "Create Challenge" (or "Update Challenge")
   - Action: Submit form
   - API: `POST /api/v1/arenas` (create) or `PATCH /api/v1/arenas/{id}` (edit)
   - On Success: Redirect to dashboard or preview

2. **Secondary Button:** "Cancel" (implied)
   - Action: Discard changes and return to dashboard

#### Frontend Validation

**Pre-Submit Checks:**
1. Title is not empty
2. At least one class selected
3. At least one criterion defined
4. Criteria weights sum to exactly 100%
5. If start_time provided, it must be in the future

**Error Handling:**
- Display field-level errors inline
- Display API errors as toast/banner
- Specific error for 403 (teacher doesn't teach selected class)

#### API Integration

**Create Flow:**
```javascript
POST /api/v1/arenas
Body: {
  class_id, title, description,
  criteria, rules,
  start_time, duration_minutes
}
Response: SuccessResponse<ArenaResponse>
```

**Edit Flow:**
```javascript
// 1. Load existing arena
GET /api/v1/arenas/{id}
// 2. Populate form with response data
// 3. Submit updates
PATCH /api/v1/arenas/{id}
Body: { ...updated fields }
Response: SuccessResponse<ArenaResponse>
```

---

### Screen 3: Arena Challenge Pool

**Figma Node:** `4017:6276`
**Route:** `/teacher/arena-management/challenge-pool`
**Purpose:** Browse and select pre-made challenges from YouSpeak catalog

#### UI Components

##### Header
- **Title:** "YouSpeak Challenge Pool"
- **Subtitle:** "Browse pre-made challenges to use in your classes"

##### Filters/Search (Assumed)
- **Search Bar:** Text input to search challenge titles/descriptions
- **Filter Options:**
  - Challenge type (debate, role play, etc.)
  - Proficiency level (beginner, intermediate, advanced)
  - Duration range

##### Challenge Cards Grid

**Card Structure:**
- **Title:** Challenge title
- **Description:** Short description or preview
- **Metadata:**
  - Challenge type badge
  - Proficiency level
  - Average duration
  - Usage count (popularity indicator)
- **Action Button:** "Use this challenge"
  - Action: Clone challenge to teacher's arena with option to customize

#### API Integration

**Endpoints Required:** (NOT YET IMPLEMENTED)

1. **List Public Challenges**
   ```
   GET /api/v1/arenas/pool
   Query params: page, page_size, search, type, level
   Response: PaginatedResponse<ChallengePoolItem>
   ```

2. **Get Challenge Details**
   ```
   GET /api/v1/arenas/pool/{id}
   Response: SuccessResponse<ChallengePoolDetails>
   ```

3. **Clone from Pool**
   ```
   POST /api/v1/arenas/from-pool
   Body: { pool_challenge_id, class_id, customizations }
   Response: SuccessResponse<ArenaResponse>
   ```

**Gap:** This entire feature is not implemented in backend. See Gap Analysis Section 7.

---

### Screen 4: Arena Preview

**Figma Node:** `4018:6877`
**Route:** `/teacher/arena-management/preview/:id` or Modal overlay
**Purpose:** Display full arena details before editing or moderating

#### UI Components

##### Header
- **Title:** Arena title
- **Status Badge:** Visual indicator (draft/scheduled/live/completed)
- **Class Name:** Display associated class

##### Details Section

**Challenge Information:**
- **Description:** Full description text
- **Schedule:** Start time and duration (if set)
- **Status:** Current status with icon

**Judging Criteria List:**
- Display each criterion with weight percentage
- Example:
  ```
  Pronunciation: 30%
  Vocabulary: 40%
  Fluency: 30%
  ```

**Rules List:**
- Numbered or bulleted list of all rules
- Example:
  ```
  1. Participants must speak for at least two minutes
  2. No reading from notes allowed
  ```

##### Action Buttons

**Primary Actions (state-dependent):**

1. **If status = DRAFT:**
   - "Edit" button → Navigate to edit form
   - "Schedule" button → Quick schedule modal (set start_time)

2. **If status = SCHEDULED:**
   - "Edit" button → Navigate to edit form
   - "Start Now" button → Change status to LIVE

3. **If status = LIVE:**
   - "Moderate" button → Open moderation interface (NOT YET IMPLEMENTED)
   - "End Arena" button → Change status to COMPLETED

4. **If status = COMPLETED:**
   - "View Results" button → Show performance data (NOT YET IMPLEMENTED)
   - "Clone" button → Create new draft copy

**Secondary Actions:**
- "Delete" button (with confirmation)
- "Back" button → Return to dashboard

#### API Integration

**On Load:**
```javascript
GET /api/v1/arenas/{id}
Response: SuccessResponse<ArenaResponse>
```

**Actions:**
- Edit: Navigate with existing data
- Schedule/Start/End: `PATCH /api/v1/arenas/{id}` with status update
- Delete: `DELETE /api/v1/arenas/{id}` (NOT YET IMPLEMENTED - see Gap Analysis)

---

## Gap Analysis

### 1. Missing Endpoints

#### 1.1 Analytics Endpoint (Dashboard)

**Gap:** Arena Performance Analytics section has no data source

**Required Endpoint:**
```
GET /api/v1/arenas/analytics

Query Parameters:
- timeframe: "7d" | "30d" | "90d" | "all"
- class_id: UUID (optional filter)

Response:
{
  "participation_rate": {
    "percentage": 80,
    "present_count": 24,
    "absent_count": 6,
    "total_students": 30
  },
  "top_challenge_types": [
    { "type": "debate", "percentage": 45, "count": 12 },
    { "type": "role_play", "percentage": 25, "count": 7 }
  ],
  "total_arenas": 27,
  "total_participants": 120
}
```

**Priority:** Medium (dashboard displays placeholder until implemented)

---

#### 1.2 Challenge Pool Endpoints

**Gap:** Entire Challenge Pool feature is not implemented

**Required Endpoints:**

1. **List Pool Challenges**
   ```
   GET /api/v1/arenas/pool

   Query Parameters:
   - page, page_size: Pagination
   - search: Text search (title, description)
   - challenge_type: Filter by type
   - proficiency_level: Filter by level

   Response: PaginatedResponse<PoolChallengeListRow>
   ```

2. **Get Pool Challenge Details**
   ```
   GET /api/v1/arenas/pool/{pool_challenge_id}

   Response: SuccessResponse<PoolChallengeDetail>
   ```

3. **Publish Arena to Pool**
   ```
   POST /api/v1/arenas/{arena_id}/publish-to-pool

   Body: { is_public: true }

   Response: SuccessResponse<{ pool_challenge_id: UUID }>
   ```

4. **Clone from Pool**
   ```
   POST /api/v1/arenas/from-pool

   Body: {
     pool_challenge_id: UUID,
     class_id: UUID,
     title: string (optional override),
     description: string (optional override)
   }

   Response: SuccessResponse<ArenaResponse>
   ```

**Database Changes Required:**
- Add `is_public` boolean to `arenas` table
- Add `source_pool_challenge_id` UUID nullable to `arenas` (tracks clones)
- Add index on `is_public` for efficient pool queries
- Add `usage_count` integer to track popularity

**Priority:** Low (nice-to-have, can defer to later sprint)

---

#### 1.3 Delete Arena Endpoint

**Gap:** No delete endpoint exists

**Required Endpoint:**
```
DELETE /api/v1/arenas/{arena_id}

Response: SuccessResponse<null>

Business Rules:
- Cannot delete if status = LIVE
- Soft delete vs hard delete (TBD)
- Cascade deletes criteria, rules, performers
```

**Priority:** Medium (common CRUD operation)

---

#### 1.4 Moderation Interface Endpoints

**Gap:** "Moderate" action has no backend support

**Required Endpoints:**

1. **Get Live Arena Session**
   ```
   GET /api/v1/arenas/{arena_id}/session

   Response: {
     arena: ArenaResponse,
     active_performers: [
       { user_id, name, status: "speaking" | "waiting" | "completed" }
     ],
     queue: [ ... ]
   }
   ```

2. **Score Performer**
   ```
   POST /api/v1/arenas/{arena_id}/score

   Body: {
     performer_id: UUID,
     criteria_scores: {
       "Pronunciation": 8.5,
       "Vocabulary": 9.0,
       "Fluency": 7.5
     }
   }

   Response: SuccessResponse<{ total_points: Numeric }>
   ```

**Priority:** High (required for core functionality)

---

### 2. Missing Database Fields

#### 2.1 Challenge Pool Fields

**Table:** `arenas`

| Field | Type | Purpose |
|-------|------|---------|
| `is_public` | Boolean | Marks arena as available in challenge pool |
| `source_pool_challenge_id` | UUID nullable | Tracks if arena was cloned from pool |
| `usage_count` | Integer | Tracks popularity for pool sorting |

---

#### 2.2 Multi-Class Support

**Gap:** Figma shows multiple "Associated class(es)" dropdowns, suggesting multi-class arenas

**Current:** `arena.class_id` is single foreign key

**Option 1:** Keep single class (simplest)
**Option 2:** Add `arena_classes` join table for many-to-many

**Recommendation:** Defer multi-class to future version (v2). Current single-class model is simpler and covers 90% of use cases.

---

### 3. Frontend-Only Gaps

#### 3.1 Stats Card Aggregation

**Current API:** Client must make 3 separate requests to get counts

**Optimization Option:** Create summary endpoint
```
GET /api/v1/arenas/summary

Response: {
  draft_count: 3,
  scheduled_count: 5,
  live_count: 1,
  completed_count: 18
}
```

**Trade-off:**
- Pro: Single request for dashboard
- Con: Less flexible than query-based approach

**Recommendation:** Keep current approach (3 requests). Parallel fetching is fast, and counts are cached effectively.

---

### 4. Business Logic Gaps

#### 4.1 Automatic Status Transitions

**Gap:** No automatic status changes based on time

**Required:**
- SCHEDULED → LIVE when `start_time` reached
- LIVE → COMPLETED when `start_time + duration_minutes` passed

**Implementation Options:**
1. **Cron Job:** Scheduled task every 1 minute checks and updates statuses
2. **On-Demand:** Status computed dynamically in queries (virtual field)
3. **Webhook:** Client triggers status check on dashboard load

**Recommendation:** Option 1 (Cron Job) for reliability

---

#### 4.2 Criteria Weight Validation

**Gap:** Backend does not validate criteria weights sum to 100%

**Current:** Frontend validates, but backend accepts any values

**Recommendation:** Add backend validation in `ArenaCreate` and `ArenaUpdate` schemas:
```python
@field_validator('criteria')
def validate_criteria_weights(cls, v):
    if sum(v.values()) != 100:
        raise ValueError("Criteria weights must sum to 100%")
    return v
```

**Priority:** Medium (prevents data integrity issues if frontend validation bypassed)

---

### 5. Documentation Gaps

**Required:**
- OpenAPI/Swagger annotations for all endpoints
- Frontend integration guide with code examples
- Data flow diagrams (client → API → DB)

---

## Implementation Roadmap

### Phase 1: Core CRUD (Completed ✅)

**Status:** Implemented and tested

- [x] Arena data models (Arena, ArenaCriteria, ArenaRule, ArenaPerformer)
- [x] List arenas endpoint (GET /arenas)
- [x] Create arena endpoint (POST /arenas)
- [x] Get arena by ID endpoint (GET /arenas/{id})
- [x] Update arena endpoint (PATCH /arenas/{id})
- [x] Teacher authorization middleware
- [x] Integration tests

---

### Phase 2: Dashboard Enhancement (Next Sprint)

**Priority:** High
**Estimated Effort:** 3-5 days

**Tasks:**
1. Add DELETE endpoint for arenas
   - Implement soft delete (add `deleted_at` column)
   - Add cascade logic
   - Add integration test
   - Update frontend to handle deletion

2. Add backend criteria weight validation
   - Add Pydantic validator
   - Test error cases
   - Document in API schema

3. Implement automatic status transitions
   - Create background job (Celery or similar)
   - Job runs every 1 minute
   - Updates SCHEDULED → LIVE and LIVE → COMPLETED based on timestamps
   - Add logging for status changes

---

### Phase 3: Analytics (Sprint +1)

**Priority:** Medium
**Estimated Effort:** 5-7 days

**Tasks:**
1. Design analytics data model
   - Participation tracking (who joined, who didn't)
   - Challenge type taxonomy
   - Performance aggregations

2. Implement analytics endpoint
   - GET /arenas/analytics
   - Support timeframe filtering
   - Optimize queries for performance

3. Create database indexes
   - Index on (status, start_time) for time-based queries
   - Index on class_id for teacher filtering

4. Frontend integration
   - Connect dashboard analytics section
   - Add chart visualizations (Chart.js or similar)

---

### Phase 4: Live Moderation (Sprint +2)

**Priority:** High (core feature)
**Estimated Effort:** 10-14 days

**Tasks:**
1. Design moderation session model
   - WebSocket connection for real-time updates
   - Performer queue management
   - Turn tracking

2. Implement moderation endpoints
   - GET /arenas/{id}/session
   - POST /arenas/{id}/score
   - WebSocket subscriptions

3. Build scoring algorithm
   - Weighted average from criteria
   - Decimal precision handling
   - Leaderboard updates

4. Frontend moderation UI
   - Real-time performer list
   - Scoring interface
   - Timer and status indicators

---

### Phase 5: Challenge Pool (Sprint +3) (Optional)

**Priority:** Low (nice-to-have)
**Estimated Effort:** 7-10 days

**Tasks:**
1. Add database fields (is_public, source_pool_challenge_id, usage_count)
2. Create migration
3. Implement pool endpoints (list, get, publish, clone)
4. Add pool management UI
5. Add discovery/search functionality

---

## Appendix

### A. API Request/Response Examples

#### Example 1: Create Arena with Full Data

**Request:**
```http
POST /api/v1/arenas
Authorization: Bearer <teacher_jwt>
Content-Type: application/json

{
  "class_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "title": "Advanced Debate: Technology Ethics",
  "description": "A structured debate on ethical implications of AI technology. Students will be divided into pro and con teams.",
  "criteria": {
    "Argumentation": 35,
    "Pronunciation": 25,
    "Vocabulary": 25,
    "Rebuttal Quality": 15
  },
  "rules": [
    "Each participant must present opening arguments for 2 minutes",
    "Rebuttal phase is 1 minute per person",
    "No personal attacks or off-topic discussions",
    "Evidence-based arguments are encouraged"
  ],
  "start_time": "2026-03-20T15:00:00Z",
  "duration_minutes": 60
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "message": "Arena created successfully",
  "data": {
    "id": "a7f3c2b1-8e4d-4c89-b123-456789abcdef",
    "class_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "title": "Advanced Debate: Technology Ethics",
    "description": "A structured debate on ethical implications of AI technology. Students will be divided into pro and con teams.",
    "status": "draft",
    "start_time": "2026-03-20T15:00:00Z",
    "duration_minutes": 60,
    "criteria": [
      { "name": "Argumentation", "weight_percentage": 35 },
      { "name": "Pronunciation", "weight_percentage": 25 },
      { "name": "Vocabulary", "weight_percentage": 25 },
      { "name": "Rebuttal Quality", "weight_percentage": 15 }
    ],
    "rules": [
      "Each participant must present opening arguments for 2 minutes",
      "Rebuttal phase is 1 minute per person",
      "No personal attacks or off-topic discussions",
      "Evidence-based arguments are encouraged"
    ]
  }
}
```

---

#### Example 2: List Arenas with Filters

**Request:**
```http
GET /api/v1/arenas?page=1&page_size=5&status=scheduled&class_id=f47ac10b-58cc-4372-a567-0e02b2c3d479
Authorization: Bearer <teacher_jwt>
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": [
    {
      "id": "a7f3c2b1-8e4d-4c89-b123-456789abcdef",
      "title": "Advanced Debate: Technology Ethics",
      "status": "scheduled",
      "class_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "class_name": "Grade 12 English Advanced",
      "start_time": "2026-03-20T15:00:00Z",
      "duration_minutes": 60
    },
    {
      "id": "b8e4d3c2-9f5e-5d90-c234-567890bcdefg",
      "title": "Role Play: Job Interview",
      "status": "scheduled",
      "class_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "class_name": "Grade 12 English Advanced",
      "start_time": "2026-03-22T10:00:00Z",
      "duration_minutes": 45
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 5,
    "total": 2,
    "total_pages": 1
  }
}
```

---

#### Example 3: Update Arena Status to Live

**Request:**
```http
PATCH /api/v1/arenas/a7f3c2b1-8e4d-4c89-b123-456789abcdef
Authorization: Bearer <teacher_jwt>
Content-Type: application/json

{
  "status": "live"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "message": "Arena updated successfully",
  "data": {
    "id": "a7f3c2b1-8e4d-4c89-b123-456789abcdef",
    "class_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "title": "Advanced Debate: Technology Ethics",
    "description": "A structured debate on ethical implications of AI technology...",
    "status": "live",
    "start_time": "2026-03-20T15:00:00Z",
    "duration_minutes": 60,
    "criteria": [ /* ... */ ],
    "rules": [ /* ... */ ]
  }
}
```

---

### B. Frontend Integration Checklist

**Dashboard Implementation:**
- [ ] Fetch and display stats cards (3 parallel API calls)
- [ ] Render scheduled arenas list with status badges
- [ ] Implement date/time formatting utilities
- [ ] Add navigation to create, edit, preview routes
- [ ] Handle "Moderate" action (stub until backend ready)
- [ ] Add placeholder for analytics section
- [ ] Implement quick access navigation cards

**Create/Edit Form Implementation:**
- [ ] Build dynamic criteria list (add/remove rows)
- [ ] Build dynamic rules list (add/remove rows)
- [ ] Add real-time weight total calculator
- [ ] Implement form validation (frontend + display API errors)
- [ ] Add datetime picker for start_time
- [ ] Fetch teacher's classes for dropdown
- [ ] Handle create (POST) and edit (PATCH) submissions
- [ ] Add success/error toast notifications

**Preview Modal/Page Implementation:**
- [ ] Fetch and display full arena details
- [ ] Implement state-dependent action buttons
- [ ] Add confirmation dialog for destructive actions
- [ ] Handle status transitions (schedule, start, end)

**General:**
- [ ] Set up API client with auth headers (JWT)
- [ ] Implement error boundary for API failures
- [ ] Add loading states for all async operations
- [ ] Implement optimistic UI updates where appropriate
- [ ] Add analytics tracking for user actions

---

### C. Testing Strategy

**Unit Tests:**
- [ ] ArenaService methods (create, update, get, list)
- [ ] Authorization logic (teacher teaches class)
- [ ] Criteria weight validation
- [ ] Status transition logic

**Integration Tests:**
- [x] POST /arenas (create arena)
- [x] GET /arenas (list with filters)
- [x] GET /arenas/{id} (get by ID)
- [x] PATCH /arenas/{id} (update arena)
- [ ] DELETE /arenas/{id} (when implemented)
- [ ] GET /arenas/analytics (when implemented)

**E2E Tests:**
- [ ] Complete flow: Create arena → Edit → Schedule → Preview → Start Live
- [ ] Dashboard loads with correct stats
- [ ] Teacher cannot access another teacher's arenas (403 tests)

---

### D. Security Considerations

1. **Authorization:**
   - All endpoints enforce teacher role
   - Teachers can only access arenas for classes they teach
   - Joins on `teacher_assignments` table prevent privilege escalation

2. **Input Validation:**
   - Pydantic schemas validate all request bodies
   - UUID format validation prevents injection
   - Max length constraints on text fields

3. **Rate Limiting:**
   - Consider adding rate limits to creation endpoints (prevent spam)

4. **Data Privacy:**
   - Arena data scoped to school
   - No cross-school data leakage
   - Participant scores visible only to class teachers

---

### E. Performance Optimization

**Database Indexes:**
- [x] `arenas.class_id` (existing)
- [x] `arenas.status` (existing)
- [ ] `arenas.(status, start_time)` composite (for scheduled queries)
- [ ] `arena_criteria.arena_id` (existing)
- [ ] `arena_rules.arena_id` (existing)

**Query Optimization:**
- Use `selectinload` for eager loading criteria/rules (already implemented)
- Pagination for list endpoints (already implemented)
- Consider caching stats counts (5-minute TTL)

**Caching Strategy:**
- Redis cache for teacher's class list (changes infrequently)
- Cache stats counts with short TTL
- Invalidate arena cache on create/update/delete

---

## Changelog

**v1.0 (2026-03-15):**
- Initial PRD creation
- Documented all Figma screens
- Mapped existing endpoints
- Identified gaps and implementation roadmap
- Added comprehensive examples and integration guides
