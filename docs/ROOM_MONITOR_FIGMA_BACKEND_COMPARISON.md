# Room Monitor – Figma vs Backend Comparison

**Source:** Figma file **"Indiigoo Labs _You Speak_ AI language assistant"**, page **Websites**, frame **Room Monitor** (node `3543:5489`). Fetched via Figma MCP: `get_design_context` (depth 5), `get_node` on frames `3546:5915` (cards row) and `3852:6703` (Class Performance Summary).

---

## 1. Figma screen structure (summary)

| Section | Figma content | Notes |
|--------|----------------|-------|
| **Page title** | "Room Monitor" | — |
| **Tabs** | "Learning room" (selected), "Practice room" | Filter by session type |
| **Top row (3 cards)** | **KPI cards**, not class cards: (1) Total Learning Sessions – 200, (2) Active Students – 35, (3) Avg. Session Duration – 12 mins. Each has "This Week" dropdown and "see more". | Aggregate stats |
| **Middle left** | "Recent Activity Timeline" + "see more" | Timeline of recent activity |
| **Middle right** | "Proficiency Growth Curve" + "see more" (chart: months Jan–Dec, levels A1–B2, "Current" dot) | Chart data |
| **Bottom** | **Class Performance Summary** + "see all" | Table (see below) |

---

## 2. Class Performance Summary table (Figma)

**Columns:** Class Name | Module Progress | Avg. Quiz Score | Time Spent | Last Activity | (action)

**Example rows (from Figma):**
- Grade 10 - Spanish → 85% (Mod 12) | 88% | 12h 30m / student | View Report
- Grade 9 - French → 62% (Mod 8) | 74% | 8h 15m / student | View Report
- Grade 11 - Mandarin → 94% (Mod 15) | 91% | 15h 45m / student | View Report
- Grade 8 - German → 40% (Mod 5) | 65% | 4h 10m / student | View Report

So the design expects **per-class metrics**: class name, module progress (e.g. 85% and current module), avg quiz score %, time spent per student, last activity, and "View Report".

---

## 3. Backend today (recap)

| Endpoint | Returns |
|----------|--------|
| `GET /api/v1/my-classes/monitor` | List of **RoomMonitorCard**: one per class → `class_id`, `class_name`, `student_count`, `active_session`. |
| `GET /api/v1/my-classes/{class_id}/monitor` | **RoomMonitorResponse**: same card fields + `performance_summary` with `recent_sessions_count` and `recent_sessions` (list of learning sessions, up to 5). |
| `GET /api/v1/my-classes/{class_id}/sessions` | List of learning sessions (for "see all" / recent activity). |
| `GET /api/v1/my-classes/{class_id}/roster` | Roster (students + roles). |

**RoomMonitorCard** has: `class_id`, `class_name`, `student_count`, `active_session` (session type, started_at, status).  
**ClassPerformanceSummary** has: `recent_sessions_count`, `recent_sessions` (session list). No module progress, quiz score, time spent, or last activity.

---

## 4. Gap analysis

### 4.1 Top row: three KPI cards (Figma)

| Figma card | Backend | Gap |
|------------|--------|-----|
| Total Learning Sessions (e.g. 200, "This Week") | No aggregate. We have per-class sessions only. | **Missing:** endpoint or query for total learning sessions (optionally filtered by timeframe e.g. this week). |
| Active Students (e.g. 35, "This Week") | No aggregate. We have roster per class. | **Missing:** endpoint or query for "active students" count (definition TBD: e.g. students with at least one session in period). |
| Avg. Session Duration (e.g. 12 mins) | Sessions have `started_at` and `ended_at` but no precomputed average. | **Missing:** endpoint or field for average session duration (e.g. for teacher’s classes, optional timeframe). |

**Conclusion:** Backend does not expose the three dashboard KPIs. Frontend can either (a) compute from existing data (e.g. fetch all sessions and aggregate in the client), or (b) we add a small **dashboard stats** endpoint (e.g. `GET /my-classes/monitor/stats?timeframe=week`) returning `total_sessions`, `active_students`, `avg_session_duration_minutes`.

---

### 4.2 Tabs: "Learning room" / "Practice room"

Backend already has `session_type`: `learning` | `practice`. Frontend can filter by `session_type` when displaying sessions or when calling a future stats endpoint. **No backend change required** if filtering is client-side.

---

### 4.3 Recent Activity Timeline

Backend has `recent_sessions` in `RoomMonitorResponse.performance_summary` and `GET /my-classes/{class_id}/sessions`. That can drive a "Recent Activity" timeline (sessions as events). If the design expects **cross-class** recent activity, we’d need either (a) frontend to aggregate from multiple classes, or (b) an endpoint that returns recent sessions across the teacher’s classes. **Partial coverage;** possible small extension for cross-class recent activity.

---

### 4.4 Proficiency Growth Curve

Chart shows progression over time (months) and levels (A1–B2). Backend has no proficiency-over-time or growth-curve API. If we need to serve this from the backend, it would require new models/aggregates (e.g. student or class proficiency snapshots). **Gap** for any backend-served growth curve.

---

### 4.5 Class Performance Summary table (Figma)

| Column / need | Backend | Gap |
|---------------|--------|-----|
| Class name | ✅ `class_name` on RoomMonitorCard / RoomMonitorResponse | OK |
| Module Progress (e.g. 85%, Mod 12) | ❌ Not in backend | **Missing:** module progress per class (e.g. % and current module). Depends on curriculum/module model. |
| Avg. Quiz Score | ❌ Not in backend | **Missing:** per-class average quiz/assessment score. Depends on assessment/quiz data. |
| Time Spent (e.g. 12h 30m / student) | ❌ Not in backend | **Missing:** per-class time spent per student (e.g. from sessions or activity). |
| Last Activity | ❌ Not in backend | **Missing:** last activity datetime per class (e.g. last session end or last student activity). |
| View Report | N/A (link/action) | Frontend can link to class detail or report route. |

**Conclusion:** The **Class Performance Summary** in Figma is a table of **classes with metrics**. The backend currently exposes class list + recent sessions only. To support the table as designed we need one or more of:

- A **class summary** or **class stats** response that includes, per class: `module_progress` (and optionally current module), `avg_quiz_score`, `time_spent_per_student`, `last_activity`.
- Or separate endpoints/fields that the frontend can combine (e.g. module progress from curriculum, quiz score from assessments, time from sessions).

---

## 5. Summary table

| Figma element | Backend support | Action |
|--------------|-----------------|--------|
| Page title "Room Monitor" | N/A | Frontend |
| Tabs Learning / Practice | `session_type` exists | Filter in frontend |
| KPI: Total Learning Sessions | ✅ `GET /my-classes/monitor/stats` | Implemented |
| KPI: Active Students | ✅ `GET /my-classes/monitor/stats` | Implemented |
| KPI: Avg. Session Duration | ✅ `GET /my-classes/monitor/stats` | Implemented |
| Recent Activity Timeline | ✅ Sessions list (per class) | Use sessions; optional cross-class endpoint |
| Proficiency Growth Curve | ❌ | New data if backend must serve chart |
| Class Performance Summary table | ✅ `GET /my-classes/monitor/summary` | Implemented (time_spent, last_activity, avg_quiz_score; module_progress stubbed null) |

---

## 6. Recommended next steps

1. **Dashboard KPIs:** Add `GET /api/v1/my-classes/monitor/stats?timeframe=week` (or similar) returning `total_sessions`, `active_students`, `avg_session_duration_minutes` for the teacher’s classes (and optional timeframe). If product agrees, implement and document in [ROOM_MONITOR_API.md](ROOM_MONITOR_API.md).
2. **Class Performance Summary table:** Define with product which metrics are MVP (e.g. module progress vs quiz score vs time spent). Then add either:
   - a **class summary** payload (e.g. on `GET /my-classes/monitor` or a new `GET /my-classes/monitor/summary`) with per-class metrics, or
   - reuse/extend existing class + sessions + roster endpoints and add new aggregates (module progress, quiz average, time spent, last activity) where data exists.
3. **Proficiency Growth Curve:** Defer until we have a clear source of truth (e.g. proficiency snapshots or assessments) and a product decision to serve it from the backend.
4. Keep [ROOM_MONITOR_API.md](ROOM_MONITOR_API.md) and this comparison in sync when adding or changing endpoints.
