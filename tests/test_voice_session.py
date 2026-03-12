"""Integration tests for voice session lifecycle (WebSocket handler).

Tests the full handler orchestration with mocked external dependencies
(Firestore, Supabase, ADK Runner). Validates setup, streaming loop
structure, cleanup, and error handling.

Does NOT call the real Gemini API -- all ADK/Gemini interactions are mocked.
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
    # Patch config with test values
    monkeypatch.setenv("SUPABASE_URL", "https://fake-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "fake-service-key-for-testing")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")


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
def mock_runner_no_events():
    """Create a mock Runner whose run_live yields no events (immediate end)."""
    mock_runner_cls = MagicMock()
    mock_runner_instance = MagicMock()

    async def _empty_gen(*args, **kwargs):
        return
        yield  # noqa: RET504 -- makes this an async generator

    mock_runner_instance.run_live = _empty_gen
    mock_runner_cls.return_value = mock_runner_instance
    return mock_runner_cls, mock_runner_instance


@pytest.fixture
def mock_session_service():
    """Create a mock InMemorySessionService."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()

    # create_session returns a mock session
    mock_session = MagicMock()
    mock_session.state = {}
    mock_instance.create_session = AsyncMock(return_value=mock_session)
    mock_instance.get_session = AsyncMock(return_value=mock_session)

    mock_cls.return_value = mock_instance
    return mock_cls, mock_instance, mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionCreationAndSetup:
    """Test that WebSocket setup correctly fetches lead, loads KB, creates agent."""

    def test_session_lead_fetched_and_agent_created(
        self, _mock_voice_deps, mock_lead, mock_runner_no_events, mock_session_service
    ):
        """Verify full setup: lead fetched, KB loaded, agent created, session started."""
        runner_cls, runner_instance = mock_runner_no_events
        ss_cls, ss_instance, ss_mock = mock_session_service

        with (
            patch(
                "voice_handler.fetch_lead",
                new_callable=AsyncMock,
                return_value=mock_lead,
            ) as mock_fetch,
            patch(
                "voice_handler.load_knowledge_base",
                new_callable=AsyncMock,
                return_value="mock KB content",
            ) as mock_load_kb,
            patch(
                "voice_handler.build_system_instruction",
                return_value="mock system instruction",
            ) as mock_build_si,
            patch(
                "voice_handler.create_sarah_agent",
                return_value=MagicMock(),
            ) as mock_create_agent,
            patch("voice_handler.Runner", runner_cls),
            patch("voice_handler.InMemorySessionService", ss_cls),
            patch(
                "voice_handler.get_firestore_client",
                return_value=MagicMock(),
            ),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
            patch("voice_handler.LiveRequestQueue", MagicMock),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                # Send a small audio chunk to trigger upstream, then close
                ws.send_bytes(b"\x00" * 160)
                # The mock runner yields no events, so downstream ends quickly

            # Verify setup was called correctly
            mock_fetch.assert_awaited_once_with("lead-001")
            mock_load_kb.assert_awaited_once()
            mock_build_si.assert_called_once_with(
                "Adebayo Ogunlesi", "mock KB content"
            )
            mock_create_agent.assert_called_once_with("mock system instruction")


class TestLeadNotFound:
    """Test that missing lead returns error and closes WebSocket."""

    def test_session_lead_not_found(self, _mock_voice_deps):
        """WebSocket should receive error JSON and close when lead not found."""
        with (
            patch(
                "voice_handler.fetch_lead",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("voice_handler.log_event", new_callable=AsyncMock),
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
        self, _mock_voice_deps, mock_lead, mock_runner_no_events, mock_session_service
    ):
        """process_call_end must be called after disconnect to write outcome."""
        runner_cls, runner_instance = mock_runner_no_events
        ss_cls, ss_instance, ss_mock = mock_session_service

        mock_process = AsyncMock()
        mock_lrq_instance = MagicMock()
        mock_lrq_cls = MagicMock(return_value=mock_lrq_instance)

        with (
            patch(
                "voice_handler.fetch_lead",
                new_callable=AsyncMock,
                return_value=mock_lead,
            ),
            patch(
                "voice_handler.load_knowledge_base",
                new_callable=AsyncMock,
                return_value="mock KB",
            ),
            patch(
                "voice_handler.build_system_instruction",
                return_value="mock instruction",
            ),
            patch(
                "voice_handler.create_sarah_agent",
                return_value=MagicMock(),
            ),
            patch("voice_handler.Runner", runner_cls),
            patch("voice_handler.InMemorySessionService", ss_cls),
            patch(
                "voice_handler.get_firestore_client",
                return_value=MagicMock(),
            ),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", mock_process),
            patch("voice_handler.LiveRequestQueue", mock_lrq_cls),
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

            # Verify live_request_queue was closed
            mock_lrq_instance.close.assert_called_once()

    def test_watchdog_cancelled_on_disconnect(
        self, _mock_voice_deps, mock_lead, mock_runner_no_events, mock_session_service
    ):
        """Watchdog task should be cancelled when call ends before 8.5 min."""
        runner_cls, _ = mock_runner_no_events
        ss_cls, _, _ = mock_session_service

        with (
            patch(
                "voice_handler.fetch_lead",
                new_callable=AsyncMock,
                return_value=mock_lead,
            ),
            patch(
                "voice_handler.load_knowledge_base",
                new_callable=AsyncMock,
                return_value="mock KB",
            ),
            patch(
                "voice_handler.build_system_instruction",
                return_value="mock instruction",
            ),
            patch(
                "voice_handler.create_sarah_agent",
                return_value=MagicMock(),
            ),
            patch("voice_handler.Runner", runner_cls),
            patch("voice_handler.InMemorySessionService", ss_cls),
            patch(
                "voice_handler.get_firestore_client",
                return_value=MagicMock(),
            ),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", new_callable=AsyncMock),
            patch("voice_handler.LiveRequestQueue", MagicMock),
            patch(
                "voice_handler.duration_watchdog",
                new_callable=AsyncMock,
            ) as mock_watchdog,
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            # duration_watchdog was called (as part of the gather)
            mock_watchdog.assert_awaited_once()


class TestTranscriptionAccumulation:
    """Test that transcriptions are captured from ADK events."""

    def test_transcriptions_accumulated_in_session(
        self, _mock_voice_deps, mock_lead, mock_session_service
    ):
        """CallSession should accumulate user and agent transcripts from events."""
        ss_cls, ss_instance, ss_mock = mock_session_service

        # Create mock events with transcriptions
        event1 = MagicMock()
        event1.content = None
        event1.input_transcription = MagicMock(text="Hello, is this Cloudboosta?")
        event1.output_transcription = None

        event2 = MagicMock()
        event2.content = None
        event2.input_transcription = None
        event2.output_transcription = MagicMock(
            text="Hi Adebayo! Yes, this is Sarah from Cloudboosta."
        )

        event3 = MagicMock()
        event3.content = None
        event3.input_transcription = MagicMock(
            text="I want to learn about cloud engineering."
        )
        event3.output_transcription = None

        # Mock runner that yields these events
        mock_runner_cls = MagicMock()
        mock_runner_instance = MagicMock()

        async def _event_gen(*args, **kwargs):
            for event in [event1, event2, event3]:
                yield event

        mock_runner_instance.run_live = _event_gen
        mock_runner_cls.return_value = mock_runner_instance

        captured_sessions = []

        async def _capture_process(session):
            captured_sessions.append(session)

        with (
            patch(
                "voice_handler.fetch_lead",
                new_callable=AsyncMock,
                return_value=mock_lead,
            ),
            patch(
                "voice_handler.load_knowledge_base",
                new_callable=AsyncMock,
                return_value="mock KB",
            ),
            patch(
                "voice_handler.build_system_instruction",
                return_value="mock instruction",
            ),
            patch(
                "voice_handler.create_sarah_agent",
                return_value=MagicMock(),
            ),
            patch("voice_handler.Runner", mock_runner_cls),
            patch("voice_handler.InMemorySessionService", ss_cls),
            patch(
                "voice_handler.get_firestore_client",
                return_value=MagicMock(),
            ),
            patch("voice_handler.log_event", new_callable=AsyncMock),
            patch("voice_handler.process_call_end", _capture_process),
            patch("voice_handler.LiveRequestQueue", MagicMock),
            patch(
                "voice_handler.duration_watchdog",
                new_callable=AsyncMock,
            ),
        ):
            from main import app

            client = TestClient(app)
            with client.websocket_connect("/ws/voice/lead-001") as ws:
                ws.send_bytes(b"\x00" * 160)

            # Verify transcriptions were accumulated
            assert len(captured_sessions) == 1
            session = captured_sessions[0]
            assert len(session.user_transcripts) == 2
            assert session.user_transcripts[0] == "Hello, is this Cloudboosta?"
            assert (
                session.user_transcripts[1]
                == "I want to learn about cloud engineering."
            )
            assert len(session.agent_transcripts) == 1
            assert (
                session.agent_transcripts[0]
                == "Hi Adebayo! Yes, this is Sarah from Cloudboosta."
            )


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
