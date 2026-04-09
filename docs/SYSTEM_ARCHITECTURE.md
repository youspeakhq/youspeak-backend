# YouSpeak Backend — System Architecture & Decisions

Living document of architectural choices, technology decisions, and system design rationale.
Updated as decisions are made.

---

## Infrastructure Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Compute** | AWS ECS Fargate | Serverless containers, no instance management, auto-scaling |
| **Database** | PostgreSQL (AWS RDS) | Relational data with strong consistency for user/school/arena models |
| **Cache / Pub-Sub** | Redis (ElastiCache) | WebSocket horizontal scaling via Pub/Sub, session caching |
| **Object Storage** | Cloudflare R2 | S3-compatible, zero egress fees for audio recordings and uploads |
| **Container Registry** | AWS ECR | Native ECS integration |
| **Secrets** | AWS Secrets Manager | Injected into ECS task definitions at runtime |
| **IaC** | Terraform | Reproducible infrastructure, version-controlled |
| **CI/CD** | GitHub Actions | Build, test, deploy on push to main |
| **DNS / CDN** | Cloudflare + Route53 | Cloudflare for CDN/DDoS, Route53 for DNS records |

---

## Application Architecture

| Component | Technology | Why |
|-----------|-----------|-----|
| **API Framework** | FastAPI (Python) | Async-first, Pydantic validation, OpenAPI docs, WebSocket support |
| **ORM** | SQLAlchemy 2.0 (async) | Mature, async support, Alembic migrations |
| **Auth** | JWT (HS256) | Stateless auth, short-lived access + refresh tokens |
| **Email** | Resend | Simple API, good deliverability |
| **AI (Curriculum)** | AWS Bedrock (Nova Lite) | Structured output for curriculum generation, assessment scoring |
| **AI (Pronunciation)** | Azure Speech Services | Only managed API with real pronunciation assessment (see below) |
| **Audio Conferencing** | Cloudflare RealtimeKit | WebRTC SFU, auto-recording to R2, low-latency audio |

---

## Key Design Decisions

### 1. Azure Speech for Pronunciation Assessment (April 2026)

**Decision:** Use Azure Speech Pronunciation Assessment alongside our AWS-native stack.

**Why Azure (cross-cloud)?**
- AWS has no pronunciation assessment API. Amazon Transcribe does speech-to-text (what was said) but cannot score how well it was pronounced.
- Google Speech-to-Text and OpenAI Whisper are also transcription-only — no phoneme accuracy, fluency metrics, or mispronunciation detection.
- Azure Speech is the only managed service that provides:
  - Per-word accuracy score (0-100) comparing spoken phonemes to native reference
  - Fluency score (natural rhythm, pauses)
  - Mispronunciation / omission / insertion detection per word
  - Prosody score for English (stress, intonation)
  - 33 supported languages including English, Spanish, French, Russian, Arabic, Chinese, Portuguese
- Cost: ~$1.32/hr of audio at standard rates.

**Trade-off:** Introduces a single non-AWS dependency (managed via `AZURE_SPEECH_KEY` in Secrets Manager). Acceptable because no AWS equivalent exists and building custom pronunciation models is Phase 2.

**Phase 2 plan (rare languages):** For languages Azure doesn't support (e.g. Ibibio), we'll fine-tune wav2vec2/HuBERT models on target language phoneme data and self-host on AWS SageMaker. The backend's `AudioAnalysisService` is designed to swap providers based on language.

### 2. Real-Time Audio Analysis Pipeline

**Architecture:**
```
Frontend (per speaker)                    Backend (FastAPI)
  AudioWorklet captures mic ──►  Binary WS frames (PCM 16kHz 16-bit mono)
  alongside RealtimeKit WebRTC      │
                                     ▼
                              AudioAnalysisService
                                ├─ Azure Speech PushAudioInputStream
                                │   (streaming pronunciation assessment)
                                ├─ Rolling score aggregation (last 10 segments)
                                └─ Bedrock LLM coaching tips (every ~10s)
                                     │
                                     ▼
                              WS broadcast "ai_analysis" event
                              ──► Teacher monitoring panel
```

**Why binary WebSocket frames (not base64 JSON)?**
- Raw PCM at 16kHz 16-bit = 32KB/s per speaker
- Base64 encoding would add ~33% overhead (42KB/s) for zero benefit since the WS connection is already authenticated
- Backend identifies sender from the JWT-authenticated connection (user_id known from connect)

**Why parallel audio capture (not tapping RealtimeKit)?**
- RealtimeKit is a P2P WebRTC SFU — the backend has no server-side access to audio streams
- Recordings go to R2 as complete files (post-session only), no real-time chunk API
- Frontend captures audio via AudioWorklet alongside the WebRTC session — both read from the same mic MediaStream, no conflict

### 3. Bedrock for Coaching Feedback Summaries

**Decision:** Use AWS Bedrock (Nova Lite) to generate 1-sentence coaching tips from pronunciation scores.

**Why not Azure OpenAI or standalone GPT?**
- Already using Bedrock for curriculum generation — reuse existing client, IAM roles, and billing
- Nova Lite is fast and cheap for short completions (60 token max)
- Keeps AI inference costs consolidated on AWS

**Throttling:** One feedback summary per ~10 seconds per participant to avoid Bedrock cost/latency during live sessions.

### 4. WebSocket Architecture (Arena Live Sessions)

**Design:** Single WebSocket endpoint per arena (`/arenas/{id}/live`) handles both coordination events and audio.

**Event types:**
| Direction | Event | Format |
|-----------|-------|--------|
| Client → Server | `speaking_started` / `speaking_stopped` | JSON text frame |
| Client → Server | `reaction_sent` | JSON text frame |
| Client → Server | Audio chunks | Binary frame (PCM bytes) |
| Server → Client | `speaking_update` | JSON text frame |
| Server → Client | `reaction_broadcast` | JSON text frame |
| Server → Client | `ai_analysis` | JSON text frame |
| Server → Client | `session_state` / `session_ended` | JSON text frame |

**Horizontal scaling:** Redis Pub/Sub channel per arena (`arena:{id}:live`). Any server receiving a message publishes to Redis; all servers with connections to that arena receive and broadcast locally.

**Rate limiting:**
- Text messages: 30/minute per user (disconnect on exceed)
- Audio bytes: 512KB/s per user (drop excess chunks, don't disconnect)

### 5. Cloudflare RealtimeKit for Audio Conferencing

**Decision:** Cloudflare RealtimeKit (WebRTC SFU) for live arena audio.

**Why not Twilio / Agora / LiveKit?**
- Already using Cloudflare for R2, CDN, DNS — consolidated vendor
- Auto-records to R2 with zero egress fees
- Simple token-based auth with presets (host/participant roles)
- Competitive pricing for WebRTC SFU

**Limitation:** No server-side audio stream access. Audio flows P2P through the SFU; backend only gets complete recordings after session ends. This is why we capture audio separately via AudioWorklet for real-time analysis.

### 6. Curriculum AI Service (Separate Microservice)

**Decision:** Curriculum generation runs as a separate FastAPI service, proxied by the main API.

**Why separate?**
- Heavy AI operations (Bedrock calls with retries) isolated from the main API
- Independent scaling — curriculum generation is bursty
- Circuit breaker pattern prevents Bedrock failures from cascading to other endpoints
- Different timeout requirements (90s for generation vs 30s for normal API)

---

## Database Design Principles

- **UUIDs for all primary keys** — no auto-increment leakage
- **Soft delete via `is_active` flag** — preserve referential integrity
- **School-scoped data** — `SchoolScopedMixin` on models that belong to a school, enforced at query level
- **Alembic migrations** — sequential numbering for arena phases (001-010+), hash IDs for general migrations
- **Nullable AI score columns** — `ai_pronunciation_score` and `ai_fluency_score` on ArenaParticipant are NULL until analysis runs

---

## Security Model

- **JWT auth** with short-lived access tokens (15 min) and refresh tokens (7 days)
- **RBAC:** Three roles — `school_admin`, `teacher`, `student` — enforced via FastAPI dependencies (`require_admin`, `require_teacher`, `require_teacher_or_admin`)
- **WebSocket auth:** JWT in query param or Authorization header, verified on connect
- **Secrets:** Never in code. All via environment variables, injected from AWS Secrets Manager in ECS
- **CORS:** Explicit origin whitelist + regex for `*.youspeakhq.com`
- **Rate limiting:** Global per-IP + per-user for authenticated endpoints

---

## Cost Awareness

| Service | Cost Driver | Optimization |
|---------|------------|-------------|
| Azure Speech | ~$1.32/hr audio | Only runs during active speaking in live sessions |
| AWS Bedrock | Per-token | Throttled to 1 call/10s per participant, 60 token max |
| Cloudflare R2 | Storage only (no egress) | Lifecycle policies for old recordings |
| RDS PostgreSQL | Instance hours | Right-sized, connection pooling via SQLAlchemy |
| ECS Fargate | vCPU + memory hours | Auto-scaling, right-sized tasks |

---

## Future Architecture Notes

- **Phase 2 languages (Ibibio, etc.):** Fine-tune wav2vec2/HuBERT on custom phoneme datasets, host on SageMaker. Backend swaps provider based on `Language.code` → Azure locale mapping. If no Azure locale exists, route to custom model endpoint.
- **Post-session analysis:** Use R2 recordings + full transcription for deeper analysis (vocabulary, grammar, content scoring) via Bedrock after session ends.
- **Real-time engagement scoring:** Currently manual delta updates. Plan: derive from speaking time + reactions + AI scores automatically.
