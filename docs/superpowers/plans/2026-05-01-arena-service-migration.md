# Arena Service Migration Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Arena live session functionality from the core backend to a specialized standalone service to improve scalability and reliability.

**Architecture:** Three-phase migration starting with a shared database (Phase 1), moving to internal API communication for metadata (Phase 2), and optimizing the audio pipeline with a dedicated message bus (Phase 3).

**Tech Stack:** FastAPI, PostgreSQL (Shared), Redis (Pub/Sub), Docker, GitHub Actions, AWS ECS.

---

## Phase 1: Hybrid Split (Foundation)

### Task 1: Scaffold Arena Service Structure
**Files:**
- Create: `services/arena/main.py`
- Create: `services/arena/config.py`
- Create: `services/arena/database.py`
- Create: `services/arena/Dockerfile`
- Create: `services/arena/requirements.txt`

- [ ] **Step 1: Create base directory and requirements**
```python
# services/arena/requirements.txt
fastapi==0.110.0
uvicorn==0.27.1
sqlalchemy==2.0.27
asyncpg==0.29.0
redis==5.0.1
azure-cognitiveservices-speech==1.35.0
boto3==1.34.40
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
```

- [ ] **Step 2: Create config and database modules**
- [ ] **Step 3: Create Dockerfile (multi-stage build)**

### Task 2: Port Real-time Audio Logic
**Files:**
- Create: `services/arena/services/audio_analysis_service.py`
- Create: `services/arena/services/realtimekit_service.py`
- Create: `services/arena/websocket/connection_manager.py`

- [ ] **Step 1: Move AudioAnalysisService**
- [ ] **Step 2: Move ArenaConnectionManager (preserving Redis Pub/Sub logic)**
- [ ] **Step 3: Move RealtimeKitService**

### Task 3: Move Live Session Endpoints
**Files:**
- Create: `services/arena/api/v1/endpoints/live.py`
- Modify: `app/api/v1/endpoints/arenas.py` (Remove live routes)

- [ ] **Step 1: Port WebSocket endpoint**
- [ ] **Step 2: Port /join-code, /waiting-room, /admit, /audio/token**

### Task 4: Infrastructure & CI/CD
**Files:**
- Modify: `.github/workflows/ci-cd.yml`
- Modify: `terraform/main.tf`

- [ ] **Step 1: Add Arena service to CI/CD bake/build**
- [ ] **Step 2: Define ECS service and Target Group in Terraform**
- [ ] **Step 3: Configure ALB listener rules (path-based routing: /api/v1/arenas/live/*)**

---

## Phase 2: Decoupling (API Communication)

### Task 5: Core Internal API
**Files:**
- Create: `app/api/v1/endpoints/internal.py`

- [ ] **Step 1: Add internal metadata endpoints for Arena Service**
```python
@router.get("/arenas/{id}/metadata")
async def get_arena_metadata(id: UUID, db: AsyncSession):
    # Returns arena criteria, rules, and student selection
```

### Task 6: Refactor Arena Service to use Internal API
**Files:**
- Modify: `services/arena/services/arena_logic.py`

- [ ] **Step 1: Replace direct DB calls for metadata with HTTP calls to Core Service**

---

## Phase 3: Optimization (Message Bus)

### Task 7: Redis Streams for Audio
**Files:**
- Modify: `services/arena/websocket/connection_manager.py`
- Create: `services/arena/workers/audio_worker.py`

- [ ] **Step 1: Ingest audio chunks into Redis Streams instead of direct processing**
- [ ] **Step 2: Create background workers to consume from Redis Streams and call Azure/Bedrock**
