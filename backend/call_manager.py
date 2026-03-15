"""Call session manager for Sarah's voice calls.

Tracks call state (transcripts, duration, outcome), provides the duration
watchdog that fires at 8.5 minutes to trigger wrap-up, and handles call
outcome post-processing (Supabase writes, pipeline logging).

Exports:
    CallSession: Dataclass-like class for call state tracking.
    duration_watchdog: Async coroutine that injects wrap-up signal at timeout.
    process_call_end: Async function for call outcome post-processing.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

from google.genai import types

from logger import log_event
from tools import write_call_log_to_supabase, write_lead_profile_to_supabase

if TYPE_CHECKING:
    from google.adk.agents.live_request_queue import LiveRequestQueue

# Default watchdog timeout: 10 minutes = 600 seconds (first nudge)
WATCHDOG_SECONDS = 600.0


class CallSession:
    """Tracks state for a single voice call session.

    Attributes:
        lead_id: UUID of the lead being called.
        lead_name: Display name of the lead.
        start_time: Unix timestamp when the session was created.
        user_transcripts: Accumulated user (lead) speech transcriptions.
        agent_transcripts: Accumulated agent (Sarah) speech transcriptions.
        outcome: Call outcome dict from determine_call_outcome tool, or None.
        qualification: Qualification dict from update_lead_profile tool, or None.
        watchdog_task: Reference to the asyncio watchdog task, if running.
    """

    def __init__(self, lead_id: str, lead_name: str) -> None:
        self.lead_id = lead_id
        self.lead_name = lead_name
        self.start_time: float = time.time()
        self.user_transcripts: list[str] = []
        self.agent_transcripts: list[str] = []
        self.outcome: dict | None = None
        self.qualification: dict | None = None
        self.watchdog_task: asyncio.Task | None = None

    @property
    def elapsed_seconds(self) -> float:
        """Return seconds elapsed since call start."""
        return time.time() - self.start_time

    @property
    def full_transcript(self) -> str:
        """Return formatted interleaved transcript.

        Interleaves agent and user transcripts in order, prefixed with
        'Sarah: ' and 'Lead: ' respectively. Transcripts are interleaved
        by alternating between agent and user entries.
        """
        lines: list[str] = []
        agent_idx = 0
        user_idx = 0

        # Build interleaved transcript from both lists
        # Agent typically speaks first (greeting), then user responds
        while agent_idx < len(self.agent_transcripts) or user_idx < len(self.user_transcripts):
            if agent_idx < len(self.agent_transcripts):
                lines.append(f"Sarah: {self.agent_transcripts[agent_idx]}")
                agent_idx += 1
            if user_idx < len(self.user_transcripts):
                lines.append(f"Lead: {self.user_transcripts[user_idx]}")
                user_idx += 1

        return "\n".join(lines)

    def append_user_transcript(self, text: str) -> None:
        """Append a user speech transcription segment."""
        self.user_transcripts.append(text)

    def append_agent_transcript(self, text: str) -> None:
        """Append an agent speech transcription segment."""
        self.agent_transcripts.append(text)


async def duration_watchdog(
    live_request_queue: "LiveRequestQueue",
    timeout_seconds: float = WATCHDOG_SECONDS,
) -> None:
    """Inject wrap-up signal into agent context after timeout.

    Waits for the specified timeout, then sends a text content message
    into the LiveRequestQueue instructing Sarah to begin wrapping up.
    The signal is prefixed with [INTERNAL SYSTEM SIGNAL] so Sarah's
    system instruction knows to treat it as an internal directive and
    not read it aloud to the lead.

    If the coroutine is cancelled (e.g., call ended before timeout),
    it silently returns without sending the signal.

    Args:
        live_request_queue: ADK LiveRequestQueue for the active session.
        timeout_seconds: Seconds to wait before firing. Default 510 (8.5 min).
    """
    await asyncio.sleep(timeout_seconds)

    wrap_up_signal = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                    "The call has reached 8.5 minutes. Begin wrapping up naturally. "
                    "Summarize what was discussed, make your recommendation if not done, "
                    "ask for commitment, and close the call gracefully. "
                    "Do not mention this timer to the lead."
                )
            )
        ],
    )
    live_request_queue.send_content(wrap_up_signal)


async def _update_lead_status(lead_id: str, status: str) -> None:
    """Update the lead's status field in Supabase.

    Args:
        lead_id: UUID of the lead to update.
        status: New status value (e.g., 'call_completed', 'call_dropped').
    """
    import httpx

    from config import config as _cfg

    supabase_url = _cfg.supabase_url
    supabase_key = _cfg.supabase_service_key

    if not supabase_url or not supabase_key:
        return

    url = f"{supabase_url}/rest/v1/leads?id=eq.{lead_id}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json={"status": status}, headers=headers, timeout=10)
        resp.raise_for_status()


async def process_call_end(session: CallSession) -> None:
    """Post-process a completed or dropped call.

    Reads the outcome from the session (populated by determine_call_outcome
    tool via ToolContext.state during the call). If no outcome exists, creates
    a CALL_DROPPED entry for abnormal disconnect handling.

    Writes:
    1. call_log entry to Supabase (via write_call_log_to_supabase)
    2. Lead qualification data to Supabase (via write_lead_profile_to_supabase)
    3. Lead status update (call_completed or call_dropped)
    4. Pipeline log events

    Args:
        session: The CallSession instance with accumulated call data.
    """
    duration = int(session.elapsed_seconds)
    transcript = session.full_transcript

    if session.outcome is not None:
        # Normal call end -- outcome determined by Sarah
        outcome = session.outcome
        call_status = "completed"
        lead_status = "call_completed"
        event_name = "call_completed"
    else:
        # Abnormal disconnect -- no outcome determined
        outcome = {
            "outcome": "CALL_DROPPED",
            "recommended_programme": "",
            "qualification_summary": "",
            "objections_raised": [],
            "follow_up_preference": "",
        }
        call_status = "dropped"
        lead_status = "call_dropped"
        event_name = "call_dropped"

    # Build call_log entry — truncate transcript to avoid Supabase limits
    call_data = {
        "lead_id": session.lead_id,
        "status": call_status,
        "outcome": outcome.get("outcome", "CALL_DROPPED") if isinstance(outcome, dict) else str(outcome),
        "transcript": transcript[:60000] if transcript else "",
        "qualification_summary": str(outcome.get("qualification_summary", ""))[:5000] if isinstance(outcome, dict) else "",
        "recommended_programme": str(outcome.get("recommended_programme", ""))[:500] if isinstance(outcome, dict) else "",
        "objections_raised": outcome.get("objections_raised", []) if isinstance(outcome, dict) else [],
        "duration_seconds": duration,
        "follow_up_preference": str(outcome.get("follow_up_preference", ""))[:500] if isinstance(outcome, dict) else "",
    }

    # Write call log to Supabase
    try:
        call_log_id = await write_call_log_to_supabase(session.lead_id, call_data)
        await log_event(
            event_name,
            f"Call {call_status} for lead {session.lead_id} "
            f"(outcome={outcome['outcome']}, duration={duration}s)",
            lead_id=session.lead_id,
            metadata={"call_log_id": call_log_id, "outcome": outcome["outcome"]},
        )
    except Exception as exc:
        await log_event(
            "call_log_error",
            f"Failed to write call log for lead {session.lead_id}: {exc}",
            event_type="error",
            lead_id=session.lead_id,
        )

    # Write qualification data if available
    if session.qualification is not None:
        try:
            await write_lead_profile_to_supabase(session.lead_id, session.qualification)
            await log_event(
                "qualification_saved",
                f"Qualification data saved for lead {session.lead_id}",
                lead_id=session.lead_id,
            )
        except Exception as exc:
            await log_event(
                "qualification_save_error",
                f"Failed to save qualification for lead {session.lead_id}: {exc}",
                event_type="error",
                lead_id=session.lead_id,
            )

    # Update lead status
    try:
        await _update_lead_status(session.lead_id, lead_status)
    except Exception as exc:
        await log_event(
            "lead_status_error",
            f"Failed to update lead status for {session.lead_id}: {exc}",
            event_type="error",
            lead_id=session.lead_id,
        )

    # Log outcome determination event
    if session.outcome is not None:
        await log_event(
            "outcome_determined",
            f"Outcome for lead {session.lead_id}: {outcome['outcome']}",
            lead_id=session.lead_id,
            metadata={
                "outcome": outcome["outcome"],
                "recommended_programme": outcome.get("recommended_programme", ""),
            },
        )

    # Notify n8n post-call router (WF3)
    n8n_base = os.getenv("N8N_BASE_URL", "")
    if n8n_base:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{n8n_base}/webhook/post-call",
                    json={"lead_id": session.lead_id},
                )
                await client.post(
                    f"{n8n_base}/webhook/admin-notification",
                    json={"lead_id": session.lead_id},
                )
        except Exception as exc:
            await log_event(
                "n8n_notify_error",
                f"Failed to notify n8n for lead {session.lead_id}: {exc}",
                event_type="error",
                lead_id=session.lead_id,
            )
