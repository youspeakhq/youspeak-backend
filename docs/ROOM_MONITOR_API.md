# Room Monitor – API for Frontend

This document describes the **Room Monitor** backend endpoints and data shapes so the frontend can consume them. The design intent is aligned with the Figma Room Monitor frame (header with tabs, row of class cards, Class Performance Summary with “see all”).

**Figma:** Room Monitor frame (node `3543:5489`). See [ROOM_MONITOR_FIGMA_BACKEND_COMPARISON.md](ROOM_MONITOR_FIGMA_BACKEND_COMPARISON.md) for full comparison and gaps.
---

## Base URL and auth

- **Base path:** `/api/v1/my-classes`
- **Auth:** All endpoints require a **teacher** JWT (`Authorization: Bearer <token>`).
- **Response envelope:** Success responses use `{ "success": true, "data": ..., "message": "..." }`. Errors use standard HTTP status and `detail`.

---

## Endpoints summary

| Purpose | Method | Path | Response |
|--------|--------|------|----------|
| **KPI stats** (Total Sessions, Active Students, Avg. Duration) | GET | `/my-classes/monitor/stats?timeframe=week` | `RoomMonitorStats` |
| **Class Performance Summary table** | GET | `/my-classes/monitor/summary` | `List[ClassPerformanceSummaryRow]` |
| List room monitor cards (dashboard row) | GET | `/my-classes/monitor` | `List[RoomMonitorCard]` |
| Room monitor detail for one class | GET | `/my-classes/{class_id}/monitor` | `RoomMonitorResponse` |
| List learning sessions for a class | GET | `/my-classes/{class_id}/sessions` | `List[LearningSessionOut]` |
| Start a session | POST | `/my-classes/{class_id}/sessions` | `LearningSessionOut` |
| End a session | PATCH | `/my-classes/{class_id}/sessions/{session_id}` | `{}` |
| Class roster (students + roles) | GET | `/my-classes/{class_id}/roster` | roster list |
| List teacher’s classes | GET | `/my-classes` | `List[ClassResponse]` |

---

## 1. Room monitor stats (KPI cards)

**GET** `/api/v1/my-classes/monitor/stats?timeframe=week`

Returns aggregate KPIs for the teacher's classes (Figma: Total Learning Sessions, Active Students, Avg. Session Duration).  
**Query:** `timeframe` = `week` | `month` | `all` (default `week`).

**Response `data`:** **RoomMonitorStats**

```ts
interface RoomMonitorStats {
  total_sessions: number;
  active_students: number;
  avg_session_duration_minutes: number | null;
}
```

---

## 2. Class Performance Summary table

**GET** `/api/v1/my-classes/monitor/summary`

Returns one row per class for the Class Performance Summary table (Figma: Class Name, Module Progress, Avg. Quiz Score, Time Spent, Last Activity).

**Response `data`:** array of **ClassPerformanceSummaryRow**

```ts
interface ClassPerformanceSummaryRow {
  class_id: string;
  class_name: string;
  student_count: number;
  module_progress_pct: number | null;   // optional; null until module progress is implemented
  module_progress_label: string | null;
  avg_quiz_score_pct: number | null;
  time_spent_minutes_per_student: number | null;
  last_activity_at: string | null;     // ISO datetime
  active_session: LearningSessionOut | null;
}
```

---

## 3. List room monitor cards (dashboard)

**GET** `/api/v1/my-classes/monitor`

Returns one card per class the teacher teaches (Figma: row of class cards).

**Response `data`:** array of **RoomMonitorCard**

```ts
interface RoomMonitorCard {
  class_id: string;       // UUID
  class_name: string;
  student_count: number;
  active_session: LearningSessionOut | null;
}

interface LearningSessionOut {
  id: string;             // UUID
  class_id: string;
  started_by_user_id: string | null;
  session_type: "learning" | "practice";
  started_at: string;     // ISO datetime
  ended_at: string | null;
  status: "in_progress" | "completed";
}
```

Use for: dashboard row of cards; each card can show class name, student count, and whether there’s an active session (and link to `/my-classes/{class_id}/monitor`).

---

## 4. Room monitor detail for one class

**GET** `/api/v1/my-classes/{class_id}/monitor`

Returns the single-class room monitor view: card data plus Class Performance Summary (Figma: detail + summary section with “see all”).

**Response `data`:** **RoomMonitorResponse**

```ts
interface RoomMonitorResponse {
  class_id: string;
  class_name: string;
  student_count: number;
  active_session: LearningSessionOut | null;
  performance_summary: {
    recent_sessions_count: number;
    recent_sessions: LearningSessionOut[];
  } | null;
}
```

- **performance_summary.recent_sessions**: up to 5 most recent sessions (any status). “See all” can link to `/my-classes/{class_id}/sessions`.

---

## 5. Learning sessions (list / start / end)

**GET** `/api/v1/my-classes/{class_id}/sessions?limit=50`

List learning sessions for the class (most recent first). Default `limit=50`, max 100.

**Response `data`:** array of **LearningSessionOut** (same shape as above).

---

**POST** `/api/v1/my-classes/{class_id}/sessions`

Start a learning session. Body:

```json
{ "session_type": "learning" }
```
or `"practice"`.

- Only one active session per class at a time. If one is already in progress, returns 400.

**Response `data`:** single **LearningSessionOut** (the new session).

---

**PATCH** `/api/v1/my-classes/{class_id}/sessions/{session_id}`

End the given in-progress session. No body. Returns `data: {}` on success.

---

## 6. Class roster

**GET** `/api/v1/my-classes/{class_id}/roster`

List students in the class with roles (for roster display in room monitor or elsewhere).

**Response `data`:** array of roster entries:

```ts
interface RosterEntry {
  id: string;             // user UUID
  first_name: string;
  last_name: string;
  email: string;
  role: "student" | "class_monitor" | "time_keeper";
  joined_at: string;      // ISO datetime
  profile_picture_url: string | null;
}
```

---

## 7. List teacher’s classes

**GET** `/api/v1/my-classes`

Returns all classes assigned to the teacher (**ClassResponse**). Use for navigation, tabs, or class switcher if needed alongside the monitor.

---

## Data schema alignment (backend)

| Figma / UI concept | Backend source |
|--------------------|----------------|
| Row of class cards (one per class) | `GET /my-classes/monitor` → `RoomMonitorCard[]` (Figma top row is 3 KPI cards; see comparison doc) |
| Single class card (name, student count, active session) | `RoomMonitorCard` / `RoomMonitorResponse` |
| “Class Performance Summary” + recent sessions | `RoomMonitorResponse.performance_summary` |
| “See all” sessions | `GET /my-classes/{class_id}/sessions` |
| Start/end session | `POST` / `PATCH` on `.../sessions` |
| Roster (students + roles) | `GET /my-classes/{class_id}/roster` |

---

## Gaps vs Figma (see comparison doc)

- **Top row (3 KPI cards):** Total Learning Sessions, Active Students, Avg. Session Duration. Backend has no aggregate stats endpoint.
- **Class Performance Summary table:** Figma has Module Progress, Avg. Quiz Score, Time Spent, Last Activity. Backend exposes only class name and recent sessions.
- **Proficiency Growth Curve:** No backend data yet.
- **Tabs Learning room / Practice room:** Use `session_type`; filter client-side or in a future stats API.

See ROOM_MONITOR_FIGMA_BACKEND_COMPARISON.md for recommended next steps.
