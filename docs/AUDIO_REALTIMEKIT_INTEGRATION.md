# Cloudflare RealtimeKit Audio Integration

## Overview

YouSpeak uses **Cloudflare RealtimeKit** for real-time audio conferencing in Arena live sessions.

- **Architecture**: WebRTC SFU (Selective Forwarding Unit) on Cloudflare's edge network (335+ locations)
- **Latency**: <50ms globally
- **Cost**: $0.0005/min/participant (~$1.52 per 1-hour session with 50 participants)
- **Recording**: Cloud recording to Cloudflare R2 bucket

## Role-Based Audio Model

### Host (Teachers)
- Can **publish** audio (speak)
- Can **receive** audio (hear others)
- Full audio controls

### Audience (Students)
- Can **receive** audio only (listen)
- Cannot publish audio by default
- Optimized for cost (audience is ~10x cheaper than host)

## API Integration

### 1. Generate Audio Token

**Endpoint**: `POST /api/v1/arenas/{arena_id}/audio/token`

**Authentication**: Bearer token (teacher or admitted student)

**Request**:
```bash
POST /api/v1/arenas/{arena_id}/audio/token
Authorization: Bearer <JWT_TOKEN>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "token": "auth_token_from_cloudflare",
    "participant_id": "participant_uuid",
    "meeting_id": "meeting_uuid",
    "preset_name": "teacher-host",
    "name": "John Doe"
  },
  "message": "Audio token generated (teacher-host)"
}
```

**Preset Determination**:
- Teachers → `"teacher-host"` (can publish audio)
- Students → `"student-audience"` (receive-only)

**Token**: authToken from Cloudflare, valid until explicitly revoked or meeting ends

**Requirements**:
- Arena session must be in `"initialized"` or `"live"` state
- Students must be admitted from waiting room first

---

## Frontend Integration

### React Native + Web

Cloudflare RealtimeKit uses **standard WebRTC APIs** that work on both React Native and Web.

### Installation

```bash
npm install @cloudflare/realtimekit-sdk
# or
yarn add @cloudflare/realtimekit-sdk
```

### React Native Setup

```typescript
import { RealtimeKitClient } from '@cloudflare/realtimekit-sdk';

const AudioProvider = ({ arenaId, children }) => {
  const [client, setClient] = useState<RealtimeKitClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(true);

  useEffect(() => {
    const initAudio = async () => {
      try {
        // 1. Get audio token from backend
        const response = await fetch(
          `${API_URL}/api/v1/arenas/${arenaId}/audio/token`,
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );

        const { data } = await response.json();
        const { token, room_id } = data;

        // 2. Initialize RealtimeKit client
        const rtcClient = new RealtimeKitClient({
          token,
          roomId: room_id,
        });

        // 3. Connect to audio room
        await rtcClient.connect();
        setClient(rtcClient);
        setIsConnected(true);

        // 4. Listen for remote audio tracks
        rtcClient.on('track', (track, participant) => {
          console.log(`Received audio from: ${participant.name}`);
          // Play remote audio automatically
          const audio = new Audio();
          audio.srcObject = new MediaStream([track]);
          audio.play();
        });

      } catch (error) {
        console.error('Failed to initialize audio:', error);
      }
    };

    initAudio();

    return () => {
      client?.disconnect();
    };
  }, [arenaId]);

  const toggleMute = async () => {
    if (client) {
      if (isMuted) {
        await client.publishAudio();
      } else {
        await client.unpublishAudio();
      }
      setIsMuted(!isMuted);
    }
  };

  return (
    <AudioContext.Provider value={{ isConnected, isMuted, toggleMute }}>
      {children}
    </AudioContext.Provider>
  );
};
```

### Web Setup (Same API)

The exact same code works in web browsers - RealtimeKit uses WebRTC which is natively supported.

---

## Architecture Flow

```
1. Student/Teacher opens Arena session
   ↓
2. Frontend calls POST /arenas/{id}/audio/token
   ↓
3. Backend validates access and generates JWT token
   ↓
4. Frontend connects to RealtimeKit with token
   ↓
5. Audio flows through Cloudflare edge network (not backend)
   ↓
6. Recording saved to R2 (if enabled)
```

**Important**: Audio traffic does NOT flow through the YouSpeak backend. It goes directly through Cloudflare's edge network (WebRTC SFU).

---

## WebSocket vs Audio

### WebSocket (`/arenas/{id}/live`)
- Session state and coordination
- Speaking indicators (visual)
- Reactions (emojis)
- Engagement tracking
- Participant status

### RealtimeKit Audio
- Actual audio transmission
- WebRTC media streams
- Audio mixing and forwarding
- Voice activity detection

**Both are required** for full Arena functionality:
- WebSocket handles session coordination
- RealtimeKit handles audio transmission

---

## Recording & Transcription

### Start Recording

Recording is started automatically when the arena session goes live (handled internally).

### Recording Output

- **Format**: MP4 (audio-only)
- **Location**: Cloudflare R2 bucket at `arena-recordings/{arena_id}/`
- **Access**: Private (requires signed URL)

### Transcription (Post-Session)

After recording completes, backend automatically:
1. Retrieves recording from R2
2. Sends to AWS Transcribe
3. Stores transcript in database
4. Uses transcript for AI analysis

---

## Cost Optimization

### Host vs Audience Pricing

| Role     | Cost/min/user | 1-hour session |
|----------|---------------|----------------|
| Host     | $0.0050       | $3.00          |
| Audience | $0.0005       | $0.30          |

**Example**: 1 teacher + 49 students for 60 minutes
- Teacher (host): 1 × $3.00 = $3.00
- Students (audience): 49 × $0.30 = $14.70
- **Total**: $17.70/session

### Best Practices

1. **Limit hosts**: Only teachers should be hosts
2. **Audience-first**: All students are audience by default
3. **Selective promotion**: Promote students to host only when speaking
4. **Session duration**: Monitor and cap session length

---

## Environment Variables

Add these to your `.env` file:

```bash
# Cloudflare RealtimeKit
CLOUDFLARE_ACCOUNT_ID=8e6a443fe353bb4107a01c492d1f1fc6
CLOUDFLARE_REALTIMEKIT_APP_ID=5c9cdb5a-706c-48e9-94f9-3f1bbde8d0df
CLOUDFLARE_API_TOKEN=cfat_lRHSRipDMj5mgOaMAQfIFs7TqauKlJwlomWqg8dXe79e121f

# Recording bucket (same as R2 storage)
CLOUDFLARE_R2_BUCKET_NAME=youspeak
```

### Getting RealtimeKit Credentials

**App ID**: Available from your RealtimeKit app URL
**API Token**: Create at https://dash.cloudflare.com/profile/api-tokens
1. Click **"Create Token"** → **"Create Custom Token"**
2. **Permissions**: Account → Realtime → Edit
3. **Account Resources**: Select your account
4. Copy token immediately (shown only once!)

**Note**: During beta, RealtimeKit is FREE. Pricing starts after GA.

---

## Testing

### Local Development

1. Set environment variables in `.env`
2. Start backend: `uvicorn app.main:app --reload`
3. Create arena and start session
4. Call token endpoint: `POST /api/v1/arenas/{id}/audio/token`
5. Use token in RealtimeKit SDK

### Production Checklist

- [ ] Environment variables configured
- [ ] RealtimeKit app created in Cloudflare
- [ ] R2 bucket configured for recordings
- [ ] Token expiration tested (60 min)
- [ ] Role-based access verified
- [ ] Audio quality tested (<50ms latency)
- [ ] Recording workflow tested
- [ ] Cost monitoring enabled

---

## Troubleshooting

### Token Generation Fails

**Error**: `"Arena session is not active"`

**Fix**: Ensure arena `session_state` is `"initialized"` or `"live"`

```python
# Check arena session state
GET /api/v1/arenas/{id}/session
```

---

### Student Cannot Get Token

**Error**: `"Not authorized for this arena"`

**Fix**: Student must be admitted from waiting room first

```python
# Admit student
POST /api/v1/arenas/{id}/waiting-room/{entry_id}/admit
```

---

### Audio Not Working

1. **Check token expiration**: Tokens expire after 60 minutes
2. **Verify role**: Students should be `"audience"`, teachers `"host"`
3. **Check browser permissions**: WebRTC requires microphone access
4. **Network issues**: Ensure WebRTC traffic is not blocked

---

## References

- [Cloudflare RealtimeKit Documentation](https://developers.cloudflare.com/realtime/realtimekit/)
- [WebRTC API](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)
- [RealtimeKit SDK (npm)](https://www.npmjs.com/package/@cloudflare/realtimekit-sdk)
