# Arena Management – Figma → Backend Alignment

**Context: Teacher console.** Arena management endpoints are for the authenticated **teacher** only. They operate on arenas for classes the teacher teaches. Admin leaderboard (existing) shows arena performance school-wide.

**Figma source:** File **"Indiigoo Labs _You Speak_ AI language assistant"**, page **Websites**, section **Arena management** (node `3967:6382`). Fetched via Figma MCP: `get_design_context` (depth 1), `get_node` on frames below.

---

## 1. Figma screens (all Arena management)

| Screen / Frame | Node ID | Purpose |
|----------------|---------|--------|
| **ArenaManagement** | `3967:6383` | Main dashboard: stats cards, Arena Performance Analytics, Scheduled Arena list, Quick Access. |
| **Schedule an Arena** | `4008:8612` | Create Arena Challenge form (Basic Information, Rules and Criteria, Create Challenge). |
| **Arena challenge pool** | `4017:6276` | Browse pre-made challenges (YouSpeak Challenge pool). |
| **Arena Preview** | `4018:6877` | Preview of an arena (design detail). |
| **Learning room** | `4031:6547` | Learning room entry (Quick Access target). |
| **Add more rules** | `4204:6295` | “Add more rules” component. |
| **Time frame dropdown** | `4008:8603` | Timeframe selector (e.g. Last 30 Days). |

---

## 2. Data fields from Figma (by screen)

### ArenaManagement (`3967:6383`)

- **Header:** “Arena Management”, “Manage class-mode speaking challenges”, CTA **“Create new challenge”**.
- **Stats cards:** “1 Active Arena” (Live now), “3 Upcoming arena”, “1 Drafts”.
- **Arena Performance Analytics:** Title “Arena Performance Analytics”, subtitle “Insight from past challenges and students engagement”, **timeframe dropdown** “Last 30 Days”.
  - **Participation rate:** 80%, Avg. Attendance, legend Present / Absent.
  - **Top 2 challenges:** e.g. Debate 45%, Role play 25% (progress bars).
- **Scheduled Arena:** List of cards; each card has:
  - Date/time (e.g. “Today”, “09:30”, “PM”).
  - Title (e.g. “Beginner Debate: Climate change”).
  - Status: “Live now” or “Scheduled”.
  - Actions: **“Moderate”** (for live) or **“Edit”**.
- **Quick Access:** Learning room, Practice room, **YouSpeak Challenge pool** (“Browse Catalog”).

### Schedule an Arena / Create Arena Challenge (`4008:8612`)

- **Header:** “Create Arena Challenge”, “Design a new speaking activity for your students, define the rules, format and criteria”.
- **Basic Information:**
  - **Challenge Title** (input).
  - **Description** (textarea).
  - **Associated class(es)** – dropdown “Select class...” (Figma shows three dropdowns; UI suggests multi-select or multiple class slots).
- **Rules and Criteria:**
  - **Judging criteria:** name + weight %; example “Pronunciation” 30%, “Vocabulary” 40%, “Fluency” 30% (Total: 100%).
  - **General rules:** multi-line text; example “Participants must speak for at least two minutes …”, “Add more rules” button.
- **Option:** “Save to YouSpeak challenge pool” (radio) – “Making this challenge public allows other teachers to use it in their classes.”
- **Primary CTA:** “Create Challenge”.

---

## 3. Backend data model (existing)

- **Arena:** `class_id`, `title`, `description`, `status` (DRAFT | SCHEDULED | LIVE | COMPLETED), `start_time`, `duration_minutes`; relations: criteria, rules, performers, moderators.
- **ArenaCriteria:** `arena_id`, `name`, `weight_percentage`.
- **ArenaRule:** `arena_id`, `description`.
- **ArenaPerformer:** `arena_id`, `user_id`, `total_points`.
- **arena_moderators:** arena_id, user_id.

---

## 4. Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/arenas` | List arenas (query: class_id, status, page, page_size). Supports dashboard list and filters. | Teacher |
| POST | `/arenas` | Create arena (body: class_id, title, description, criteria, rules, start_time, duration_minutes). | Teacher |
| GET | `/arenas/{id}` | Get arena by id (for Edit / Moderate). | Teacher |
| PATCH | `/arenas/{id}` | Update arena (title, description, status, criteria, rules, schedule). | Teacher |
| GET | `/admin/leaderboard` | Top students and classes by arena points (query: timeframe=week \| month \| all). | Admin |

---

## 5. Alignment and gaps

| Figma | Backend | Notes |
|-------|---------|--------|
| Stats (Active / Upcoming / Drafts) | GET /arenas with status filter | Client can aggregate counts from list or we add a summary endpoint later. |
| Arena Performance Analytics (participation, top challenges) | Not yet | Possible future: analytics endpoint for teacher (participation rate, top arenas by engagement). |
| Timeframe “Last 30 Days” | Leaderboard has week/month/all | Analytics timeframe could align with same enum. |
| Scheduled list (date, time, title, status, Moderate/Edit) | GET /arenas + GET /arenas/{id}, PATCH | List row has start_time, status, class_name; Moderate = open live arena (no dedicated endpoint yet). |
| Create: Title, Description, Associated class(es) | class_id, title, description | **Implemented.** Figma shows multiple “Associated class(es)” – backend currently single class per arena; multi-class could be a later extension. |
| Judging criteria (name + %) | criteria: Dict[str, int] | **Implemented.** |
| General rules + “Add more rules” | rules: List[str] | **Implemented.** |
| “Save to YouSpeak challenge pool” | Not in model | **Gap:** No `is_public` or “challenge pool” flag; would require schema + listing for pool. |
| Learning room / Practice room / Challenge pool (Browse Catalog) | Out of scope | Navigation / separate features; no arena-specific endpoints required. |

---

## 6. Summary

- **Figma screens:** All Arena management frames are identified and listed with node IDs; main screens (ArenaManagement, Schedule an Arena) were fetched and field list is above.
- **Backend:** Teacher-scoped CRUD (list, create, get, update) and admin leaderboard are implemented and aligned with Figma create/list and status flow.
- **Optional gaps:** (1) Analytics summary (participation rate, top challenges) for teacher; (2) multi-class per arena; (3) “Save to YouSpeak challenge pool” (public/pool flag and pool listing).
