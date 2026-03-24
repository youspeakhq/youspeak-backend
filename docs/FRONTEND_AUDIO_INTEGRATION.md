# Frontend Audio Integration Guide

**Status**: Backend implementation complete. Presets need to be created tomorrow.

## Quick Start

Audio conferencing for Arena sessions is implemented using **Cloudflare RealtimeKit** - a WebRTC-based audio infrastructure.

### What You Need to Know

1. **Backend is ready** - Audio token API endpoint is deployed and working
2. **Presets not created yet** - Will be done tomorrow (teacher-host & student-audience)
3. **Once presets are ready** - You can start frontend integration immediately

---

## Architecture Overview

```
Frontend → POST /api/v1/arenas/{id}/audio/token → Get authToken
         → Connect RealtimeKit SDK with token
         → Audio flows through Cloudflare edge (NOT our backend)
```

**Two separate systems:**
- **WebSocket** (`/arenas/{id}/live`) - Session coordination, reactions, speaking indicators
- **RealtimeKit** - Actual audio transmission

Both are required for full functionality.

---

## API Endpoint

### Generate Audio Token

**Endpoint**: `POST /api/v1/arenas/{arena_id}/audio/token`

**Headers**:
```
Authorization: Bearer <JWT_TOKEN>
```

**Request**: No body needed

**Response**:
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "participant_id": "550e8400-e29b-41d4-a716-446655440000",
    "meeting_id": "5c9cdb5a-706c-48e9-94f9-3f1bbde8d0df",
    "preset_name": "teacher-host",
    "name": "John Doe"
  },
  "message": "Audio token generated (teacher-host)"
}
```

**Fields**:
- `token` - Use this with RealtimeKit SDK (Cloudflare authToken)
- `meeting_id` - RealtimeKit meeting ID
- `participant_id` - Your participant ID in the meeting
- `preset_name` - Either "teacher-host" (can speak) or "student-audience" (listen-only)
- `name` - Display name for this participant

**Requirements**:
- Arena session must be in `"initialized"` or `"live"` state
- Students must be admitted from waiting room first
- Teachers get `"teacher-host"` preset (can publish audio)
- Students get `"student-audience"` preset (receive-only)

**Errors**:
- `401` - Not authenticated
- `403` - Not authorized for this arena (student not admitted)
- `404` - Arena not found
- `400` - Arena session not active

---

## Frontend Integration

### Installation

```bash
npm install @cloudflare/realtimekit-sdk
# or
yarn add @cloudflare/realtimekit-sdk
```

Works on both **React Native** and **Web** (uses standard WebRTC).

---

### React Native Example

```typescript
import { RealtimeKitClient } from '@cloudflare/realtimekit-sdk';
import { useState, useEffect } from 'react';

interface UseAudioProps {
  arenaId: string;
  accessToken: string;
}

export const useArenaAudio = ({ arenaId, accessToken }: UseAudioProps) => {
  const [client, setClient] = useState<RealtimeKitClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [isHost, setIsHost] = useState(false);

  useEffect(() => {
    let rtcClient: RealtimeKitClient | null = null;

    const initAudio = async () => {
      try {
        // 1. Get audio token from backend
        const response = await fetch(
          `${API_URL}/api/v1/arenas/${arenaId}/audio/token`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${accessToken}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to get audio token');
        }

        const { data } = await response.json();
        const { token, meeting_id, preset_name } = data;

        // Determine if user can publish audio
        setIsHost(preset_name === 'teacher-host');

        // 2. Initialize RealtimeKit client
        rtcClient = new RealtimeKitClient({
          token,
          roomId: meeting_id,
        });

        // 3. Listen for remote audio tracks (other participants)
        rtcClient.on('track', (track, participant) => {
          console.log(`Received audio from: ${participant.name}`);

          // Automatically play remote audio
          const audio = new Audio();
          audio.srcObject = new MediaStream([track]);
          audio.play().catch(err => {
            console.error('Failed to play audio:', err);
          });
        });

        // 4. Handle participant events
        rtcClient.on('participantJoined', (participant) => {
          console.log(`${participant.name} joined`);
        });

        rtcClient.on('participantLeft', (participant) => {
          console.log(`${participant.name} left`);
        });

        // 5. Connect to audio room
        await rtcClient.connect();
        setClient(rtcClient);
        setIsConnected(true);

        console.log('Audio connected successfully');

      } catch (error) {
        console.error('Failed to initialize audio:', error);
        setIsConnected(false);
      }
    };

    initAudio();

    // Cleanup on unmount
    return () => {
      if (rtcClient) {
        rtcClient.disconnect();
      }
    };
  }, [arenaId, accessToken]);

  // Mute/unmute controls (only works for hosts)
  const toggleMute = async () => {
    if (!client || !isHost) return;

    try {
      if (isMuted) {
        await client.publishAudio();
        setIsMuted(false);
      } else {
        await client.unpublishAudio();
        setIsMuted(true);
      }
    } catch (error) {
      console.error('Failed to toggle mute:', error);
    }
  };

  return {
    isConnected,
    isMuted,
    toggleMute,
    isHost,  // true if teacher (can speak), false if student (listen-only)
  };
};
```

---

### Usage in Component

```typescript
import { useArenaAudio } from './hooks/useArenaAudio';

export const ArenaLiveSession = ({ arenaId }: { arenaId: string }) => {
  const { accessToken } = useAuth();
  const { isConnected, isMuted, toggleMute, isHost } = useArenaAudio({
    arenaId,
    accessToken,
  });

  return (
    <View>
      <Text>Audio: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}</Text>

      {isHost && (
        <Button onPress={toggleMute}>
          {isMuted ? '🎤 Unmute' : '🔇 Mute'}
        </Button>
      )}

      {!isHost && (
        <Text>Listening mode - You cannot speak</Text>
      )}
    </View>
  );
};
```

---

## Role-Based Permissions

### Teacher (Host)
- **Preset**: `teacher-host`
- **Can publish audio**: Yes (speak)
- **Can receive audio**: Yes (hear others)
- **Cost**: $0.0050/min ($3.00 per hour)

### Student (Audience)
- **Preset**: `student-audience`
- **Can publish audio**: No (listen-only)
- **Can receive audio**: Yes (hear teacher)
- **Cost**: $0.0005/min ($0.30 per hour)

**Cost optimization**: Students are 10x cheaper because they're in receive-only mode.

**Example**: 1 teacher + 49 students for 60 minutes = $17.70 total
- Teacher: 1 × $3.00 = $3.00
- Students: 49 × $0.30 = $14.70

---

## Important Notes

### 1. Presets Must Be Created First

**BEFORE frontend integration will work**, these presets must be created in Cloudflare dashboard:

1. **teacher-host** - Webinar Host (can publish audio)
2. **student-audience** - Webinar Participant (receive-only)

**Status**: Not created yet. Will be done tomorrow.

**Location**: Cloudflare Dashboard → RealtimeKit → App → Presets tab

Once presets are created, the backend API will work immediately.

---

### 2. WebSocket vs Audio

Don't confuse these two systems:

**WebSocket** (`/arenas/{id}/live`):
- Session state (started, ended)
- Participant list
- Speaking indicators (visual only)
- Reactions (emojis)
- NOT actual audio

**RealtimeKit**:
- Actual audio transmission
- WebRTC media streams
- Voice activity detection
- Mute/unmute controls

---

### 3. Testing Checklist

Once presets are created:

- [ ] Call audio token endpoint successfully
- [ ] Receive valid authToken in response
- [ ] Connect RealtimeKit SDK with token
- [ ] Verify teacher can publish audio (unmute works)
- [ ] Verify student cannot publish audio (listen-only)
- [ ] Verify audio latency <300ms
- [ ] Test with multiple participants
- [ ] Test reconnection after network interruption

---

## Troubleshooting

### "Arena session is not active"
**Fix**: Ensure arena `session_state` is `"initialized"` or `"live"` before requesting token.

### "Not authorized for this arena"
**Fix**: Student must be admitted from waiting room first.

### "Preset not found"
**Fix**: Presets must be created in Cloudflare dashboard (doing tomorrow).

### No audio heard
1. Check browser/app microphone permissions
2. Verify token is not expired
3. Check network allows WebRTC traffic
4. Ensure remote participant has published audio

### Student can't unmute
**Expected behavior**: Students are audience-only. Only teachers can publish audio.

---

## Next Steps for Frontend

1. **Wait for presets** - Backend team will create them tomorrow
2. **Install SDK** - `npm install @cloudflare/realtimekit-sdk`
3. **Implement audio hook** - Use example code above
4. **Test with teacher account** - Should be able to speak
5. **Test with student account** - Should be listen-only
6. **Add mute/unmute UI** - Only show for teachers

---

## Additional Resources

- [Cloudflare RealtimeKit Docs](https://developers.cloudflare.com/realtime/realtimekit/)
- [WebRTC API Reference](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)
- [RealtimeKit SDK (npm)](https://www.npmjs.com/package/@cloudflare/realtimekit-sdk)

---

## Questions?

Contact backend team for:
- API endpoint issues
- Token generation problems
- Preset configuration questions
- Cost optimization strategies

---

**Last Updated**: 2026-03-24
**Backend Status**: ✅ Complete (API deployed, secrets in AWS)
**Presets Status**: ⏳ Pending (will be created tomorrow)
**Frontend Status**: ⏳ Ready to start after presets are created
