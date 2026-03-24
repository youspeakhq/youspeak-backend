# RealtimeKit Preset Setup Guide

## What are Presets?

Presets define the **permissions and capabilities** of participants in a RealtimeKit meeting. They control:
- Who can publish audio/video (speak/present)
- Who can only receive (listen/watch)
- UI layout and controls
- Meeting type (video call, audio call, webinar)

## Required Presets for YouSpeak

You need to create **2 presets** in your RealtimeKit app:

### 1. `teacher-host` (Webinar Host)
- **Role**: Host/Presenter
- **Permissions**: Can publish audio (speak)
- **Use case**: Teachers moderating Arena sessions

### 2. `student-audience` (Webinar Participant)
- **Role**: Audience/Listener
- **Permissions**: Receive-only (listen, cannot speak)
- **Use case**: Students participating in Arena sessions

---

## How to Create Presets

### Step 1: Navigate to Presets Tab

1. Go to your RealtimeKit app dashboard:
   https://dash.cloudflare.com/8e6a443fe353bb4107a01c492d1f1fc6/realtime/apps/5c9cdb5a-706c-48e9-94f9-3f1bbde8d0df

2. Click the **"Presets"** tab (you were already on this tab in your screenshot!)

---

### Step 2: Create "teacher-host" Preset

1. Click **"Create Preset"** or similar button

2. Fill in the form:

**Preset Name**: `teacher-host`

**Preset Type**: Select **"Webinar Host"** or **"Group Call Host"**
- Allows publishing audio
- Full moderator controls

**Audio Settings**:
- ✅ **Can publish audio** (enabled)
- ✅ **Can receive audio** (enabled)

**Video Settings** (optional, you can disable if audio-only):
- ❌ Can publish video (disabled for audio-only)
- ❌ Can receive video (disabled for audio-only)

**Other Settings**:
- ✅ Can mute others (if available)
- ✅ Can remove participants (if available)

3. Click **"Save"** or **"Create"**

---

### Step 3: Create "student-audience" Preset

1. Click **"Create Preset"** again

2. Fill in the form:

**Preset Name**: `student-audience`

**Preset Type**: Select **"Webinar Participant"** or **"Audience"**
- Receive-only mode
- No publishing capabilities

**Audio Settings**:
- ❌ **Can publish audio** (disabled)
- ✅ **Can receive audio** (enabled)

**Video Settings**:
- ❌ Can publish video (disabled)
- ❌ Can receive video (disabled)

**Other Settings**:
- ❌ Can mute others (disabled)
- ❌ Can remove participants (disabled)
- ✅ Can send reactions (optional, if you want emoji reactions)

3. Click **"Save"** or **"Create"**

---

## Verifying Presets

After creation, you should see both presets listed:

```
Presets (2)
├── teacher-host        (Webinar Host - Can publish)
└── student-audience    (Webinar Participant - Receive only)
```

---

## How Presets are Used in the API

When a user requests an audio token, the backend automatically assigns the correct preset:

```python
# Backend logic (already implemented)
if user.role == TEACHER:
    preset_name = "teacher-host"      # Can speak
else:
    preset_name = "student-audience"  # Can only listen
```

The frontend receives the token and joins with those permissions automatically.

---

## Cost Implications

**This is why presets matter for cost:**

| Preset            | Cost/min/user | 1-hour session |
|-------------------|---------------|----------------|
| teacher-host      | $0.0050       | $3.00          |
| student-audience  | $0.0005       | $0.30          |

**Example**: 1 teacher + 49 students for 60 minutes
- Teacher (host): $3.00
- Students (audience): 49 × $0.30 = $14.70
- **Total**: $17.70

If all 50 users were "hosts": 50 × $3.00 = **$150** ❌

**Using presets correctly saves 8x in costs!**

---

## Testing the Setup

After creating both presets, test the flow:

1. **Start backend** with environment variables set
2. **Create an arena** and start session
3. **Request audio token** as teacher: `POST /api/v1/arenas/{id}/audio/token`
4. **Response should include**: `"preset_name": "teacher-host"`
5. **Request as student**: Should get `"preset_name": "student-audience"`

---

## Troubleshooting

### Error: "Preset not found"

**Cause**: Preset name doesn't match exactly

**Fix**: Ensure preset names are:
- `teacher-host` (exact spelling, lowercase, hyphen)
- `student-audience` (exact spelling, lowercase, hyphen)

### Error: "Cannot publish audio"

**Cause**: Student assigned "student-audience" preset (correct behavior)

**Expected**: Students should only be able to listen, not speak by default

---

## Next Steps

After creating presets:
1. ✅ Add environment variables to `.env`
2. ✅ Run database migration: `alembic upgrade head`
3. ✅ Test audio token endpoint
4. ✅ Integrate frontend SDK

Full integration guide: `AUDIO_REALTIMEKIT_INTEGRATION.md`
