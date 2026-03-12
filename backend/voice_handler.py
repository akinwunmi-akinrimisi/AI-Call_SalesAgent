"""WebSocket voice handler for Sarah -- Cloudboosta AI Voice Agent.

Manages the real-time bidirectional audio stream between a WebSocket client
(browser in Phase 3, Twilio in Phase 6) and the ADK Runner / Gemini Live API.

Flow per connection:
1. Accept WebSocket
2. Fetch lead from Supabase REST API
3. Load KB from Firestore -> build system instruction
4. Create ADK Agent + Runner + session
5. Stream audio bidirectionally (upstream + downstream + watchdog)
6. On disconnect, cleanup: extract tool state, write outcome to Supabase

Exports:
    handle_voice_session: Main WebSocket handler (called from main.py route).
    fetch_lead: Fetch lead from Supabase (also used in tests).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx
from fastapi import WebSocket, WebSocketDisconnect
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import firestore
from google.genai import types

from agent import create_sarah_agent
from call_manager import CallSession, duration_watchdog, process_call_end
from config import config
from knowledge_loader import build_system_instruction, load_knowledge_base
from logger import log_event

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Module-level Firestore client (reused across calls)
_firestore_client: firestore.AsyncClient | None = None


def get_firestore_client() -> firestore.AsyncClient:
    """Get or create the module-level Firestore AsyncClient.

    Uses the GCP project from config and service account credentials
    from the path specified in config.google_application_credentials.

    Returns:
        Firestore AsyncClient instance.
    """
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.AsyncClient(
            project=config.gcp_project_id,
        )
    return _firestore_client


async def fetch_lead(lead_id: str) -> dict | None:
    """Fetch a lead from Supabase REST API by ID.

    Uses Accept-Profile: sales_agent header to target the correct schema.

    Args:
        lead_id: UUID of the lead to fetch.

    Returns:
        Lead dict if found, None otherwise.
    """
    supabase_url = config.supabase_url
    supabase_key = config.supabase_service_key

    if not supabase_url or not supabase_key:
        logger.warning("Supabase not configured, cannot fetch lead %s", lead_id)
        return None

    url = f"{supabase_url}/rest/v1/leads?id=eq.{lead_id}&select=*"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept": "application/json",
        "Accept-Profile": "sales_agent",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data and len(data) > 0:
                await log_event(
                    "lead_fetched",
                    f"Lead {lead_id} fetched for voice session",
                    lead_id=lead_id,
                )
                return data[0]
            else:
                await log_event(
                    "lead_not_found",
                    f"Lead {lead_id} not found in Supabase",
                    lead_id=lead_id,
                    event_type="warning",
                )
                return None
    except Exception as exc:
        logger.error("Failed to fetch lead %s: %s", lead_id, exc)
        await log_event(
            "lead_fetch_error",
            f"Failed to fetch lead {lead_id}: {exc}",
            lead_id=lead_id,
            event_type="error",
        )
        return None


async def handle_voice_session(websocket: WebSocket, lead_id: str) -> None:
    """Handle a complete voice call session over WebSocket.

    This is the main orchestration function that connects a WebSocket client
    to Sarah (ADK Agent) via the Gemini Live API. It manages the full lifecycle:
    setup, streaming, and cleanup.

    Args:
        websocket: FastAPI WebSocket connection.
        lead_id: UUID of the lead being called.
    """
    await websocket.accept()

    # ---- SETUP ----

    # 1. Fetch lead from Supabase
    lead = await fetch_lead(lead_id)
    if lead is None:
        await websocket.send_json({"error": "Lead not found", "lead_id": lead_id})
        await websocket.close(code=4004, reason="Lead not found")
        return

    lead_name = lead.get("name", "there")

    # 2. Load KB from Firestore
    fs_client = get_firestore_client()
    kb_content = await load_knowledge_base(fs_client)

    # 3. Build system instruction with lead name + KB
    system_instruction = build_system_instruction(lead_name, kb_content)

    # 4. Create ADK Agent with dynamic system instruction
    agent = create_sarah_agent(system_instruction)

    # 5. Create session service and runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="cloudboosta-voice-agent",
        session_service=session_service,
    )

    # 6. Create session with unique ID (supports multiple calls to same lead)
    session_id = f"call-{lead_id}-{int(time.time())}"
    session = await session_service.create_session(
        app_name="cloudboosta-voice-agent",
        user_id=lead_id,
        session_id=session_id,
    )

    # 7. Create LiveRequestQueue for bidirectional streaming
    live_request_queue = LiveRequestQueue()

    # 8. Create CallSession for state tracking
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    # 9. Log call start
    await log_event(
        "call_started",
        f"Voice session started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
    )

    # ---- CONFIGURE RunConfig ----

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            ),
            language_code="en-GB",
        ),
    )

    # ---- STREAMING (three concurrent tasks) ----

    async def upstream_audio():
        """Receive PCM audio from WebSocket client -> send to ADK agent."""
        try:
            while True:
                data = await websocket.receive_bytes()
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=data,
                )
                live_request_queue.send_realtime(audio_blob)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("Upstream audio ended: %s", exc)

    async def downstream_audio():
        """Receive agent audio events -> send to WebSocket client + capture transcripts."""
        try:
            async for event in runner.run_live(
                user_id=lead_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                # Send audio data to client
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if (
                            hasattr(part, "inline_data")
                            and part.inline_data
                            and part.inline_data.data
                        ):
                            try:
                                await websocket.send_bytes(part.inline_data.data)
                            except WebSocketDisconnect:
                                return

                # Capture user speech transcription + forward to browser
                if (
                    hasattr(event, "input_transcription")
                    and event.input_transcription
                    and event.input_transcription.text
                ):
                    call_session.append_user_transcript(
                        event.input_transcription.text
                    )
                    try:
                        await websocket.send_json({
                            "type": "transcript",
                            "speaker": "user",
                            "text": event.input_transcription.text,
                        })
                    except WebSocketDisconnect:
                        return

                # Capture agent speech transcription + forward to browser
                if (
                    hasattr(event, "output_transcription")
                    and event.output_transcription
                    and event.output_transcription.text
                ):
                    call_session.append_agent_transcript(
                        event.output_transcription.text
                    )
                    try:
                        await websocket.send_json({
                            "type": "transcript",
                            "speaker": "agent",
                            "text": event.output_transcription.text,
                        })
                    except WebSocketDisconnect:
                        return
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("Downstream audio ended: %s", exc)

    async def watchdog():
        """Start the duration watchdog as a concurrent task."""
        call_session.watchdog_task = asyncio.current_task()
        await duration_watchdog(live_request_queue)

    # ---- RUN + CLEANUP ----

    try:
        await asyncio.gather(
            upstream_audio(),
            downstream_audio(),
            watchdog(),
            return_exceptions=True,
        )
    finally:
        # Cancel watchdog if still running
        if call_session.watchdog_task and not call_session.watchdog_task.done():
            call_session.watchdog_task.cancel()
            try:
                await call_session.watchdog_task
            except asyncio.CancelledError:
                pass

        # Close the live request queue
        live_request_queue.close()

        # Extract tool state from ADK session
        try:
            adk_session = await session_service.get_session(
                app_name="cloudboosta-voice-agent",
                user_id=lead_id,
                session_id=session_id,
            )
            if adk_session and hasattr(adk_session, "state"):
                state = adk_session.state or {}
                if "call_outcome" in state:
                    call_session.outcome = state["call_outcome"]
                if "qualification" in state:
                    call_session.qualification = state["qualification"]
        except Exception as exc:
            logger.warning("Could not extract tool state from session: %s", exc)

        # Write outcome and transcript to Supabase
        await process_call_end(call_session)

        # Log call end
        duration = int(call_session.elapsed_seconds)
        await log_event(
            "call_ended",
            f"Voice session ended for lead {lead_id} (duration={duration}s)",
            lead_id=lead_id,
            metadata={"duration_seconds": duration},
        )
