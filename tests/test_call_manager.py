"""Tests for call session manager (CallSession, duration_watchdog, process_call_end).

Covers call state tracking, transcript accumulation, duration monitoring,
watchdog signal injection, and call outcome post-processing.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- CallSession tests ----


def test_call_session_init():
    """CallSession initializes with lead_id, lead_name, start_time, empty transcripts, no outcome."""
    from call_manager import CallSession

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    assert session.lead_id == "lead-123"
    assert session.lead_name == "Akin"
    assert isinstance(session.start_time, float)
    assert session.start_time > 0
    assert session.user_transcripts == []
    assert session.agent_transcripts == []
    assert session.outcome is None
    assert session.watchdog_task is None


def test_call_session_duration():
    """CallSession.elapsed_seconds returns correct duration."""
    from call_manager import CallSession

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    # Manually set start_time to 2 seconds ago
    session.start_time = time.time() - 2.0
    elapsed = session.elapsed_seconds
    assert 1.5 <= elapsed <= 3.0  # Allow some tolerance


def test_call_session_append_user_transcript():
    """append_user_transcript accumulates text in user_transcripts list."""
    from call_manager import CallSession

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    session.append_user_transcript("Hello, I'm interested in cloud training.")
    session.append_user_transcript("I'm a junior developer.")
    assert len(session.user_transcripts) == 2
    assert session.user_transcripts[0] == "Hello, I'm interested in cloud training."
    assert session.user_transcripts[1] == "I'm a junior developer."


def test_call_session_append_agent_transcript():
    """append_agent_transcript accumulates text in agent_transcripts list."""
    from call_manager import CallSession

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    session.append_agent_transcript("Hi Akin, this is Sarah from Cloudboosta.")
    session.append_agent_transcript("Tell me about your cloud experience.")
    assert len(session.agent_transcripts) == 2
    assert "Sarah" in session.agent_transcripts[0]


def test_call_session_full_transcript():
    """full_transcript returns formatted 'Lead: ... / Sarah: ...' interleaved text."""
    from call_manager import CallSession

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    session.append_agent_transcript("Hi Akin, this is Sarah.")
    session.append_user_transcript("Hi Sarah, I'm interested.")
    session.append_agent_transcript("Tell me about your role.")
    session.append_user_transcript("I'm a junior dev.")

    transcript = session.full_transcript
    assert "Sarah: Hi Akin, this is Sarah." in transcript
    assert "Lead: Hi Sarah, I'm interested." in transcript
    assert "Sarah: Tell me about your role." in transcript
    assert "Lead: I'm a junior dev." in transcript


# ---- duration_watchdog tests ----


async def test_watchdog_fires_at_correct_time():
    """duration_watchdog with timeout=0.1s sends content to LiveRequestQueue within 0.2s."""
    from call_manager import duration_watchdog

    mock_queue = MagicMock()
    mock_queue.send_content = MagicMock()

    start = time.time()
    await duration_watchdog(mock_queue, timeout_seconds=0.1)
    elapsed = time.time() - start

    assert elapsed >= 0.09  # At least the timeout
    assert elapsed < 0.5  # Should not take too long
    mock_queue.send_content.assert_called_once()


async def test_watchdog_signal_content():
    """The injected content contains '[INTERNAL SYSTEM SIGNAL]' text."""
    from call_manager import duration_watchdog

    mock_queue = MagicMock()
    mock_queue.send_content = MagicMock()

    await duration_watchdog(mock_queue, timeout_seconds=0.05)

    call_args = mock_queue.send_content.call_args
    content = call_args[0][0]  # First positional argument

    # Content should have role="user" and parts with the signal text
    assert content.role == "user"
    assert len(content.parts) > 0
    signal_text = content.parts[0].text
    assert "[INTERNAL SYSTEM SIGNAL" in signal_text
    assert "DO NOT READ ALOUD" in signal_text
    assert "8.5 minutes" in signal_text


async def test_watchdog_cancellation():
    """Cancelling the watchdog task before timeout does not send signal."""
    from call_manager import duration_watchdog

    mock_queue = MagicMock()
    mock_queue.send_content = MagicMock()

    task = asyncio.create_task(duration_watchdog(mock_queue, timeout_seconds=5.0))
    await asyncio.sleep(0.05)  # Let it start sleeping
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    mock_queue.send_content.assert_not_called()


# ---- process_call_end tests ----


async def test_process_call_end_committed():
    """process_call_end writes call_log and updates lead status to 'call_completed'."""
    from call_manager import CallSession, process_call_end

    session = CallSession(lead_id="lead-123", lead_name="Akin")
    session.start_time = time.time() - 300  # 5 minutes ago
    session.outcome = {
        "outcome": "COMMITTED",
        "recommended_programme": "cloud-security",
        "qualification_summary": "Junior dev with networking background",
        "objections_raised": ["price"],
        "follow_up_preference": "",
    }
    session.append_agent_transcript("Hi Akin")
    session.append_user_transcript("Hi Sarah")

    with patch("call_manager.write_call_log_to_supabase", new_callable=AsyncMock) as mock_write_log, \
         patch("call_manager.write_lead_profile_to_supabase", new_callable=AsyncMock) as mock_write_profile, \
         patch("call_manager.log_event", new_callable=AsyncMock) as mock_log, \
         patch("call_manager._update_lead_status", new_callable=AsyncMock) as mock_status:

        mock_write_log.return_value = "call-log-uuid-1"

        await process_call_end(session)

        # call_log should be written
        mock_write_log.assert_called_once()
        call_data = mock_write_log.call_args[0][1]
        assert call_data["lead_id"] == "lead-123"
        assert call_data["status"] == "completed"
        assert call_data["outcome"] == "COMMITTED"

        # Lead status should be updated
        mock_status.assert_called_once_with("lead-123", "call_completed")


async def test_process_call_end_follow_up():
    """process_call_end with FOLLOW_UP outcome includes follow_up_date."""
    from call_manager import CallSession, process_call_end

    session = CallSession(lead_id="lead-456", lead_name="Bola")
    session.start_time = time.time() - 420  # 7 minutes ago
    session.outcome = {
        "outcome": "FOLLOW_UP",
        "recommended_programme": "sre-platform-engineering",
        "qualification_summary": "Mid-level sysadmin",
        "objections_raised": ["time"],
        "follow_up_preference": "next Tuesday",
    }

    with patch("call_manager.write_call_log_to_supabase", new_callable=AsyncMock) as mock_write_log, \
         patch("call_manager.write_lead_profile_to_supabase", new_callable=AsyncMock) as mock_write_profile, \
         patch("call_manager.log_event", new_callable=AsyncMock) as mock_log, \
         patch("call_manager._update_lead_status", new_callable=AsyncMock) as mock_status:

        mock_write_log.return_value = "call-log-uuid-2"

        await process_call_end(session)

        call_data = mock_write_log.call_args[0][1]
        assert call_data["outcome"] == "FOLLOW_UP"
        assert call_data["follow_up_preference"] == "next Tuesday"


async def test_process_call_end_dropped():
    """process_call_end with no outcome records CALL_DROPPED."""
    from call_manager import CallSession, process_call_end

    session = CallSession(lead_id="lead-789", lead_name="Chika")
    session.start_time = time.time() - 120  # 2 minutes ago
    session.outcome = None  # No outcome -- abnormal disconnect
    session.append_agent_transcript("Hi Chika, this is Sarah.")
    session.append_user_transcript("Hi, can you hear me?")

    with patch("call_manager.write_call_log_to_supabase", new_callable=AsyncMock) as mock_write_log, \
         patch("call_manager.write_lead_profile_to_supabase", new_callable=AsyncMock) as mock_write_profile, \
         patch("call_manager.log_event", new_callable=AsyncMock) as mock_log, \
         patch("call_manager._update_lead_status", new_callable=AsyncMock) as mock_status:

        mock_write_log.return_value = "call-log-uuid-3"

        await process_call_end(session)

        call_data = mock_write_log.call_args[0][1]
        assert call_data["status"] == "dropped"
        assert call_data["outcome"] == "CALL_DROPPED"

        # Lead status should still be updated
        mock_status.assert_called_once_with("lead-789", "call_dropped")


async def test_process_call_end_logs_events():
    """process_call_end calls log_event with appropriate event names."""
    from call_manager import CallSession, process_call_end

    session = CallSession(lead_id="lead-100", lead_name="Dayo")
    session.start_time = time.time() - 300
    session.outcome = {
        "outcome": "DECLINED",
        "recommended_programme": "cloud-security",
        "qualification_summary": "Senior dev not interested",
        "objections_raised": ["not relevant to my career"],
        "follow_up_preference": "",
    }

    with patch("call_manager.write_call_log_to_supabase", new_callable=AsyncMock) as mock_write_log, \
         patch("call_manager.write_lead_profile_to_supabase", new_callable=AsyncMock) as mock_write_profile, \
         patch("call_manager.log_event", new_callable=AsyncMock) as mock_log, \
         patch("call_manager._update_lead_status", new_callable=AsyncMock) as mock_status:

        mock_write_log.return_value = "call-log-uuid-4"

        await process_call_end(session)

        # Should log at least one event
        assert mock_log.call_count >= 1
        event_names = [call.args[0] for call in mock_log.call_args_list]
        # Should have a call_completed or call_dropped event
        assert any("call_completed" in name or "outcome_determined" in name for name in event_names)


async def test_process_call_end_writes_qualification():
    """process_call_end writes qualification data to Supabase when present in session."""
    from call_manager import CallSession, process_call_end

    session = CallSession(lead_id="lead-200", lead_name="Emeka")
    session.start_time = time.time() - 300
    session.qualification = {
        "role": "Junior Developer",
        "experience_level": "junior",
        "cloud_background": "None",
        "motivation": "Career change",
    }
    session.outcome = {
        "outcome": "COMMITTED",
        "recommended_programme": "cloud-security",
        "qualification_summary": "Junior dev wanting career change",
        "objections_raised": [],
        "follow_up_preference": "",
    }

    with patch("call_manager.write_call_log_to_supabase", new_callable=AsyncMock) as mock_write_log, \
         patch("call_manager.write_lead_profile_to_supabase", new_callable=AsyncMock) as mock_write_profile, \
         patch("call_manager.log_event", new_callable=AsyncMock) as mock_log, \
         patch("call_manager._update_lead_status", new_callable=AsyncMock) as mock_status:

        mock_write_log.return_value = "call-log-uuid-5"

        await process_call_end(session)

        # Should write qualification data to Supabase
        mock_write_profile.assert_called_once()
        profile_data = mock_write_profile.call_args[0][1]
        assert profile_data["role"] == "Junior Developer"
        assert profile_data["experience_level"] == "junior"
