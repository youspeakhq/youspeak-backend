# Cloudflare RealtimeKit - How It Works

## Overview
Cloudflare RealtimeKit provides real-time WebRTC audio infrastructure on Cloudflare's global edge network (335+ locations worldwide).

## Architecture Flow

### 1. **Backend: Create Meeting (One-time Setup)**
```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/realtime/kit/{app_id}/meetings
```

**Request:**
```json
{
  "title": "Arena: Speaking Challenge",
  "record_on_start": true,
  "persist_chat": false
}
```

**Response:**
```json
{
  "result": {
    "id": "meeting_abc123",
    "title": "Arena: Speaking Challenge",
    "created_at": "2026-03-28T20:00:00Z"
  }
}
```

**What happens:** Cloudflare creates a reusable "room" for this arena. The meeting ID is stored in the database (`arena.realtimekit_meeting_id`).

---

### 2. **Backend: Add Participant & Get Auth Token**
When a user (teacher or student) joins the arena, they request an audio token:

```
POST /api/v1/arenas/{arena_id}/audio/token
Authorization: Bearer {user_jwt}
```

**Backend flow:**
1. Verify user is authorized (teacher or admitted student)
2. Get or create RealtimeKit meeting for this arena
3. Call Cloudflare to add participant:

```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/realtime/kit/{app_id}/meetings/{meeting_id}/participants
```

**Request:**
```json
{
  "custom_participant_id": "user_uuid",
  "preset_name": "group_call_host",  // or "group_call_participant"
  "name": "John Doe"
}
```

**Response:**
```json
{
  "result": {
    "id": "participant_xyz",
    "token": "eyJhbGciOiJSUzI1Ni...",  // THIS is what frontend needs!
    "custom_participant_id": "user_uuid",
    "preset_name": "group_call_host",
    "name": "John Doe",
    "created_at": "2026-03-28T20:05:00Z"
  }
}
```

**Backend returns to frontend:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJSUzI1Ni...",
    "participant_id": "participant_xyz789",
    "meeting_id": "meeting_abc123",
    "preset_name": "group_call_host",
    "name": "John Doe"
  },
  "message": "Audio token generated (group_call_host)"
}
```

---

### 3. **Frontend: Join Meeting with SDK**

The frontend receives the `token` and uses Cloudflare's RealtimeKit SDK:

```javascript
import { RealtimeKitClient } from '@cloudflare/realtimekit-client';

// Initialize client with the auth token from backend
const client = new RealtimeKitClient({
  authToken: audioToken  // From step 2
});

// Join the meeting
await client.connect();

// Listen to other participants
client.on('participantJoined', (participant) => {
  console.log('New participant:', participant.name);
});

client.on('audioTrack', (track, participant) => {
  // Play audio from this participant
  const audio = new Audio();
  audio.srcObject = new MediaStream([track]);
  audio.play();
});

// Publish your own audio (for teachers/hosts)
const localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
const audioTrack = localStream.getAudioTracks()[0];
await client.publishTrack(audioTrack);

// Everyone in the meeting automatically receives your audio!
```

---

## How Members Listen to Each Other (Real-time Audio)

### WebRTC Peer-to-Peer Architecture

1. **Signaling via Cloudflare Edge:**
   - All audio streams are routed through Cloudflare's edge network
   - <50ms latency globally (thanks to 335+ data centers)
   - No direct peer-to-peer connections (simpler NAT traversal)

2. **Audio Streaming:**
   ```
   Teacher speaks → WebRTC → Cloudflare Edge → WebRTC → All Students hear
   Student speaks → WebRTC → Cloudflare Edge → WebRTC → Teacher hears
   ```

3. **Automatic Mixing:**
   - Each participant receives a mixed audio stream of ALL other participants
   - No need to manually mix tracks
   - Cloudflare handles echo cancellation and noise suppression

---

## Role-Based Access (Presets)

### **group_call_host** (Teachers/Admins)
- ✅ **Can:** Publish audio (speak)
- ✅ **Can:** Receive audio (listen to everyone)
- ✅ **Can:** Kick participants
- ✅ **Can:** Mute other participants
- Used for: Teachers, School Admins

### **group_call_participant** (Students)
- ✅ **Can:** Publish audio (speak) - Students are NOT receive-only!
- ✅ **Can:** Receive audio (listen to everyone)
- ❌ **Cannot:** Kick or mute others
- Used for: Students who have been admitted to the arena

**In code:**
```python
if user.role in [UserRole.TEACHER, UserRole.SCHOOL_ADMIN]:
    preset_name = "group_call_host"
else:
    preset_name = "group_call_participant"
```

---

## Security Model

1. **JWT-based authentication:**
   - User logs in → Gets JWT from your backend
   - User requests audio token → Backend validates JWT
   - Backend calls Cloudflare → Gets RealtimeKit auth token
   - Frontend uses RealtimeKit token to join

2. **Short-lived tokens:**
   - RealtimeKit tokens expire after the meeting
   - Must request new token for each session

3. **Server-side authorization:**
   - Only backend can create meetings
   - Only backend can add participants
   - Frontend cannot bypass permission checks

---

## Recording & Playback

**Auto-recording** (enabled with `record_on_start: true`):
- Starts when first participant joins
- Stops when last participant leaves
- Saved to Cloudflare R2 storage
- Accessible via Cloudflare API

**Manual recording control:**
```python
# Start recording
await realtimekit_service.start_recording(arena_id, meeting_id)

# Stop recording
await realtimekit_service.stop_recording(meeting_id, recording_id)
```

---

## Testing Flow

### **Step 1:** Register school and get auth token
```bash
curl -X POST https://api-staging.youspeakhq.com/api/v1/auth/register/school \
  -H "Content-Type: application/json" \
  -d '{
    "school_name": "Test School",
    "email": "test@example.com",
    "password": "TestPass123!",
    "school_type": "secondary",
    "program_type": "partnership",
    "address_country": "US",
    "address_state": "CA",
    "address_city": "SF",
    "address_zip": "94102",
    "languages": ["spanish"]
  }'
```

### **Step 2:** Login and get JWT
```bash
curl -X POST https://api-staging.youspeakhq.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'
```

### **Step 3:** Create classroom, arena, start session

### **Step 4:** Get audio token
```bash
curl -X POST https://api-staging.youspeakhq.com/api/v1/arenas/{arena_id}/audio/token \
  -H "Authorization: Bearer {jwt_token}"
```

**Expected response:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGc...",
    "participant_id": "participant_xyz789",
    "meeting_id": "meeting_abc123",
    "preset_name": "group_call_host",
    "name": "John Doe"
  },
  "message": "Audio token generated (group_call_host)"
}
```

### **Step 5:** Frontend joins with SDK
```javascript
const client = new RealtimeKitClient({ authToken: data.token });
await client.connect();
// Now you're in the live audio session!
```

---

## Troubleshooting

### "Cannot create meeting: RealtimeKit credentials not configured"
**Cause:** Environment variables not set
**Solution:** Verify:
```bash
# Should return account ID
aws secretsmanager get-secret-value --secret-id youspeak/cloudflare-account-id-staging --region us-east-1

# Check ECS task definition includes secrets
aws ecs describe-task-definition --task-definition youspeak-api-task:11 --region eu-north-1
```

### "Failed to create audio meeting" (HTTP 500)
**Cause:** Cloudflare API call failed
**Solution:** Check logs:
```bash
aws logs tail /ecs/youspeak-api --region us-east-1 --filter-pattern "CloudFlare" --since 5m
```

### Meeting ID not saved to database
**Cause:** Transaction failed after meeting creation
**Solution:** Check `arena.realtimekit_meeting_id` field in database
