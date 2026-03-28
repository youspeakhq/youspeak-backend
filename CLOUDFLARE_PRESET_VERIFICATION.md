# Cloudflare RealtimeKit Preset Name Verification

**Date:** 2026-03-28
**Status:** ✅ VERIFIED

## Summary

Our current implementation uses the **CORRECT** preset names for Cloudflare RealtimeKit. The underscore format (`group_call_host`, `group_call_participant`) is what works with our Cloudflare app.

## Test Results

### ✅ Working Presets (Underscore Format)
- `group_call_host` - HTTP 201, token generated successfully
- `group_call_participant` - HTTP 201, token generated successfully

### ❌ Failed Presets (Hyphen Format - Documentation Examples)
- `group-call-host` - HTTP 404: "ResourceNotFound: No preset found with name group-call-host"
- `group-call-participant` - HTTP 404: "ResourceNotFound: No preset found with name group-call-participant"
- `webinar-host` - HTTP 404: "ResourceNotFound: No preset found with name webinar-host"
- `webinar-participant` - HTTP 404: "ResourceNotFound: No preset found with name webinar-participant"

## Analysis

### Why the Discrepancy?

The Cloudflare documentation shows examples using **hyphen format** (e.g., `group-call-host`, `webinar-host`), but our app uses **underscore format** (e.g., `group_call_host`).

**Reason:** Preset names are **app-specific**, not universal. They are created when you set up a RealtimeKit app in the Cloudflare dashboard. The documentation shows generic examples, but the actual preset names depend on how they were configured for each app.

From Cloudflare docs:
> "A set of default presets are created for you, when you create an app via the Cloudflare dashboard"

### Our App Configuration

**App ID:** `8a566efb-7b21-4050-8150-2e7e01d660f3`
**Account ID:** `a9edc14299c7518ddfbdd714348ceb61`
**Environment:** Staging

**Available Presets:**
1. **`group_call_host`** (Preset ID: `873ba0af-4098-468e-9390-efc66e5e3e56`)
   - Used for: Teachers, School Admins
   - Permissions: Can publish audio, moderate, kick participants

2. **`group_call_participant`** (Preset ID: `e140b8e2-1c1c-401e-8633-35d0d92ac806`)
   - Used for: Students
   - Permissions: Can publish audio, listen to others

## Code Verification

### Backend Implementation ✓
**File:** `app/services/cloudflare_realtimekit_service.py:111`

```python
async def add_participant(
    self,
    meeting_id: str,
    user_id: UUID,
    user_name: str,
    preset_name: str = "group_call_participant"  # ✓ CORRECT (underscore)
) -> Optional[Dict[str, Any]]:
```

### Endpoint Usage ✓
**File:** `app/api/v1/endpoints/arenas.py:750,760`

```python
if is_teacher:
    preset_name = "group_call_host"  # ✓ CORRECT (underscore)
else:
    preset_name = "group_call_participant"  # ✓ CORRECT (underscore)
```

## Testing Methodology

### Direct API Test
**Script:** `scripts/test_cloudflare_presets_direct.py`

1. Fetched credentials from AWS Secrets Manager (staging)
2. Created a test meeting via Cloudflare API
3. Tested adding participants with 6 different preset name formats
4. Recorded HTTP status codes and responses

### Test Commands
```bash
# Fetch credentials
aws secretsmanager get-secret-value --secret-id youspeak/cloudflare-account-id-staging --region us-east-1
aws secretsmanager get-secret-value --secret-id youspeak/cloudflare-realtimekit-app-id-staging --region us-east-1
aws secretsmanager get-secret-value --secret-id youspeak/cloudflare-api-token-staging --region us-east-1

# Run test
python3 scripts/test_cloudflare_presets_direct.py
```

## Recommendations

### 1. **No Code Changes Needed** ✅
The current implementation is correct and working.

### 2. **Documentation is Accurate** ✅
`REALTIMEKIT_EXPLANATION.md` has been updated with:
- Correct preset names (`group_call_host`, `group_call_participant`)
- Accurate response schemas
- Clear explanations of student audio permissions

### 3. **Production Verification**
When deploying to production, verify the production Cloudflare app also uses the same preset names. If the production app was configured differently, the preset names might differ.

```bash
# Check production presets
aws secretsmanager get-secret-value --secret-id youspeak/cloudflare-account-id-production --region us-east-1
# Then run the test script against production credentials
```

## Conclusion

✅ **Current code is CORRECT**
✅ **Uses underscore format: `group_call_host`, `group_call_participant`**
✅ **Verified against live Cloudflare API**
✅ **Documentation updated to match actual implementation**

The discrepancy between documentation examples (hyphen format) and our implementation (underscore format) is expected and normal. Preset names are app-specific configuration, not API standards.

## Related Files

- **Implementation:** `app/services/cloudflare_realtimekit_service.py`
- **Endpoint:** `app/api/v1/endpoints/arenas.py`
- **Documentation:** `REALTIMEKIT_EXPLANATION.md`
- **Test Script:** `scripts/test_cloudflare_presets_direct.py`
- **Previous Analysis:** `REALTIMEKIT_GAPS_ANALYSIS.md`
