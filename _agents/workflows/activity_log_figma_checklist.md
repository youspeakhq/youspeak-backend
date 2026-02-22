# Activity Log – Figma → Backend Alignment

Use this when checking Activity Log screens in Figma (via **Figma MCP Bridge**) to confirm or adjust the backend.

## Figma references (Activity Log)

| Screen / modal | Node ID | URL |
|----------------|---------|-----|
| Activity Log (main) | `3542-4610` | [Figma node 3542-4610](https://www.figma.com/design/fE7qXuaAyJzPA2Tnglg58h?node-id=3542-4610) |
| (variant 2) | `3831-5687` | [Figma node 3831-5687](https://www.figma.com/design/fE7qXuaAyJzPA2Tnglg58h?node-id=3831-5687) |
| (variant 3) | `4028-8311` | [Figma node 4028-8311](https://www.figma.com/design/fE7qXuaAyJzPA2Tnglg58h?node-id=4028-8311) |

**File key:** `fE7qXuaAyJzPA2Tnglg58h`

---

## How to get design data (Figma Bridge)

1. Open the Figma file above.
2. In Figma, **select** the frame(s) for the Activity Log (e.g. the main list and/or the “add activity” modal). You can multi-select the three nodes if they’re on the same page.
3. Run the **Figma MCP Bridge** plugin (Plugins → Figma MCP Bridge).
4. In Cursor, ask the agent to “check Activity Log from Figma” or “get design context for Activity Log”. The agent will call `get_design_context` (and optionally `get_metadata` / `get_screenshot`) and use the **current selection**.
5. Use the checklist below to compare Figma with the backend.

**If the plugin shows "Selection: 0 node(s)":** the Bridge has nothing to send. Select the Activity Log frame(s) in the Layers panel or canvas first (e.g. node `3542-4610`), then retry.

---

## Figma design (extracted 2026-02-22)

From **Frame 2942** (Activity Summary / Activity Log card) and selected nodes:

- **Titles:** "Activity Summary" on the card; "Activity Log" / "View Activity Log" elsewhere.
- **Row layout (per entry):**
  - **Icon:** 48×48 rounded box, color by type: purple `#f4e5ff`, blue `#e0f2fe`.
  - **Description:** One line, 14px Space Grotesk, `#3d3d3d` (e.g. "John Doe submitted \"unit 3 essay\"", "You uploaded a new resource, \"Grammar guide PDF\"", "Class 5B just finished 'French: Greetings Basics' with an avg score of 88%.").
  - **Timestamp:** 12px Space Grotesk, `#8a8a8a`, format like "09-12-25, 9:30am".
- **"see more"** link (purple `#4b0081`) → full Activity Log page.
- **Activity types in design:** submission, resource upload, class/session completion (with score).

Backend alignment: `description` + `created_at` + `performer_name` match the row. Frontend can format `created_at` as MM-DD-YY, 9:30am and map `action_type` to icon color.

---

## What to extract from Figma

### 1. List / table (main Activity Log)

- **Column headers or labels**  
  e.g. Date, Time, Action, Performed by, Target/Link.
- **Row content**  
  What each row shows (single line of text vs multiple fields).
- **Sort**  
  Default sort (e.g. newest first) and whether sorting is by date only or by other fields.
- **Filters**  
  Any dropdowns or chips (e.g. “All”, “Students”, “Classes”, “Teachers”) and whether they map to our `action_type` or something else.
- **Pagination**  
  “Load more” vs page numbers vs infinite scroll (backend already supports `page` + `page_size`).

### 2. “Add activity” / create modal (if present)

- **Required fields**  
  e.g. Action type (dropdown?), Description (text?), optional target.
- **Optional fields**  
  e.g. Link to class/student, custom message.
- **Labels and placeholders**  
  To align with `ActivityLogCreate` and any future validation messages.

### 3. Detail / drill-down (if present)

- **What’s shown when you click a row**  
  Only `description` + `created_at` + performer, or extra metadata (e.g. `target_entity_type` / `target_entity_id` for deep links). Backend already returns these in `ActivityLogOut`.

---

## Current backend (for comparison)

### GET `/admin/activity`

- **Response:** Paginated list of `ActivityLogOut`.
- **Query params:** `page`, `page_size`, `action_type` (optional filter).
- **Fields per entry:**
  - `id`, `action_type`, `description`
  - `performed_by_user_id`, `performer_name`
  - `target_entity_type`, `target_entity_id`
  - `created_at`

### POST `/admin/activity`

- **Body:** `ActivityLogCreate`: `action_type`, `description`, optional `target_entity_type`, `target_entity_id`, `metadata`.
- **Response:** Single `ActivityLogOut` (the created entry).

### Action types (enum)

`student_registered`, `student_removed`, `class_created`, `class_archived`, `teacher_invited`, `teacher_joined`, `curriculum_published`, `arena_scheduled`, `arena_completed`, `other`.

---

## After you have Figma data

1. **Filters**  
   If Figma uses different filter categories, either:
   - map them to existing `action_type` values, or
   - add new enum values / query params and update the API.
2. **List columns**  
   If Figma shows more or fewer columns, add or hide fields in `ActivityLogOut` (or document that the frontend derives display from existing fields).
3. **Create modal**  
   If the “add activity” modal has different required/optional fields, update `ActivityLogCreate` and validation.
4. **Date range**  
   If the design has “From / To” date filters, add optional `from_date` / `to_date` to GET and use them in `ActivityService.list_activity`.

Once the Bridge returns data, run this checklist and adjust the backend (and this doc) so the API matches the Figma Activity Log screens.
