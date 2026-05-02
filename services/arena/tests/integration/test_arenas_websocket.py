"""Integration tests: Arena WebSocket & Live Sessions (Phase 3).

Tests WebSocket real-time communication, authentication, authorization,
rate limiting, and session control.

Requirements tested:
- WS /arenas/{id}/live: Real-time arena session WebSocket
- POST /arenas/{id}/start: Start live session
- POST /arenas/{id}/end: End live session
- GET /arenas/{id}/session: Get current session state

Note: Full WebSocket tests require websockets library and live server.
Session control REST API tests run normally.
WebSocket connection tests are marked for manual/E2E testing.
"""

import pytest
import asyncio
import json
from httpx import AsyncClient

from ..conftest import FAKE_CLASS_ID, requires_seeded_data

# All tests in this module need a real seeded teacher+class in the live DB
pytestmark = requires_seeded_data

# Mark WebSocket tests as requiring live server
requires_websocket = pytest.mark.skipif(
    True,
    reason="WebSocket tests require live server and websockets library"
)


@pytest.fixture
async def initialized_arena_for_ws(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """Create and initialize an arena ready for WebSocket testing."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"][:2]

    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "WebSocket Test Arena",
            "criteria": {"Clarity": 50, "Confidence": 50},
            "rules": ["Rule 1"],
        },
    )
    assert resp.status_code == 200, resp.text
    arena_id = resp.json()["data"]["id"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/initialize",
        headers=headers,
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
        },
    )
    assert resp.status_code == 200, resp.text

    return {"arena_id": arena_id, "headers": headers, "student_ids": student_ids}


@pytest.fixture
async def live_arena(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena_for_ws: dict,
):
    """Create an arena in 'live' state ready for WebSocket connections."""
    arena_id = initialized_arena_for_ws["arena_id"]
    headers = initialized_arena_for_ws["headers"]

    resp = await async_client.post(f"{api_base}/arenas/{arena_id}/start", headers=headers)
    assert resp.status_code == 200, resp.text

    return initialized_arena_for_ws


@pytest.fixture
def admitted_student_token(teacher_with_class_and_students: dict) -> str:
    """Return a mock admitted student token (WebSocket tests are skipped anyway)."""
    from services.arena.security import create_access_token
    student_id = teacher_with_class_and_students["student_ids"][0]
    return create_access_token({"sub": student_id, "type": "access"})


# ============================================================================
# Session Control Tests (REST API)
# ============================================================================


@pytest.mark.asyncio
async def test_start_session_success(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena_for_ws: dict,
):
    """
    GIVEN: An initialized arena
    WHEN: Teacher starts session
    THEN: Returns 200, session_state transitions to 'live'
    """
    arena_id = initialized_arena_for_ws["arena_id"]
    headers = initialized_arena_for_ws["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/start",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["session_state"] == "live"
    assert body["data"]["arena_id"] == arena_id


@pytest.mark.asyncio
async def test_start_session_404_when_not_found(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    GIVEN: Non-existent arena
    WHEN: Teacher tries to start session
    THEN: Returns 404
    """
    resp = await async_client.post(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001/start",
        headers=teacher_headers,
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_session_requires_teacher_auth(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena_for_ws: dict,
):
    """
    GIVEN: An initialized arena
    WHEN: Unauthenticated request to start session
    THEN: Returns 401
    """
    arena_id = initialized_arena_for_ws["arena_id"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/start",
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_end_session_success(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena session
    WHEN: Teacher ends session
    THEN: Returns 200, session_state transitions to 'completed'
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/end",
        headers=headers,
        json={},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["session_state"] == "completed"


@pytest.mark.asyncio
async def test_end_session_with_reason(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena session
    WHEN: Teacher ends session with reason
    THEN: Returns 200, session_state transitions to 'cancelled'
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/end",
        headers=headers,
        json={"reason": "Technical issues"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["session_state"] == "cancelled"


@pytest.mark.asyncio
async def test_get_session_state(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena session
    WHEN: Client requests session state
    THEN: Returns 200 with current session details
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]

    resp = await async_client.get(
        f"{api_base}/arenas/{arena_id}/session",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["session_state"] == "live"
    assert body["data"]["arena_id"] == arena_id
    assert "participants" in body["data"]


# ============================================================================
# WebSocket Authentication Tests
# ============================================================================


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_without_token_rejected(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena
    WHEN: Client connects to WebSocket without token
    THEN: Connection closes with code 4001 (Unauthorized)
    """
    arena_id = live_arena["arena_id"]

    # Extract base URL and construct WebSocket URL
    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live"

    with pytest.raises(Exception) as exc_info:
        async with async_client.websocket_connect(ws_url) as websocket:
            # Should not reach here
            await websocket.receive_text()

    # Verify connection was rejected (will raise WebSocketDisconnect or similar)
    assert exc_info.value is not None


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_with_invalid_token_rejected(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena
    WHEN: Client connects with invalid token
    THEN: Connection closes with code 4001 (Unauthorized)
    """
    arena_id = live_arena["arena_id"]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token=invalid_token"

    with pytest.raises(Exception) as exc_info:
        async with async_client.websocket_connect(ws_url) as websocket:
            await websocket.receive_text()

    assert exc_info.value is not None


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_teacher_success(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena
    WHEN: Teacher connects with valid token
    THEN: Connection succeeds, receives session_state event
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]

    # Extract token from headers
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Should receive initial session_state event
        data = await websocket.receive_text()
        message = json.loads(data)

        assert message["event_type"] == "session_state"
        assert message["data"]["arena_id"] == arena_id
        assert message["data"]["session_state"] == "live"


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_admitted_student_success(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
    admitted_student_token: str,
):
    """
    GIVEN: A live arena
    WHEN: Admitted student connects with valid token
    THEN: Connection succeeds, receives session_state event
    """
    arena_id = live_arena["arena_id"]
    token = admitted_student_token

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Should receive initial session_state event
        data = await websocket.receive_text()
        message = json.loads(data)

        assert message["event_type"] == "session_state"
        assert message["data"]["session_state"] == "live"


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_unadmitted_student_rejected(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
    unique_suffix: str,
    registered_school: dict,
):
    """
    GIVEN: A live arena
    WHEN: Unadmitted student connects
    THEN: Connection closes with code 4003 (Not authorized)
    """
    arena_id = live_arena["arena_id"]

    # Create student but DON'T admit to arena or enroll in class
    # # from tests.conftest import create_student_direct

    student_email = f"unadmitted_{unique_suffix}@test.com"
    # Create student without class enrollment (pass empty class_id)
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "Unadmitted",
            "last_name": "Student",
            "email": student_email,
            "lang_id": 1,
            "password": "Pass123!",
        },
    )
    assert resp.status_code == 200
    student_id = resp.json()["data"]["id"]

    # Login student
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": student_email, "password": "Pass123!"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]

    # Try to connect (should be rejected)
    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    with pytest.raises(Exception) as exc_info:
        async with async_client.websocket_connect(ws_url) as websocket:
            await websocket.receive_text()

    assert exc_info.value is not None


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_to_non_live_arena_rejected(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena_for_ws: dict,
):
    """
    GIVEN: An initialized (not live) arena
    WHEN: Teacher tries to connect via WebSocket
    THEN: Connection closes with code 4003 (Arena not live)
    """
    arena_id = initialized_arena_for_ws["arena_id"]
    headers = initialized_arena_for_ws["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    with pytest.raises(Exception) as exc_info:
        async with async_client.websocket_connect(ws_url) as websocket:
            await websocket.receive_text()

    assert exc_info.value is not None


# ============================================================================
# WebSocket Event Broadcasting Tests
# ============================================================================


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_speaking_started_broadcast(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: Two connected WebSocket clients
    WHEN: Client 1 sends speaking_started event
    THEN: Client 2 receives speaking_update broadcast
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    # Connect two clients
    async with async_client.websocket_connect(ws_url) as ws1:
        async with async_client.websocket_connect(ws_url) as ws2:
            # Clear initial session_state messages
            await ws1.receive_text()
            await ws2.receive_text()

            # Client 1 sends speaking_started
            await ws1.send_text(json.dumps({
                "event_type": "speaking_started"
            }))

            # Both clients should receive speaking_update
            # (ws1 gets its own broadcast, ws2 gets broadcast from server)
            data1 = await ws1.receive_text()
            data2 = await ws2.receive_text()

            msg1 = json.loads(data1)
            msg2 = json.loads(data2)

            assert msg1["event_type"] == "speaking_update"
            assert msg1["data"]["is_speaking"] is True

            assert msg2["event_type"] == "speaking_update"
            assert msg2["data"]["is_speaking"] is True


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_reaction_broadcast(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: Two connected WebSocket clients
    WHEN: Client 1 sends reaction_sent event
    THEN: Client 2 receives reaction_broadcast (but not client 1)
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as ws1:
        async with async_client.websocket_connect(ws_url) as ws2:
            # Clear initial session_state messages
            await ws1.receive_text()
            await ws2.receive_text()

            # Client 1 sends reaction
            await ws1.send_text(json.dumps({
                "event_type": "reaction_sent",
                "reaction_type": "thumbs_up"
            }))

            # Client 2 should receive broadcast
            data2 = await ws2.receive_text()
            msg2 = json.loads(data2)

            assert msg2["event_type"] == "reaction_broadcast"
            assert msg2["data"]["reaction_type"] == "thumbs_up"

            # Client 1 should NOT receive (excluded from broadcast)
            # Try to receive with timeout
            try:
                await asyncio.wait_for(ws1.receive_text(), timeout=0.5)
                assert False, "Client 1 should not receive its own reaction"
            except asyncio.TimeoutError:
                pass  # Expected


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_audio_muted_broadcast(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: Two connected WebSocket clients
    WHEN: Client 1 sends audio_muted event
    THEN: Both clients receive engagement_update broadcast
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as ws1:
        async with async_client.websocket_connect(ws_url) as ws2:
            # Clear initial session_state messages
            await ws1.receive_text()
            await ws2.receive_text()

            # Client 1 sends audio_muted
            await ws1.send_text(json.dumps({
                "event_type": "audio_muted"
            }))

            # Both clients should receive engagement_update
            data1 = await ws1.receive_text()
            data2 = await ws2.receive_text()

            msg1 = json.loads(data1)
            msg2 = json.loads(data2)

            assert msg1["event_type"] == "engagement_update"
            assert msg1["data"]["audio_muted"] is True

            assert msg2["event_type"] == "engagement_update"
            assert msg2["data"]["audio_muted"] is True


# ============================================================================
# WebSocket Rate Limiting Tests
# ============================================================================


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_message_rate_limit_enforced(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A connected WebSocket client
    WHEN: Client sends more than 30 messages in 60 seconds
    THEN: Connection closes with code 4008 (Rate limit exceeded)
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Clear initial session_state message
        await websocket.receive_text()

        # Send 31 messages rapidly (exceeds 30/minute limit)
        for i in range(31):
            await websocket.send_text(json.dumps({
                "event_type": "speaking_started"
            }))

        # Connection should be closed by server
        # Try to receive, should raise exception
        with pytest.raises(Exception):
            # Give server time to close connection
            await asyncio.sleep(0.1)
            await websocket.receive_text()


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_connection_limit_per_arena(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A live arena
    WHEN: Attempt to open 101 connections (exceeds MAX_CONNECTIONS_PER_ARENA=100)
    THEN: 101st connection is rejected with code 4008

    Note: This test is slow (opens 100 connections), mark as slow or skip in fast test runs
    """
    pytest.skip("Slow test: Opens 100 connections. Run manually for full validation.")

    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    connections = []
    try:
        # Open 100 connections (should succeed)
        for i in range(100):
            ws = await async_client.websocket_connect(ws_url)
            connections.append(ws)
            await ws.receive_text()  # Clear initial message

        # 101st connection should fail
        with pytest.raises(Exception):
            ws = await async_client.websocket_connect(ws_url)
            connections.append(ws)

    finally:
        # Clean up connections
        for ws in connections:
            try:
                await ws.close()
            except:
                pass


# ============================================================================
# WebSocket Session End Broadcasting Tests
# ============================================================================


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_receives_session_ended_event(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A connected WebSocket client
    WHEN: Teacher ends session
    THEN: WebSocket client receives session_ended event
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Clear initial session_state message
        await websocket.receive_text()

        # Teacher ends session via REST API
        resp = await async_client.post(
            f"{api_base}/arenas/{arena_id}/end",
            headers=headers,
            json={"reason": "Test end"},
        )
        assert resp.status_code == 200

        # WebSocket should receive session_ended event
        data = await websocket.receive_text()
        message = json.loads(data)

        assert message["event_type"] == "session_ended"
        assert message["data"]["arena_id"] == arena_id
        assert message["data"]["reason"] == "Test end"


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_invalid_json_ignored(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A connected WebSocket client
    WHEN: Client sends invalid JSON
    THEN: Connection remains open, invalid message is ignored
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Clear initial session_state message
        await websocket.receive_text()

        # Send invalid JSON
        await websocket.send_text("invalid json {{{")

        # Connection should remain open
        # Send valid message to verify
        await websocket.send_text(json.dumps({
            "event_type": "speaking_started"
        }))

        # Should receive broadcast
        data = await websocket.receive_text()
        message = json.loads(data)
        assert message["event_type"] == "speaking_update"


@pytest.mark.asyncio
@requires_websocket
async def test_websocket_unknown_event_type_ignored(
    async_client: AsyncClient,
    api_base: str,
    live_arena: dict,
):
    """
    GIVEN: A connected WebSocket client
    WHEN: Client sends unknown event_type
    THEN: Connection remains open, unknown event is ignored
    """
    arena_id = live_arena["arena_id"]
    headers = live_arena["headers"]
    token = headers["Authorization"].split(" ")[1]

    base_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/arenas/{arena_id}/live?token={token}"

    async with async_client.websocket_connect(ws_url) as websocket:
        # Clear initial session_state message
        await websocket.receive_text()

        # Send unknown event type
        await websocket.send_text(json.dumps({
            "event_type": "unknown_event"
        }))

        # Connection should remain open
        # Send valid message to verify
        await websocket.send_text(json.dumps({
            "event_type": "speaking_started"
        }))

        # Should receive broadcast
        data = await websocket.receive_text()
        message = json.loads(data)
        assert message["event_type"] == "speaking_update"
