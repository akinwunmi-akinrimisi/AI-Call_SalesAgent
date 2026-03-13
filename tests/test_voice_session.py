"""Integration tests for voice session lifecycle (WebSocket handler).

Tests the full handler orchestration with mocked external dependencies
(Firestore, Supabase, genai Live API). Validates setup, streaming loop
structure, cleanup, and error handling.

voice_handler.py uses genai.Client.aio.live.connect() directly (not ADK).
All genai interactions are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_voice_deps(monkeypatch):
    """Patch all external dependencies used by voice_handler and main."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "fake-service-key-for-testing")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-api-key-for-testing")


@pytest.fixture
def mock_lead():
    """Return a representative lead dict as Supabase would return."""
    return {
        "id": "lead-001",
        "name": "Adebayo Ogunlesi",
        "phone": "+2348012345678",
        "email": "adebayo@example.com",
        "source": "whatsapp",
        "status": "call_scheduled",
    }


@pytest.fixture
def mock_genai_session():
    """Create a mock genai live session that yields no responses."""
    session = AsyncMock()

    # receive() returns an async iterator that yields nothing
    async def _empty_receive():
        return
        yield  # noqa: RET504 -- makes this an async generator

    session.receive = _empty_receive
    session.send_client_content = AsyncMock()
    session.send_realtime_input = AsyncMock()
    session.send_tool_response = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def mock_genai_client(mock_genai_session):
    """Create a mock genai.Client whose aio.live.connect() returns mock session."""
    client = MagicMock()
    connect_cm = AsyncMock()
    connect_cm.__aenter__ = AsyncMock(return_value=mock_genai_session)
    connect_cm.__aexit__ = AsyncMock(return_value=None)
    client.aio.live.connect = MagicMock(return_value=connect_cm)
    return client


def _voice_session_patches(mock_lead_val, mock_genai_client_val):
    """Return a list of common patches for voice session tests."""
    return [
        patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead_val),
        patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB content"),
        patch("voice_handler.build_system_instruction", return_value="mock system instruction"),
        patch("voice_handler.get_firestore_client", return_value=MagicMock()),
        patch("voice_handler.genai.Client", return_value=mock_genai_client_val),
        patch("voice_handler.log_event", new_callable=AsyncMock),
        patch("voice_handler.process_call_end", new_callable=AsyncMock),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionCreationAndSetup:
    """Test that WebSocket setup correctly fetches lead, loads KB."""

    def test_session_lead_fetched_and_agent_created(
        self, _mock_voice_deps, mock_lead, mock_genai_client
    ):
        """Verify full setup: lead fetched, KB loaded, system instruction built."""
        patches = _voice_session_patches(mock_lead, mock_genai_client)
        with patches[0] as mock_fetch, patches[1] as mock_load_kb, \
             patches[2] as mock_build_si, patches[3], patches[4], \
             patches[5], patches[6]:
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            mock_fetch.assert_awaited_once_with("lead-001")
            mock_load_kb.assert_awaited_once()
            mock_build_si.assert_called_once_with(
                "Adebayo Ogunlesi", "mock KB content"
            )


class TestLeadNotFound:
    """Test that missing lead returns error and closes WebSocket."""

    def test_session_lead_not_found(self, _mock_voice_deps):
        """WebSocket should receive error JSON and close when lead not found."""
        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=None),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/nonexistent-lead") as ws:
                data = ws.receive_json()
                assert data["error"] == "Lead not found"
                assert data["lead_id"] == "nonexistent-lead"


class TestCleanupOnDisconnect:
    """Test that cleanup always runs, even on disconnect."""

    def test_process_call_end_called_on_disconnect(
        self, _mock_voice_deps, mock_lead, mock_genai_client
    ):
        """process_call_end must be called after disconnect to write outcome."""
        mock_process = AsyncMock()

        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.build_system_instruction", return_value="mock instruction"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.genai.Client", return_value=mock_genai_client),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", mock_process),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            # Verify cleanup was called
            mock_process.assert_awaited_once()
            call_session = mock_process.call_args[0][0]
            assert call_session.lead_id == "lead-001"
            assert call_session.lead_name == "Adebayo Ogunlesi"

    def test_watchdog_cancelled_on_disconnect(
        self, _mock_voice_deps, mock_lead, mock_genai_client
    ):
        """Watchdog task should be cancelled when call ends before 8.5 min."""
        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.build_system_instruction", return_value="mock instruction"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.genai.Client", return_value=mock_genai_client),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            # If we get here without hanging, watchdog was cancelled properly


class TestTranscriptionAccumulation:
    """Test that transcriptions are captured from genai events."""

    def test_transcriptions_accumulated_in_session(
        self, _mock_voice_deps, mock_lead
    ):
        """CallSession should accumulate user and agent transcripts from events."""
        # Create mock genai session that yields transcription events
        session = AsyncMock()

        msg1 = MagicMock()
        msg1.tool_call = None
        sc1 = MagicMock()
        sc1.model_turn = None
        sc1.input_transcription = MagicMock(text="Hello, is this Cloudboosta?")
        sc1.output_transcription = None
        msg1.server_content = sc1

        msg2 = MagicMock()
        msg2.tool_call = None
        sc2 = MagicMock()
        sc2.model_turn = None
        sc2.input_transcription = None
        sc2.output_transcription = MagicMock(text="Hi Adebayo! Yes, this is Sarah from Cloudboosta.")
        msg2.server_content = sc2

        async def _event_receive():
            for msg in [msg1, msg2]:
                yield msg

        session.receive = _event_receive
        session.send_client_content = AsyncMock()
        session.send_realtime_input = AsyncMock()

        client_mock = MagicMock()
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=session)
        connect_cm.__aexit__ = AsyncMock(return_value=None)
        client_mock.aio.live.connect = MagicMock(return_value=connect_cm)

        captured_sessions = []

        async def _capture_process(cs):
            captured_sessions.append(cs)

        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.build_system_instruction", return_value="mock instruction"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.genai.Client", return_value=client_mock),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", _capture_process),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            # Verify transcriptions were accumulated
            assert len(captured_sessions) == 1
            cs = captured_sessions[0]
            assert len(cs.user_transcripts) == 1
            assert cs.user_transcripts[0] == "Hello, is this Cloudboosta?"
            assert len(cs.agent_transcripts) == 1
            assert cs.agent_transcripts[0] == "Hi Adebayo! Yes, this is Sarah from Cloudboosta."


class TestHealthEndpoint:
    """Verify Phase 3 additions did not break existing health endpoint."""

    def test_health_returns_200(self, _mock_voice_deps):
        """GET /health should return 200 with status field."""
        from main import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["service"] == "cloudboosta-voice-agent"

    def test_health_endpoint_has_missing_config(self, _mock_voice_deps):
        """Health check should report missing Twilio config (expected in test env)."""
        from main import app

        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        # Twilio config not set in test env
        assert "missing_config" in data


class TestTranscriptForwarding:
    """Test that transcripts are forwarded as JSON on the WebSocket."""

    def test_transcript_forwarding_user(
        self, _mock_voice_deps, mock_lead
    ):
        """When genai emits input_transcription, voice handler sends JSON to WebSocket client."""
        session = AsyncMock()

        msg = MagicMock()
        msg.tool_call = None
        sc = MagicMock()
        sc.model_turn = None
        sc.input_transcription = MagicMock(text="I am interested in cloud security.")
        sc.output_transcription = None
        msg.server_content = sc

        async def _event_receive():
            yield msg

        session.receive = _event_receive
        session.send_client_content = AsyncMock()
        session.send_realtime_input = AsyncMock()

        client_mock = MagicMock()
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=session)
        connect_cm.__aexit__ = AsyncMock(return_value=None)
        client_mock.aio.live.connect = MagicMock(return_value=connect_cm)

        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.build_system_instruction", return_value="mock instruction"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.genai.Client", return_value=client_mock),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)
                # Receive the ready JSON first, then transcript
                msg1 = ws.receive_json()
                if msg1.get("type") == "ready":
                    msg_transcript = ws.receive_json()
                else:
                    msg_transcript = msg1
                assert msg_transcript["type"] == "transcript"
                assert msg_transcript["speaker"] == "user"
                assert msg_transcript["text"] == "I am interested in cloud security."

    def test_transcript_forwarding_agent(
        self, _mock_voice_deps, mock_lead
    ):
        """When genai emits output_transcription, voice handler sends JSON to WebSocket client."""
        session = AsyncMock()

        msg = MagicMock()
        msg.tool_call = None
        sc = MagicMock()
        sc.model_turn = None
        sc.input_transcription = None
        sc.output_transcription = MagicMock(text="That is a great choice! Let me tell you more.")
        msg.server_content = sc

        async def _event_receive():
            yield msg

        session.receive = _event_receive
        session.send_client_content = AsyncMock()
        session.send_realtime_input = AsyncMock()

        client_mock = MagicMock()
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=session)
        connect_cm.__aexit__ = AsyncMock(return_value=None)
        client_mock.aio.live.connect = MagicMock(return_value=connect_cm)

        with (
            patch("voice_handler.fetch_lead", new_callable=AsyncMock, return_value=mock_lead),
            patch("voice_handler.load_knowledge_base", new_callable=AsyncMock, return_value="mock KB"),
            patch("voice_handler.build_system_instruction", return_value="mock instruction"),
            patch("voice_handler.get_firestore_client", return_value=MagicMock()),
            patch("voice_handler.genai.Client", return_value=client_mock),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)
                msg1 = ws.receive_json()
                if msg1.get("type") == "ready":
                    msg_transcript = ws.receive_json()
                else:
                    msg_transcript = msg1
                assert msg_transcript["type"] == "transcript"
                assert msg_transcript["speaker"] == "agent"
                assert msg_transcript["text"] == "That is a great choice! Let me tell you more."


class TestFetchLead:
    """Unit tests for the fetch_lead helper function."""

    async def test_fetch_lead_returns_lead_dict(self, _mock_voice_deps):
        """fetch_lead should return the lead dict when Supabase returns data."""
        from voice_handler import fetch_lead

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "lead-abc", "name": "Test Lead", "status": "new"}
        ]
        mock_response.raise_for_status = MagicMock()

        with (
            patch("voice_handler.httpx.AsyncClient") as mock_client_cls,
            patch("voice_handler.log_event", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await fetch_lead("lead-abc")
            assert result is not None
            assert result["id"] == "lead-abc"
            assert result["name"] == "Test Lead"

    async def test_fetch_lead_returns_none_for_empty(self, _mock_voice_deps):
        """fetch_lead should return None when Supabase returns empty array."""
        from voice_handler import fetch_lead

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with (
            patch("voice_handler.httpx.AsyncClient") as mock_client_cls,
            patch("voice_handler.log_event", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await fetch_lead("nonexistent")
            assert result is None
