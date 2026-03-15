# Arena Management System - Complete Technical Specification

**Document Version:** 1.0
**Last Updated:** 2026-03-15
**Status:** Ready for Implementation

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [API Specifications](#api-specifications)
5. [WebSocket Protocol](#websocket-protocol)
6. [Authentication & Authorization](#authentication--authorization)
7. [AI Co-Judge Integration](#ai-co-judge-integration)
8. [Report Generation](#report-generation)
9. [Error Handling](#error-handling)
10. [Testing Strategy](#testing-strategy)
11. [Implementation Phases](#implementation-phases)

---

## System Overview

### Purpose

The Arena Management System enables teachers to run live speaking competitions (arenas) where students perform, receive real-time feedback, AI-powered insights, and final evaluations.

### Key Features

- **Flexible Session Configuration**: Competitive vs. collaborative modes, teacher-only vs. hybrid judging
- **Student Selection Logic**: Manual selection, randomized, or hybrid approaches
- **Real-Time Live Sessions**: WebSocket-powered real-time speaking tracking, reactions, engagement scores
- **Waiting Room & Admission Control**: Students join via code/QR, teacher admits from queue
- **AI Co-Judge**: AWS Bedrock integration for scoring suggestions
- **Comprehensive Evaluation**: Teacher judgment, scoring, remarks, and result publishing
- **Report Generation**: PDF summaries and CSV exports

### Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **Database**: PostgreSQL with SQLAlchemy async ORM
- **Real-Time**: WebSockets + Redis Pub/Sub
- **AI**: AWS Bedrock (Claude 3.5 Sonnet)
- **PDF Generation**: WeasyPrint + Jinja2
- **Authentication**: JWT bearer tokens

---

## Architecture

### High-Level Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Frontend  │◄───────►│   FastAPI   │◄───────►│ PostgreSQL  │
│  (Teacher)  │         │   Backend   │         │  Database   │
└─────────────┘         └─────────────┘         └─────────────┘
                              │ │
                              │ └──────────────┐
                              ▼                 ▼
┌─────────────┐         ┌─────────────┐   ┌─────────────┐
│   Frontend  │◄───────►│    Redis    │   │ AWS Bedrock │
│  (Student)  │  WS     │   Pub/Sub   │   │ (AI Judge)  │
└─────────────┘         └─────────────┘   └─────────────┘
```

### WebSocket Scaling Strategy

**Problem**: Single-server WebSocket connections don't scale horizontally

**Solution**: Redis Pub/Sub message broker

```
┌──────────────┐                              ┌──────────────┐
│ Backend      │                              │ Backend      │
│ Server 1     │                              │ Server 2     │
│              │                              │              │
│ WebSocket ◄──┼──┐                      ┌───┼──► WebSocket │
│ Connections  │  │                      │   │   Connections│
└──────────────┘  │                      │   └──────────────┘
                  │                      │
                  ▼                      ▼
            ┌─────────────────────────────────┐
            │   Redis Pub/Sub Channel         │
            │   arena:{arena_id}:live         │
            └─────────────────────────────────┘
```

**Flow:**
1. Client connects to any backend server via load balancer
2. Server maintains local WebSocket connection
3. When event occurs, server publishes to Redis channel
4. All servers subscribed to channel receive message
5. Each server broadcasts to its local WebSocket connections

**Benefits:**
- Horizontal scaling: Add more backend servers without code changes
- Sub-50ms latency for real-time updates
- Automatic failover if a server dies

---

## Database Schema

### New Tables

#### 1. Arena Teams (for Collaborative Mode)

```sql
CREATE TABLE arena_teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arena_id UUID NOT NULL REFERENCES arenas(id) ON DELETE CASCADE,
    team_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(arena_id, team_name)
);

CREATE INDEX idx_arena_teams_arena ON arena_teams(arena_id);
```

#### 2. Arena Team Members

```sql
CREATE TABLE arena_team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES arena_teams(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50),  -- 'leader', 'member'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, student_id)
);

CREATE INDEX idx_team_members_team ON arena_team_members(team_id);
CREATE INDEX idx_team_members_student ON arena_team_members(student_id);
```

#### 3. Arena Waiting Room

```sql
CREATE TABLE arena_waiting_room (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arena_id UUID NOT NULL REFERENCES arenas(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'admitted' | 'rejected'
    admitted_at TIMESTAMP,
    admitted_by UUID REFERENCES users(id),
    rejection_reason TEXT,
    UNIQUE(arena_id, student_id)
);

CREATE INDEX idx_waiting_room_arena_status ON arena_waiting_room(arena_id, status);
CREATE INDEX idx_waiting_room_student ON arena_waiting_room(student_id);
```

**Business Logic:**
- Students can only join once per arena (UNIQUE constraint)
- When admitted, `status='admitted'`, `admitted_at=NOW()`, `admitted_by=teacher_id`
- When rejected, `status='rejected'`, `rejection_reason` optional

#### 4. Arena Participants (Live Session)

```sql
CREATE TABLE arena_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arena_id UUID NOT NULL REFERENCES arenas(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'participant',  -- 'participant' | 'audience'
    team_id UUID REFERENCES arena_teams(id),
    is_speaking BOOLEAN DEFAULT FALSE,
    speaking_start_time TIMESTAMP,
    total_speaking_duration_seconds INTEGER DEFAULT 0,
    engagement_score NUMERIC(5,2) DEFAULT 0.00,  -- 0.00 to 100.00
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(arena_id, student_id)
);

CREATE INDEX idx_participants_arena ON arena_participants(arena_id);
CREATE INDEX idx_participants_speaking ON arena_participants(arena_id, is_speaking);
CREATE INDEX idx_participants_team ON arena_participants(team_id);
```

**Business Logic:**
- Created when student is admitted from waiting room
- `is_speaking=true` when participant starts speaking, `speaking_start_time=NOW()`
- `is_speaking=false` when stops, update `total_speaking_duration_seconds`
- `engagement_score` calculated based on speaking time + reactions received
- Deleted or archived after session ends

#### 5. Arena Reactions

```sql
CREATE TABLE arena_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arena_id UUID NOT NULL REFERENCES arenas(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    target_participant_id UUID REFERENCES arena_participants(id),  -- Who received reaction
    reaction_type VARCHAR(20) NOT NULL,  -- 'heart' | 'clap' | 'laugh'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reactions_arena ON arena_reactions(arena_id, reaction_type);
CREATE INDEX idx_reactions_participant ON arena_reactions(target_participant_id);
CREATE INDEX idx_reactions_timestamp ON arena_reactions(arena_id, timestamp DESC);
```

**Business Logic:**
- Rate limit: 5 reactions per 10 seconds per user (enforced in Redis)
- Aggregated in real-time for engagement calculations
- Persisted for final evaluation reporting

#### 6. Arena Evaluations

```sql
CREATE TABLE arena_evaluations (
    arena_id UUID PRIMARY KEY REFERENCES arenas(id) ON DELETE CASCADE,
    teacher_judgment TEXT,  -- Overall assessment
    teacher_remark TEXT,  -- Additional comments
    final_average_score NUMERIC(5,2),  -- Calculated from all performers
    total_participants INTEGER,
    total_reaction_count INTEGER,
    total_reaction_percentage NUMERIC(5,2),  -- Engagement metric
    results_published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Logic:**
- Created via `POST /arenas/{id}/evaluate`
- `results_published=false` until `POST /arenas/{id}/publish`
- Students cannot see results until `results_published=true`

#### 7. Arena AI Insights

```sql
CREATE TABLE arena_ai_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arena_id UUID NOT NULL REFERENCES arenas(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES arena_participants(id),
    insight_text TEXT,  -- AI-generated rationale
    suggested_scores JSONB,  -- {"criterion_name": 7.5, ...}
    confidence_score NUMERIC(3,2),  -- 0.00 to 1.00
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_insights_arena ON arena_ai_insights(arena_id);
CREATE INDEX idx_ai_insights_participant ON arena_ai_insights(participant_id);
```

**Business Logic:**
- Generated after participant's speaking turn (if AI enabled)
- Stored but not directly visible to students
- Teacher sees insights in scoring UI
- Included in final PDF reports

### Modified Tables

#### Arenas Table (Add Columns)

```sql
ALTER TABLE arenas ADD COLUMN arena_mode VARCHAR(20);  -- 'competitive' | 'collaborative'
ALTER TABLE arenas ADD COLUMN judging_mode VARCHAR(20);  -- 'teacher_only' | 'hybrid'
ALTER TABLE arenas ADD COLUMN ai_co_judge_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE arenas ADD COLUMN student_selection_mode VARCHAR(20);  -- 'manual' | 'hybrid' | 'randomize'
ALTER TABLE arenas ADD COLUMN join_code VARCHAR(20) UNIQUE;
ALTER TABLE arenas ADD COLUMN qr_code_url TEXT;
ALTER TABLE arenas ADD COLUMN session_state VARCHAR(20) DEFAULT 'not_started';  -- 'not_started' | 'initialized' | 'live' | 'completed'
ALTER TABLE arenas ADD COLUMN team_size INTEGER;  -- For collaborative mode (2-5)
ALTER TABLE arenas ADD COLUMN join_code_expires_at TIMESTAMP;

CREATE INDEX idx_arenas_join_code ON arenas(join_code) WHERE join_code IS NOT NULL;
CREATE INDEX idx_arenas_session_state ON arenas(session_state);
```

---

## API Specifications

### Phase 1: Session Configuration

#### 1. Search Students

```http
GET /api/v1/students/search?name={name}&class_id={class_id}
Authorization: Bearer {teacher_jwt}
```

**Query Parameters:**
- `name` (string, optional): Search by student name (partial match, case-insensitive)
- `class_id` (UUID, required): Class to search within

**Response 200:**
```json
{
  "students": [
    {
      "id": "uuid",
      "name": "John Doe",
      "avatar_url": "https://...",
      "status": "active"
    }
  ],
  "total": 21,
  "page": 1,
  "page_size": 20
}
```

**Authorization:** Teacher must teach the specified class

---

#### 2. Initialize Arena Session

```http
POST /api/v1/arenas/{arena_id}/initialize
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "arena_mode": "competitive",  // "competitive" | "collaborative"
  "judging_mode": "teacher_only",  // "teacher_only" | "hybrid"
  "ai_co_judge_enabled": false,
  "student_selection_mode": "manual",  // "manual" | "hybrid" | "randomize"
  "selected_student_ids": ["uuid1", "uuid2"],  // For manual/hybrid
  "team_size": 2  // Required if arena_mode="collaborative"
}
```

**Response 200:**
```json
{
  "session_id": "uuid",
  "status": "initialized",
  "participants": [
    {
      "id": "uuid",
      "name": "John Doe",
      "role": "participant",
      "team_id": null
    }
  ],
  "configuration": {
    "arena_mode": "competitive",
    "judging_mode": "teacher_only",
    "ai_co_judge_enabled": false
  }
}
```

**Side Effects:**
- Updates `arenas.session_state` to `"initialized"`
- Creates entries in `arena_participants` table
- If `collaborative` mode and `team_size` provided, creates teams

**Validation:**
- `arena_mode` required
- `judging_mode` required
- If `arena_mode="collaborative"`, `team_size` (2-5) required
- If `student_selection_mode="manual"`, `selected_student_ids` required

---

#### 3. Randomize Student Selection

```http
POST /api/v1/arenas/{arena_id}/students/randomize
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "class_id": "uuid",
  "participant_count": 4
}
```

**Response 200:**
```json
{
  "selected_students": [
    {
      "id": "uuid",
      "name": "John Doe",
      "avatar_url": "https://..."
    }
  ]
}
```

**Business Logic:**
- Query students in `class_id` with `status='active'`
- Randomly select `participant_count` students (using `random.sample`)
- Return selection (does NOT save to database yet - that happens in `/initialize`)

---

#### 4. Hybrid Student Selection

```http
POST /api/v1/arenas/{arena_id}/students/hybrid
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "manual_selections": ["uuid1", "uuid2"],
  "randomize_count": 2,
  "class_id": "uuid"
}
```

**Response 200:**
```json
{
  "final_participants": [
    {
      "id": "uuid",
      "name": "John Doe",
      "avatar_url": "https://...",
      "selection_method": "manual"
    },
    {
      "id": "uuid2",
      "name": "Jane Smith",
      "avatar_url": "https://...",
      "selection_method": "random"
    }
  ]
}
```

**Business Logic:**
1. Take all `manual_selections` students
2. Query remaining students in `class_id` (excluding manual selections)
3. Randomly select `randomize_count` from remaining
4. Return combined list

---

### Phase 2: Waiting Room & Admission

#### 5. Generate Join Code

```http
POST /api/v1/arenas/{arena_id}/join-code
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "join_code": "A7B2C9",  // 6-digit alphanumeric
  "qr_code_url": "https://storage.../arena_{arena_id}_qr.png",
  "expires_at": "2026-03-15T14:30:00Z"
}
```

**Side Effects:**
- Generates unique 6-digit code (retry logic if collision)
- Generates QR code image (using `qrcode` library)
- Uploads QR code to storage (S3 or local)
- Updates `arenas.join_code`, `arenas.qr_code_url`, `arenas.join_code_expires_at`
- Sets expiration to `now() + arena.duration_minutes + 15 minutes`

**Code Generation Logic:**
```python
import random
import string

def generate_join_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))
```

---

#### 6. Student Join Waiting Room

```http
POST /api/v1/arenas/{arena_id}/waiting-room/join
Authorization: Bearer {student_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "join_code": "A7B2C9"
}
```

**Response 200:**
```json
{
  "waiting_room_id": "uuid",
  "status": "pending",
  "position_in_queue": 3,
  "estimated_wait_time_seconds": null
}
```

**Response 400:**
```json
{
  "error": {
    "code": "INVALID_JOIN_CODE",
    "message": "Join code is invalid or expired"
  }
}
```

**Response 409:**
```json
{
  "error": {
    "code": "ALREADY_JOINED",
    "message": "You are already in the waiting room"
  }
}
```

**Validation:**
- Join code must match `arenas.join_code`
- Join code must not be expired (`join_code_expires_at > now()`)
- Student cannot join same arena twice (UNIQUE constraint)
- Arena must be in `initialized` or `live` state

---

#### 7. List Waiting Room Students

```http
GET /api/v1/arenas/{arena_id}/waiting-room
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "pending_students": [
    {
      "entry_id": "uuid",
      "student_id": "uuid",
      "student_name": "John Doe",
      "avatar_url": "https://...",
      "entry_timestamp": "2026-03-15T14:25:00Z",
      "status": "pending"
    }
  ],
  "total_pending": 5,
  "total_admitted": 12,
  "total_rejected": 2
}
```

**Query:**
```sql
SELECT id, student_id, entry_timestamp, status
FROM arena_waiting_room
WHERE arena_id = $1 AND status = 'pending'
ORDER BY entry_timestamp ASC;
```

---

#### 8. Admit Student from Waiting Room

```http
POST /api/v1/arenas/{arena_id}/waiting-room/{entry_id}/admit
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "success": true,
  "participant_id": "uuid"
}
```

**Side Effects:**
1. Update `arena_waiting_room.status='admitted'`, `admitted_at=NOW()`, `admitted_by=teacher_id`
2. Create entry in `arena_participants` with `role='participant'` or `'audience'` (based on arena capacity)
3. Broadcast WebSocket event: `{"event": "participant_joined", "data": {...}}`

**Transaction:**
```python
async with db.begin():
    # Update waiting room
    await db.execute(
        update(ArenaWaitingRoom)
        .where(ArenaWaitingRoom.id == entry_id)
        .values(status='admitted', admitted_at=func.now(), admitted_by=teacher_id)
    )
    # Create participant
    participant = ArenaParticipant(arena_id=arena_id, student_id=student_id, role='participant')
    db.add(participant)
    await db.commit()
    # Broadcast via Redis
    await connection_manager.broadcast(arena_id, {"event": "participant_joined", "data": participant_dict})
```

---

#### 9. Reject Student from Waiting Room

```http
POST /api/v1/arenas/{arena_id}/waiting-room/{entry_id}/reject
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body (optional):**
```json
{
  "reason": "Arena is full"
}
```

**Response 200:**
```json
{
  "success": true
}
```

**Side Effects:**
- Update `arena_waiting_room.status='rejected'`, `rejection_reason=reason`
- Send notification to student (if notification system exists)

---

### Phase 3: Live Session

#### 10. Start Arena Session

```http
POST /api/v1/arenas/{arena_id}/start
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "status": "live",
  "start_time": "2026-03-15T14:30:00Z",
  "session_state": {
    "participants": [...],
    "current_speakers": [],
    "elapsed_seconds": 0
  }
}
```

**Side Effects:**
- Update `arenas.status='LIVE'`, `session_state='live'`
- Broadcast WebSocket: `{"event": "session_started", "data": {...}}`
- Start session timer (tracked in Redis)

---

#### 11. WebSocket Live Session

```
WS /api/v1/arenas/{arena_id}/live?token={jwt}
```

See [WebSocket Protocol](#websocket-protocol) section for detailed event specifications.

---

#### 12. Get Arena Session State

```http
GET /api/v1/arenas/{arena_id}/session
Authorization: Bearer {jwt}
```

**Response 200:**
```json
{
  "arena_id": "uuid",
  "status": "live",
  "session_state": "live",
  "participants": [
    {
      "id": "uuid",
      "name": "John Doe",
      "role": "participant",
      "is_speaking": false,
      "total_speaking_duration_seconds": 45,
      "engagement_score": 78.5
    }
  ],
  "current_speakers": ["uuid1"],
  "telemetry": {
    "elapsed_seconds": 120,
    "remaining_seconds": 300,
    "total_reactions": 45
  }
}
```

**Use Case:** Page refresh during live session, reconnection after network interruption

---

#### 13. Score Participant

```http
POST /api/v1/arenas/{arena_id}/participants/{participant_id}/score
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "criteria_scores": {
    "Clarity": 8.5,
    "Confidence": 7.0,
    "Grammar": 9.0,
    "Engagement": 8.0
  }
}
```

**Response 200:**
```json
{
  "participant_id": "uuid",
  "criteria_scores": {
    "Clarity": 8.5,
    "Confidence": 7.0,
    "Grammar": 9.0,
    "Engagement": 8.0
  },
  "calculated_total": 81.5,  // Weighted average based on criteria weights
  "rank": 2
}
```

**Business Logic:**
```python
# Calculate weighted total
total = 0
for criterion_name, score in criteria_scores.items():
    criterion = await get_criterion_by_name(arena_id, criterion_name)
    total += score * (criterion.weight_percentage / 100)

# Update arena_performers table
await db.execute(
    update(ArenaPerformer)
    .where(ArenaPerformer.id == participant_id)
    .values(criteria_scores=criteria_scores, final_score=total)
)
```

---

#### 14. Get Live Analytics

```http
GET /api/v1/arenas/{arena_id}/analytics/live
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "speaking_progress_percentage": 65.5,
  "engagement_percentage": 78.2,
  "reaction_counts": {
    "heart": 23,
    "clap": 45,
    "laugh": 12
  },
  "active_speakers": ["uuid1", "uuid2"],
  "total_participants": 15,
  "average_speaking_time_seconds": 45
}
```

**Calculations:**
- `speaking_progress_percentage`: (sum of all speaking times) / (total participants * target time per participant)
- `engagement_percentage`: (participants with >0 reactions) / (total participants) * 100

---

#### 15. End Arena Session

```http
POST /api/v1/arenas/{arena_id}/end
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "status": "completed",
  "end_time": "2026-03-15T15:00:00Z",
  "final_participant_count": 15,
  "total_speaking_time_seconds": 675
}
```

**Side Effects:**
1. Update `arenas.status='COMPLETED'`, `session_state='completed'`
2. Broadcast WebSocket: `{"event": "session_ended", "data": {...}}`
3. Close all WebSocket connections for this arena (graceful shutdown)
4. Archive `arena_participants` data to `arena_performers` for final evaluation

---

### Phase 4: Evaluation & Publishing

#### 16. Submit Final Evaluation

```http
POST /api/v1/arenas/{arena_id}/evaluate
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "teacher_judgment": "Overall excellent performance by all participants...",
  "teacher_remark": "Special recognition to top 3 performers...",
  "final_scores_confirmed": true
}
```

**Response 200:**
```json
{
  "evaluation_id": "uuid",
  "final_average_score": 78.5,
  "total_participants": 15,
  "total_reaction_count": 80,
  "total_reaction_percentage": 85.3,
  "results_published": false
}
```

**Business Logic:**
```python
# Calculate aggregates
final_avg = await db.execute(
    select(func.avg(ArenaPerformer.final_score)).where(ArenaPerformer.arena_id == arena_id)
).scalar()

total_participants = await db.execute(
    select(func.count(ArenaPerformer.id)).where(ArenaPerformer.arena_id == arena_id)
).scalar()

total_reactions = await db.execute(
    select(func.count(ArenaReaction.id)).where(ArenaReaction.arena_id == arena_id)
).scalar()

# Create evaluation record
evaluation = ArenaEvaluation(
    arena_id=arena_id,
    teacher_judgment=data.teacher_judgment,
    teacher_remark=data.teacher_remark,
    final_average_score=final_avg,
    total_participants=total_participants,
    total_reaction_count=total_reactions,
    total_reaction_percentage=(total_reactions / total_participants) if total_participants > 0 else 0
)
```

---

#### 17. Publish Results

```http
POST /api/v1/arenas/{arena_id}/publish
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "results_published": true,
  "published_at": "2026-03-15T15:30:00Z",
  "student_notification_sent": true
}
```

**Side Effects:**
- Update `arena_evaluations.results_published=true`, `published_at=NOW()`
- Students can now see their scores and teacher judgment
- Trigger notification system (email/push) to all participants

---

#### 18. Download PDF Summary Report

```http
GET /api/v1/arenas/{arena_id}/reports/summary.pdf
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="arena_{title}_summary.pdf"`

**PDF Content:**
- Arena details (title, date, mode, judging)
- Participant rankings table
- Criteria score breakdown
- Teacher judgment and remarks
- AI insights (if enabled)
- Reaction statistics

---

#### 19. Download CSV Participants Data

```http
GET /api/v1/arenas/{arena_id}/reports/participants.csv
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="arena_{title}_participants.csv"`

**CSV Columns:**
```
Participant Name,Student ID,Final Score,Rank,Speaking Time (seconds),Engagement Score,Criteria Scores (JSON)
John Doe,uuid1,81.5,2,45,78.5,"{""Clarity"": 8.5, ""Confidence"": 7.0}"
```

---

### Phase 5: Collaborative Mode & History

#### 20. Create Teams

```http
POST /api/v1/arenas/{arena_id}/teams
Authorization: Bearer {teacher_jwt}
Content-Type: application/json
```

**Request Body:**
```json
{
  "team_name": "Team Alpha",
  "member_ids": ["uuid1", "uuid2", "uuid3"],
  "role_assignments": {
    "uuid1": "leader",
    "uuid2": "member",
    "uuid3": "member"
  }
}
```

**Response 200:**
```json
{
  "team_id": "uuid",
  "team_name": "Team Alpha",
  "members": [
    {
      "student_id": "uuid1",
      "name": "John Doe",
      "role": "leader"
    }
  ]
}
```

---

#### 21. List Teams

```http
GET /api/v1/arenas/{arena_id}/teams
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "teams": [
    {
      "team_id": "uuid",
      "team_name": "Team Alpha",
      "member_count": 3,
      "members": [...]
    }
  ]
}
```

---

#### 22. Arena History

```http
GET /api/v1/arenas/history?class_id={uuid}&start_date={date}&end_date={date}&page=1&page_size=20
Authorization: Bearer {teacher_jwt}
```

**Response 200:**
```json
{
  "arenas": [
    {
      "id": "uuid",
      "title": "Debate Challenge #1",
      "class_name": "Class 10A",
      "start_time": "2026-03-10T14:00:00Z",
      "status": "completed",
      "participant_count": 15,
      "average_score": 78.5
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20
}
```

---

## WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket(`wss://api.youspeak.com/api/v1/arenas/${arenaId}/live?token=${jwt}`);
```

### Message Format

All messages use JSON format:

```json
{
  "event": "string",
  "data": {},
  "timestamp": "ISO8601",
  "sender_id": "uuid"
}
```

### Client → Server Events

#### 1. Speaking Started

```json
{
  "event": "speaking_started",
  "data": {}
}
```

**Server Action:**
- Update `arena_participants.is_speaking=true`, `speaking_start_time=NOW()`
- Broadcast to all clients: `speaking_update`

---

#### 2. Speaking Stopped

```json
{
  "event": "speaking_stopped",
  "data": {}
}
```

**Server Action:**
- Calculate duration: `NOW() - speaking_start_time`
- Update `arena_participants.is_speaking=false`, `total_speaking_duration_seconds += duration`
- Broadcast to all clients: `speaking_update`

---

#### 3. Reaction Sent

```json
{
  "event": "reaction_sent",
  "data": {
    "reaction_type": "heart",  // "heart" | "clap" | "laugh"
    "target_participant_id": "uuid"
  }
}
```

**Server Action:**
- Rate limit check (Redis: 5 per 10 seconds per user)
- Insert into `arena_reactions` table
- Increment engagement score for target participant
- Broadcast to all clients: `reaction_broadcast`

---

#### 4. Audio Control

```json
{
  "event": "audio_muted",
  "data": {}
}

{
  "event": "audio_unmuted",
  "data": {}
}
```

**Server Action:**
- Update participant state (if tracked)
- Optionally broadcast to other clients

---

### Server → Client Events

#### 1. Session State (Initial Snapshot)

Sent immediately after connection established.

```json
{
  "event": "session_state",
  "data": {
    "arena_id": "uuid",
    "status": "live",
    "participants": [
      {
        "id": "uuid",
        "name": "John Doe",
        "role": "participant",
        "is_speaking": false,
        "total_speaking_duration_seconds": 45,
        "engagement_score": 78.5
      }
    ],
    "current_speakers": ["uuid1"],
    "elapsed_seconds": 120,
    "remaining_seconds": 300,
    "reaction_counts": {
      "heart": 23,
      "clap": 45,
      "laugh": 12
    }
  },
  "timestamp": "2026-03-15T14:32:00Z"
}
```

---

#### 2. Speaking Update

```json
{
  "event": "speaking_update",
  "data": {
    "participant_id": "uuid",
    "is_speaking": true,
    "speaking_start_time": "2026-03-15T14:32:05Z",
    "total_speaking_duration_seconds": 45
  },
  "timestamp": "2026-03-15T14:32:05Z",
  "sender_id": "uuid"
}
```

---

#### 3. Engagement Update

```json
{
  "event": "engagement_update",
  "data": {
    "participant_id": "uuid",
    "engagement_score": 82.3,
    "reaction_count": 15
  },
  "timestamp": "2026-03-15T14:33:00Z"
}
```

---

#### 4. Reaction Broadcast

```json
{
  "event": "reaction_broadcast",
  "data": {
    "user_id": "uuid",
    "user_name": "Jane Smith",
    "reaction_type": "heart",
    "target_participant_id": "uuid",
    "total_count": 24
  },
  "timestamp": "2026-03-15T14:33:15Z",
  "sender_id": "uuid"
}
```

---

#### 5. AI Insight (Moderators Only)

Sent to Redis channel `arena:{arena_id}:admin` (not main channel).

```json
{
  "event": "ai_insight",
  "data": {
    "participant_id": "uuid",
    "participant_name": "John Doe",
    "insight_text": "Strong clarity and confident delivery. Minor grammar improvements needed.",
    "suggested_scores": {
      "Clarity": 8.5,
      "Confidence": 8.0,
      "Grammar": 6.5,
      "Engagement": 7.5
    },
    "confidence_score": 0.87
  },
  "timestamp": "2026-03-15T14:34:00Z"
}
```

---

#### 6. Timer Update

Sent every 10 seconds.

```json
{
  "event": "timer_update",
  "data": {
    "elapsed_seconds": 130,
    "remaining_seconds": 290
  },
  "timestamp": "2026-03-15T14:32:10Z"
}
```

---

#### 7. Participant Joined/Left

```json
{
  "event": "participant_joined",
  "data": {
    "participant_id": "uuid",
    "name": "New Student",
    "role": "participant"
  },
  "timestamp": "2026-03-15T14:35:00Z"
}

{
  "event": "participant_left",
  "data": {
    "participant_id": "uuid",
    "name": "John Doe",
    "reason": "disconnected"
  },
  "timestamp": "2026-03-15T14:40:00Z"
}
```

---

#### 8. Session Ended

```json
{
  "event": "session_ended",
  "data": {
    "end_time": "2026-03-15T15:00:00Z",
    "reason": "teacher_ended",
    "final_participant_count": 15
  },
  "timestamp": "2026-03-15T15:00:00Z"
}
```

**After this event, server closes all WebSocket connections gracefully.**

---

## Authentication & Authorization

### JWT Token Requirements

All endpoints require JWT bearer token in `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Payload

```json
{
  "sub": "user_id",
  "role": "teacher" | "student" | "admin",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### Authorization Matrix

See [Architecture - Authentication & Authorization](#authentication--authorization) section in main document.

### Dependency Injection Pattern

```python
# app/api/deps.py

async def require_teacher(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    payload = verify_jwt(token)
    if payload.get("role") != "teacher":
        raise HTTPException(403, "Requires teacher role")
    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

async def require_arena_moderator(arena_id: UUID, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user = await require_teacher(token, db)
    result = await db.execute(
        select(arena_moderators).where(
            arena_moderators.c.arena_id == arena_id,
            arena_moderators.c.user_id == user.id
        )
    )
    if not result.first():
        raise HTTPException(403, "Not authorized - must be arena moderator")
    return user
```

---

## AI Co-Judge Integration

### AWS Bedrock Configuration

```python
# app/config.py
AWS_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
AI_JUDGE_TIMEOUT_SECONDS = 5
AI_JUDGE_MAX_TOKENS = 500
```

### Service Implementation

```python
# app/services/ai_judge_service.py
import boto3
import json
import asyncio
from typing import Optional, Dict, List

class AIJudgeService:
    def __init__(self):
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=AWS_REGION
        )

    async def generate_scoring_insight(
        self,
        arena_id: UUID,
        participant_id: UUID,
        transcript: str,
        criteria: List[ArenaCriteria]
    ) -> Optional[Dict]:
        """
        Generate AI scoring suggestion based on performance transcript.

        Returns None if timeout/error occurs (graceful degradation).
        """
        criteria_desc = "\n".join([
            f"- {c.name} ({c.weight_percentage}%): {c.description or ''}"
            for c in criteria
        ])

        prompt = f"""You are an AI co-judge for a speaking arena competition. Analyze this performance and provide scoring suggestions.

Judging Criteria:
{criteria_desc}

Performance Transcript:
{transcript}

Provide:
1. Score suggestions (0-10) for each criterion
2. Brief rationale (1-2 sentences max)
3. Overall confidence (0.0-1.0)

Respond ONLY with valid JSON in this exact format:
{{
  "criteria_scores": {{
    "Clarity": 8.5,
    "Confidence": 7.0
  }},
  "rationale": "Strong delivery with minor hesitation.",
  "confidence": 0.85
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.bedrock.invoke_model,
                    modelId=BEDROCK_MODEL_ID,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": AI_JUDGE_MAX_TOKENS,
                        "messages": [{"role": "user", "content": prompt}]
                    })
                ),
                timeout=AI_JUDGE_TIMEOUT_SECONDS
            )

            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            insight_data = json.loads(content)

            # Validate structure
            assert "criteria_scores" in insight_data
            assert "rationale" in insight_data
            assert "confidence" in insight_data

            return insight_data

        except asyncio.TimeoutError:
            logger.warning(f"AI judge timeout for arena {arena_id}, participant {participant_id}")
            return None
        except Exception as e:
            logger.error(f"AI judge error: {e}")
            return None
```

### Integration with Live Session

```python
# In WebSocket handler, after participant stops speaking

if arena.ai_co_judge_enabled:
    # Fetch transcript (from audio processing service)
    transcript = await get_participant_transcript(participant_id)

    # Generate AI insight (non-blocking)
    ai_service = AIJudgeService()
    insight = await ai_service.generate_scoring_insight(
        arena_id=arena.id,
        participant_id=participant_id,
        transcript=transcript,
        criteria=arena.criteria
    )

    if insight:
        # Save to database
        db_insight = ArenaAIInsight(
            arena_id=arena.id,
            participant_id=participant_id,
            insight_text=insight["rationale"],
            suggested_scores=insight["criteria_scores"],
            confidence_score=insight["confidence"]
        )
        db.add(db_insight)
        await db.commit()

        # Broadcast to moderators only (admin channel)
        await connection_manager.broadcast_to_admins(
            arena_id,
            {
                "event": "ai_insight",
                "data": {
                    "participant_id": str(participant_id),
                    "insight_text": insight["rationale"],
                    "suggested_scores": insight["criteria_scores"],
                    "confidence_score": insight["confidence"]
                }
            }
        )
    else:
        # Graceful degradation - show "AI unavailable" in UI
        await connection_manager.broadcast_to_admins(
            arena_id,
            {
                "event": "ai_insight_unavailable",
                "data": {"participant_id": str(participant_id)}
            }
        )
```

---

## Report Generation

### Dependencies

```bash
pip install weasyprint jinja2
```

### PDF Report Service

```python
# app/services/report_service.py
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from io import BytesIO
import csv
from io import StringIO

class ReportService:
    def __init__(self):
        self.jinja_env = Environment(
            loader=FileSystemLoader('app/templates/reports')
        )

    async def generate_arena_summary_pdf(
        self,
        db: AsyncSession,
        arena_id: UUID
    ) -> BytesIO:
        """Generate PDF report for entire arena"""

        # Fetch data
        arena = await db.get(Arena, arena_id)
        evaluation = await db.get(ArenaEvaluation, arena_id)

        performers_query = (
            select(ArenaPerformer, User)
            .join(User, User.id == ArenaPerformer.performer_id)
            .where(ArenaPerformer.arena_id == arena_id)
            .order_by(ArenaPerformer.final_score.desc())
        )
        performers = (await db.execute(performers_query)).all()

        # Render HTML
        template = self.jinja_env.get_template('arena_summary.html')
        html_content = template.render(
            arena=arena,
            evaluation=evaluation,
            performers=performers,
            generated_at=datetime.utcnow()
        )

        # Convert to PDF
        pdf_bytes = HTML(string=html_content).write_pdf()
        return BytesIO(pdf_bytes)

    async def generate_participants_csv(
        self,
        db: AsyncSession,
        arena_id: UUID
    ) -> StringIO:
        """Generate CSV export of participants"""

        performers_query = (
            select(ArenaPerformer, User)
            .join(User, User.id == ArenaPerformer.performer_id)
            .where(ArenaPerformer.arena_id == arena_id)
            .order_by(ArenaPerformer.rank)
        )
        performers = (await db.execute(performers_query)).all()

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Rank',
            'Participant Name',
            'Student ID',
            'Final Score',
            'Speaking Time (seconds)',
            'Engagement Score',
            'Criteria Scores'
        ])

        # Rows
        for performer, user in performers:
            writer.writerow([
                performer.rank,
                user.name,
                str(user.id),
                float(performer.final_score or 0),
                performer.total_speaking_duration_seconds or 0,
                float(performer.engagement_score or 0),
                json.dumps(performer.criteria_scores)
            ])

        output.seek(0)
        return output
```

### HTML Template

```html
<!-- app/templates/reports/arena_summary.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Arena Summary - {{ arena.title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #4A90E2;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            color: #4A90E2;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #4A90E2;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .info-item {
            padding: 10px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #4A90E2;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .judgment {
            background: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #4A90E2;
            margin-top: 15px;
        }
        @page {
            margin: 2cm;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ arena.title }}</h1>
        <p style="color: #666;">Arena Session Report</p>
        <p style="font-size: 14px; color: #999;">Generated: {{ generated_at.strftime('%B %d, %Y at %H:%M UTC') }}</p>
    </div>

    <div class="section">
        <h2>Session Details</h2>
        <div class="info-grid">
            <div class="info-item">
                <strong>Arena Mode:</strong> {{ arena.arena_mode | title }}
            </div>
            <div class="info-item">
                <strong>Judging Mode:</strong> {{ arena.judging_mode | replace('_', ' ') | title }}
            </div>
            <div class="info-item">
                <strong>AI Co-Judge:</strong> {{ 'Enabled' if arena.ai_co_judge_enabled else 'Disabled' }}
            </div>
            <div class="info-item">
                <strong>Duration:</strong> {{ arena.duration_minutes }} minutes
            </div>
            <div class="info-item">
                <strong>Start Time:</strong> {{ arena.start_time.strftime('%B %d, %Y at %H:%M') if arena.start_time else 'N/A' }}
            </div>
            <div class="info-item">
                <strong>Total Participants:</strong> {{ evaluation.total_participants if evaluation else 0 }}
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Participants & Scores</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Name</th>
                    <th>Final Score</th>
                    <th>Speaking Time</th>
                    <th>Engagement</th>
                </tr>
            </thead>
            <tbody>
                {% for performer, user in performers %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ user.name }}</td>
                    <td>{{ "%.2f"|format(performer.final_score) if performer.final_score else 'N/A' }}</td>
                    <td>{{ performer.total_speaking_duration_seconds or 0 }}s</td>
                    <td>{{ "%.1f"|format(performer.engagement_score) if performer.engagement_score else 'N/A' }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    {% if evaluation %}
    <div class="section">
        <h2>Teacher Evaluation</h2>
        <div class="judgment">
            <strong>Overall Judgment:</strong>
            <p>{{ evaluation.teacher_judgment or 'No judgment provided.' }}</p>
        </div>
        {% if evaluation.teacher_remark %}
        <div class="judgment" style="margin-top: 10px;">
            <strong>Remarks:</strong>
            <p>{{ evaluation.teacher_remark }}</p>
        </div>
        {% endif %}
        <div class="info-grid" style="margin-top: 20px;">
            <div class="info-item">
                <strong>Average Score:</strong> {{ "%.2f"|format(evaluation.final_average_score) if evaluation.final_average_score else 'N/A' }}
            </div>
            <div class="info-item">
                <strong>Total Reactions:</strong> {{ evaluation.total_reaction_count or 0 }}
            </div>
        </div>
    </div>
    {% endif %}

    <div style="margin-top: 50px; text-align: center; color: #999; font-size: 12px;">
        <p>YouSpeak Arena Management System</p>
        <p>This is an official arena session report.</p>
    </div>
</body>
</html>
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "specific_field",
      "reason": "more context"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_JOIN_CODE` | 400 | Join code is invalid or expired |
| `ALREADY_JOINED` | 409 | Student already in waiting room |
| `ARENA_NOT_FOUND` | 404 | Arena does not exist |
| `ARENA_SESSION_ENDED` | 400 | Cannot join - session has ended |
| `NOT_AUTHORIZED` | 403 | User lacks permission for this action |
| `INVALID_TOKEN` | 401 | JWT token is invalid or expired |
| `ARENA_NOT_LIVE` | 400 | Arena is not in live state |
| `PARTICIPANT_NOT_FOUND` | 404 | Participant does not exist in this arena |
| `AI_SERVICE_UNAVAILABLE` | 503 | AI co-judge service temporarily unavailable |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests (reactions, API calls) |

### Edge Case Handling

#### 1. Teacher Disconnects During Live Session

**Problem**: Teacher loses connection, cannot score participants

**Solution**:
- Designate co-moderators before session starts
- Implement "moderator reconnection grace period" (30 seconds)
- Store partial session state in Redis with TTL
- Allow teacher to resume with same session ID

**Implementation**:
```python
async def handle_moderator_disconnect(arena_id: UUID, teacher_id: UUID):
    # Set grace period in Redis
    await redis.setex(
        f"moderator_grace:{arena_id}:{teacher_id}",
        30,  # 30 seconds TTL
        "reconnecting"
    )

    # Allow reconnection with same WebSocket session
    # If grace period expires, close session or transfer to co-moderator
```

---

#### 2. Concurrent Admission from Multiple Moderators

**Problem**: Two teachers try to admit same student simultaneously

**Solution**:
- Database UNIQUE constraint on `(arena_id, student_id)` in `arena_participants`
- Use transaction with `READ COMMITTED` isolation level
- Return 409 Conflict if already admitted

**Implementation**:
```python
async def admit_student(arena_id: UUID, entry_id: UUID, teacher_id: UUID):
    async with db.begin():  # Transaction
        # Update waiting room
        await db.execute(...)

        try:
            # Create participant (will fail if duplicate due to UNIQUE constraint)
            participant = ArenaParticipant(arena_id=arena_id, student_id=student_id)
            db.add(participant)
            await db.flush()  # Trigger constraint check
        except IntegrityError:
            raise HTTPException(409, "Student already admitted")
```

---

#### 3. Join Code Collision

**Problem**: Random 6-digit code might collide with existing code

**Solution**:
- Retry logic with 3 attempts
- Fallback to 8-character alphanumeric if collisions persist
- Query uniqueness before INSERT

**Implementation**:
```python
async def generate_unique_join_code(db: AsyncSession, max_attempts=3):
    for attempt in range(max_attempts):
        code = generate_join_code(length=6 if attempt < 2 else 8)

        # Check uniqueness
        existing = await db.execute(
            select(Arena).where(Arena.join_code == code)
        )
        if not existing.scalar_one_or_none():
            return code

    raise Exception("Failed to generate unique join code after 3 attempts")
```

---

#### 4. Reaction Spam

**Problem**: Student sends 1000 reactions/second

**Solution**:
- Client-side throttle (1 reaction/second)
- Server-side rate limit (5 reactions per 10 seconds)
- Redis sliding window counter

**Implementation**:
```python
async def check_reaction_rate_limit(user_id: UUID, arena_id: UUID) -> bool:
    key = f"reaction_limit:{arena_id}:{user_id}"
    count = await redis.incr(key)

    if count == 1:
        await redis.expire(key, 10)  # 10 second window

    return count <= 5  # Max 5 reactions per 10 seconds
```

---

#### 5. AI Co-Judge Timeout

**Problem**: AWS Bedrock API call takes >5 seconds

**Solution**:
- Graceful degradation
- Show "AI unavailable" badge in UI
- Teacher can still score manually
- Log timeout for monitoring

**Implementation**: See [AI Co-Judge Integration](#ai-co-judge-integration) section.

---

## Testing Strategy

### Integration Tests (Priority: HIGH)

Test all 24 REST endpoints with real PostgreSQL + FastAPI TestClient.

**Location**: `tests/integration/test_arenas_*.py`

**Example Test**:

```python
# tests/integration/test_arenas_session.py

async def test_initialize_arena_competitive_mode(client, auth_headers_teacher, db_session):
    """
    Given: A created arena with 4 students in class
    When: Teacher initializes session with competitive mode + manual selection
    Then: Session is created with 2 participants, status is 'initialized'
    """
    # Arrange
    arena = await create_test_arena(db_session, teacher_id, class_id)
    students = await create_test_students(db_session, class_id, count=4)

    # Act
    response = await client.post(
        f"/api/v1/arenas/{arena.id}/initialize",
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": [str(s.id) for s in students[:2]]
        },
        headers=auth_headers_teacher
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "initialized"
    assert len(data["participants"]) == 2
    assert data["configuration"]["arena_mode"] == "competitive"

    # Verify DB state
    participants = await db_session.execute(
        select(ArenaParticipant).where(ArenaParticipant.arena_id == arena.id)
    )
    assert len(participants.all()) == 2
```

**Test Coverage Target**: 90% for endpoints, 80% for service layer

---

### WebSocket Integration Tests

**Location**: `tests/integration/test_arenas_websocket.py`

**Example Test**:

```python
async def test_websocket_speaking_state_broadcast(client, db_session):
    """
    Given: 3 clients connected to live arena WebSocket
    When: One participant sends 'speaking_started' event
    Then: All clients receive 'speaking_update' broadcast
    """
    arena = await create_live_arena(db_session, teacher_id, class_id)

    # Connect 3 clients
    async with client.websocket_connect(f"/api/v1/arenas/{arena.id}/live?token={jwt1}") as ws1, \
               client.websocket_connect(f"/api/v1/arenas/{arena.id}/live?token={jwt2}") as ws2, \
               client.websocket_connect(f"/api/v1/arenas/{arena.id}/live?token={jwt3}") as ws3:

        # Act: Client 1 sends speaking_started
        await ws1.send_json({"event": "speaking_started", "data": {}})

        # Assert: All clients receive speaking_update
        msg1 = await ws1.receive_json()
        msg2 = await ws2.receive_json()
        msg3 = await ws3.receive_json()

        assert msg1["event"] == "speaking_update"
        assert msg1["data"]["is_speaking"] == True
        assert msg2 == msg1  # All receive identical message
        assert msg3 == msg1
```

---

### E2E Test (1 Critical Flow)

**Location**: `tests/e2e/test_arena_full_lifecycle.py`

```python
async def test_full_competitive_arena_lifecycle():
    """
    Full flow:
    1. Teacher creates arena
    2. Teacher initializes with competitive mode
    3. Generate join code
    4. 2 students join waiting room
    5. Teacher admits both
    6. Teacher starts session
    7. Students perform (simulated speaking events via WebSocket)
    8. Teacher scores both performers
    9. Teacher evaluates and writes judgment
    10. Teacher publishes results
    11. Verify students see results in their dashboard
    """
    # Implementation spanning ~200 lines
    # Tests complete user journey from creation to published results
```

---

## Implementation Phases

### Phase 1: Session Configuration (Week 1-2)

**Goal**: Teachers can configure arena sessions and select students

**Dependencies**: None (can start immediately)

**Database Changes**:
- Add 4 columns to `arenas` table: `arena_mode`, `judging_mode`, `ai_co_judge_enabled`, `student_selection_mode`

**Endpoints to Implement**:
1. `GET /students/search`
2. `POST /arenas/{id}/initialize`
3. `POST /arenas/{id}/students/randomize`
4. `POST /arenas/{id}/students/hybrid`

**Tests**:
- 5 integration tests covering all endpoints
- Validation tests for required fields
- Authorization tests (teacher-only)

**Deliverable**: Frontend can build Screen 1 (Student Selection)

---

### Phase 2: Waiting Room & Admission (Week 3)

**Goal**: Students can join via code, teachers admit from queue

**Dependencies**: Phase 1 complete

**Database Changes**:
- Create `arena_waiting_room` table

**Endpoints to Implement**:
1. `POST /arenas/{id}/join-code`
2. `POST /arenas/{id}/waiting-room/join`
3. `GET /arenas/{id}/waiting-room`
4. `POST /arenas/{id}/waiting-room/{entry_id}/admit`
5. `POST /arenas/{id}/waiting-room/{entry_id}/reject`

**Additional Work**:
- QR code generation (using `qrcode` library)
- Join code uniqueness validation

**Tests**:
- 6 integration tests covering all endpoints
- Edge case tests (expired codes, duplicate joins)

**Deliverable**: Frontend can build Screen 4 (Arena Entry)

---

### Phase 3: WebSocket Infrastructure (Week 4-5)

**Goal**: Real-time communication backbone

**Dependencies**: Phase 2 complete

**Infrastructure Setup**:
- Redis Pub/Sub server
- Connection Manager class

**Endpoints to Implement**:
1. `WS /arenas/{id}/live`

**Event Handlers**:
- All client→server events (speaking_started, reaction_sent, etc.)
- All server→client broadcasts (speaking_update, engagement_update, etc.)

**Tests**:
- 8 WebSocket integration tests
- Connection/disconnection tests
- Message broadcast tests

**Deliverable**: Real-time communication ready for live session features

---

### Phase 4: Live Session Features (Week 5-6)

**Goal**: Full live session functionality with scoring and analytics

**Dependencies**: Phase 3 complete

**Database Changes**:
- Create `arena_participants`, `arena_reactions` tables

**Endpoints to Implement**:
1. `POST /arenas/{id}/start`
2. `GET /arenas/{id}/session`
3. `POST /arenas/{id}/participants/{id}/score`
4. `GET /arenas/{id}/analytics/live`
5. `POST /arenas/{id}/end`

**Additional Work**:
- Speaking duration tracking
- Engagement score calculation
- Reaction aggregation

**Tests**:
- 7 integration tests covering all endpoints
- Real-time analytics calculation tests

**Deliverable**: Frontend can build Screen 5 (Live Session)

---

### Phase 5: AI Co-Judge & Evaluation (Week 6-7)

**Goal**: AI insights, final evaluation, report generation

**Dependencies**: Phase 4 complete

**Database Changes**:
- Create `arena_ai_insights`, `arena_evaluations` tables

**Endpoints to Implement**:
1. `POST /arenas/{id}/evaluate`
2. `POST /arenas/{id}/publish`
3. `GET /arenas/{id}/reports/summary.pdf`
4. `GET /arenas/{id}/reports/participants.csv`

**Additional Work**:
- AWS Bedrock integration
- PDF template design (Jinja2 + WeasyPrint)
- CSV generation

**Tests**:
- 5 integration tests covering all endpoints
- AI service mock tests
- PDF/CSV generation tests

**Deliverable**: Frontend can build Screen 6 (Evaluation)

---

### Phase 6: Collaborative Mode & Polish (Week 8-10)

**Goal**: Full system production-ready

**Dependencies**: Phase 5 complete

**Database Changes**:
- Create `arena_teams`, `arena_team_members` tables

**Endpoints to Implement**:
1. `POST /arenas/{id}/teams`
2. `GET /arenas/{id}/teams`
3. `GET /arenas/history`

**Additional Work**:
- E2E test for full lifecycle
- Performance optimization (Redis caching, query optimization)
- Load testing (100 concurrent WebSocket connections)
- Documentation finalization

**Deliverable**: Full system ready for production deployment

---

## Appendix

### Dependencies to Add

```txt
# requirements.txt additions
redis==5.0.1
aioredis==2.0.1
weasyprint==60.2
jinja2==3.1.2
qrcode[pil]==7.4.2
boto3==1.34.34  # AWS Bedrock
```

### Environment Variables

```bash
# .env additions
REDIS_URL=redis://localhost:6379
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
AI_JUDGE_TIMEOUT_SECONDS=5
STORAGE_BUCKET=youspeak-arena-assets  # For QR codes, reports
```

---

**Document End**

For questions or clarifications, refer to:
- RESPONSE_TO_FRONTEND_DEV.md - Frontend developer communication
- ARENA_MANAGEMENT_PRD.md - Original product requirements
- ARENA_ENDPOINTS_SUMMARY.md - Quick reference for existing endpoints
