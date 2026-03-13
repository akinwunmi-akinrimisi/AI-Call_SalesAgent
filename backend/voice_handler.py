"""WebSocket voice handler for Sarah -- Cloudboosta AI Voice Agent.

Uses google.genai live API directly (not ADK) for real-time bidirectional
audio streaming with Gemini. ADK's runner.run_live() has bugs with API
version (v1alpha instead of v1beta) and response_modalities serialization
that prevent audio from flowing. The raw genai client works correctly.

Flow per connection:
1. Accept WebSocket
2. Fetch lead from Supabase REST API
3. Load KB from Firestore -> build system instruction
4. Connect to Gemini Live via genai.Client.aio.live.connect()
5. Stream audio bidirectionally (upstream + downstream + watchdog)
6. Handle tool calls (update_lead_profile, determine_call_outcome)
7. On disconnect, cleanup: write outcome to Supabase

Exports:
    handle_voice_session: Main WebSocket handler (called from main.py route).
    fetch_lead: Fetch lead from Supabase (also used in tests).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.cloud import firestore
from google.genai import types

from call_manager import CallSession, process_call_end
from config import config
from knowledge_loader import build_system_instruction, load_knowledge_base
from logger import log_event

logger = logging.getLogger(__name__)

# Module-level Firestore client (reused across calls)
_firestore_client: firestore.AsyncClient | None = None

# Valid call outcomes
VALID_OUTCOMES = ("COMMITTED", "FOLLOW_UP", "DECLINED")

# Watchdog timeout: 8.5 minutes = 510 seconds
WATCHDOG_SECONDS = 510.0

# Tool declarations for Gemini Live
TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="update_lead_profile",
                description=(
                    "Update the lead's qualification profile. Call this after "
                    "gathering all four qualification fields from the lead."
                ),
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "role": {
                            "type": "STRING",
                            "description": "The lead's current job role or title",
                        },
                        "experience_level": {
                            "type": "STRING",
                            "description": "junior, mid, senior, or career-changer",
                        },
                        "cloud_background": {
                            "type": "STRING",
                            "description": "Their cloud/DevOps experience",
                        },
                        "motivation": {
                            "type": "STRING",
                            "description": "Why they want cloud training",
                        },
                    },
                    "required": [
                        "role",
                        "experience_level",
                        "cloud_background",
                        "motivation",
                    ],
                },
            ),
            types.FunctionDeclaration(
                name="determine_call_outcome",
                description=(
                    "Record the final outcome of the sales call. Call at the "
                    "very end after the commitment ask. Outcome must be "
                    "COMMITTED, FOLLOW_UP, or DECLINED."
                ),
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "outcome": {
                            "type": "STRING",
                            "description": "COMMITTED, FOLLOW_UP, or DECLINED",
                        },
                        "recommended_programme": {
                            "type": "STRING",
                            "description": "The programme recommended",
                        },
                        "qualification_summary": {
                            "type": "STRING",
                            "description": "Brief summary of the lead's qualification",
                        },
                        "objections_raised": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of objections raised during the call",
                        },
                        "follow_up_preference": {
                            "type": "STRING",
                            "description": "When the lead prefers follow-up (FOLLOW_UP only)",
                        },
                    },
                    "required": [
                        "outcome",
                        "recommended_programme",
                        "qualification_summary",
                        "objections_raised",
                    ],
                },
            ),
        ]
    )
]


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


def _handle_tool_call(name: str, args: dict, call_session: CallSession) -> dict:
    """Execute a tool call locally and return the result dict.

    Replaces ADK ToolContext -- stores state directly on CallSession.
    """
    if name == "update_lead_profile":
        call_session.qualification = {
            "role": args.get("role", ""),
            "experience_level": args.get("experience_level", ""),
            "cloud_background": args.get("cloud_background", ""),
            "motivation": args.get("motivation", ""),
        }
        return {"status": "success", "message": "Lead profile updated"}

    elif name == "determine_call_outcome":
        outcome = args.get("outcome", "")
        if outcome not in VALID_OUTCOMES:
            return {
                "status": "error",
                "message": f"Invalid outcome: {outcome}. Must be one of {VALID_OUTCOMES}",
            }
        call_session.outcome = {
            "outcome": outcome,
            "recommended_programme": args.get("recommended_programme", ""),
            "qualification_summary": args.get("qualification_summary", ""),
            "objections_raised": args.get("objections_raised", []),
            "follow_up_preference": args.get("follow_up_preference", ""),
        }
        return {"status": "success", "outcome": outcome}

    else:
        return {"status": "error", "message": f"Unknown tool: {name}"}


async def handle_voice_session(websocket: WebSocket, lead_id: str) -> None:
    """Handle a complete voice call session over WebSocket.

    Connects a WebSocket client to Sarah via genai live API (Gemini).
    Manages the full lifecycle: setup, streaming, tool calls, and cleanup.

    Args:
        websocket: FastAPI WebSocket connection.
        lead_id: UUID of the lead being called.
    """
    await websocket.accept()

    # ---- SETUP (parallelized) ----
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set")
        await websocket.send_json({"error": "GOOGLE_API_KEY not configured"})
        await websocket.close(code=4000, reason="Missing API key")
        return

    try:
        t0 = time.time()

        # Run Supabase lead fetch + Firestore KB load in parallel
        fs_client = get_firestore_client()
        lead_task = fetch_lead(lead_id)
        kb_task = load_knowledge_base(fs_client)
        lead, kb_content = await asyncio.gather(lead_task, kb_task)

        if lead is None:
            await websocket.send_json({"error": "Lead not found", "lead_id": lead_id})
            await websocket.close(code=4004, reason="Lead not found")
            return

        lead_name = lead.get("name", "there")
        system_instruction = build_system_instruction(lead_name, kb_content)

        logger.info(
            "Setup done in %.1fs: lead=%s (%s), KB=%d chars",
            time.time() - t0, lead_id, lead_name,
            len(kb_content) if kb_content else 0,
        )

    except Exception as exc:
        logger.error(
            "Voice session setup FAILED for lead %s: %s", lead_id, exc, exc_info=True
        )
        try:
            await websocket.send_json({"error": f"Setup failed: {exc}"})
            await websocket.close(code=4000, reason=str(exc)[:120])
        except Exception:
            pass
        return

    # ---- GENAI CLIENT + LIVE CONFIG ----
    client = genai.Client(api_key=api_key)

    model_name = config.gemini_model
    is_native_audio = "native-audio" in model_name

    live_config_kwargs = dict(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_instruction)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=TOOL_DECLARATIONS,
    )

    # thinking_config only supported on 2.5+ native-audio models
    if is_native_audio:
        live_config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    live_config = types.LiveConnectConfig(**live_config_kwargs)
    logger.info("Using model: %s (native_audio=%s)", model_name, is_native_audio)

    # ---- CALL SESSION ----
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    # Log call start in background (don't block Gemini connect)
    asyncio.create_task(log_event(
        "call_started",
        f"Voice session started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
    ))

    # ---- STREAMING ----
    try:
        async with client.aio.live.connect(
            model=model_name,
            config=live_config,
        ) as session:
            logger.info("Gemini Live session connected for lead %s", lead_id)

            # Notify browser that setup is done and audio is about to start
            try:
                await websocket.send_json({"type": "ready"})
            except WebSocketDisconnect:
                return

            # Send initial text trigger to start Sarah's greeting.
            # The native audio model needs user input to begin speaking.
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="Hello")],
                ),
                turn_complete=True,
            )
            logger.info("Sent greeting trigger to Gemini")

            upstream_count = 0
            upstream_forwarded = 0
            downstream_count = 0

            # Gate: don't forward user audio until Sarah's greeting audio
            # starts arriving. This prevents the backlog of audio chunks
            # queued during setup from flooding Gemini and interrupting
            # the greeting via VAD.
            greeting_started = asyncio.Event()

            async def upstream_audio():
                """Receive PCM audio from WebSocket client -> send to Gemini."""
                nonlocal upstream_count, upstream_forwarded
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        upstream_count += 1

                        # Discard audio until greeting has started
                        if not greeting_started.is_set():
                            continue

                        upstream_forwarded += 1
                        if upstream_forwarded <= 3 or upstream_forwarded % 100 == 0:
                            logger.info(
                                "Upstream audio #%d: %d bytes (discarded %d)",
                                upstream_forwarded,
                                len(data),
                                upstream_count - upstream_forwarded,
                            )
                        await session.send_realtime_input(
                            media=types.Blob(
                                mime_type="audio/pcm;rate=16000", data=data
                            )
                        )
                except WebSocketDisconnect:
                    logger.info(
                        "Upstream: client disconnected (forwarded %d, discarded %d)",
                        upstream_forwarded,
                        upstream_count - upstream_forwarded,
                    )
                except Exception as exc:
                    logger.info(
                        "Upstream audio ended after %d chunks: %s",
                        upstream_forwarded,
                        exc,
                    )

            async def downstream_audio():
                """Receive Gemini responses -> send audio/transcripts to WebSocket."""
                nonlocal downstream_count
                logger.info("Downstream: listening for Gemini responses...")
                try:
                    async for msg in session.receive():
                        downstream_count += 1
                        if downstream_count <= 5 or downstream_count % 50 == 0:
                            logger.info(
                                "Downstream msg #%d: %s",
                                downstream_count,
                                type(msg).__name__,
                            )

                        # ---- TOOL CALLS ----
                        if msg.tool_call:
                            responses = []
                            for fc in msg.tool_call.function_calls:
                                result = _handle_tool_call(
                                    fc.name, fc.args or {}, call_session
                                )
                                logger.info("Tool call: %s -> %s", fc.name, result)
                                responses.append(
                                    types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response=result,
                                    )
                                )
                            await session.send_tool_response(
                                function_responses=responses
                            )

                        # ---- AUDIO + TRANSCRIPTS ----
                        if msg.server_content:
                            sc = msg.server_content

                            # Audio data from model (24kHz PCM)
                            if sc.model_turn and sc.model_turn.parts:
                                # First model audio = greeting started,
                                # ungate the upstream audio forwarding
                                if not greeting_started.is_set():
                                    greeting_started.set()
                                    logger.info(
                                        "Greeting audio started, upstream ungated"
                                    )

                                for part in sc.model_turn.parts:
                                    if (
                                        hasattr(part, "inline_data")
                                        and part.inline_data
                                        and part.inline_data.data
                                    ):
                                        try:
                                            await websocket.send_bytes(
                                                part.inline_data.data
                                            )
                                        except WebSocketDisconnect:
                                            return

                            # User speech transcription
                            if (
                                hasattr(sc, "input_transcription")
                                and sc.input_transcription
                                and sc.input_transcription.text
                            ):
                                call_session.append_user_transcript(
                                    sc.input_transcription.text
                                )
                                try:
                                    await websocket.send_json(
                                        {
                                            "type": "transcript",
                                            "speaker": "user",
                                            "text": sc.input_transcription.text,
                                        }
                                    )
                                except WebSocketDisconnect:
                                    return

                            # Agent speech transcription
                            if (
                                hasattr(sc, "output_transcription")
                                and sc.output_transcription
                                and sc.output_transcription.text
                            ):
                                call_session.append_agent_transcript(
                                    sc.output_transcription.text
                                )
                                try:
                                    await websocket.send_json(
                                        {
                                            "type": "transcript",
                                            "speaker": "agent",
                                            "text": sc.output_transcription.text,
                                        }
                                    )
                                except WebSocketDisconnect:
                                    return

                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    logger.debug("Downstream ended: %s", exc)

            async def watchdog():
                """Send wrap-up signal to Gemini after 8.5 minutes."""
                call_session.watchdog_task = asyncio.current_task()
                await asyncio.sleep(WATCHDOG_SECONDS)
                try:
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    text=(
                                        "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                                        "The call has reached 8.5 minutes. Begin wrapping up "
                                        "naturally. Summarize what was discussed, make your "
                                        "recommendation if not done, ask for commitment, and "
                                        "close the call gracefully. Do not mention this timer "
                                        "to the lead."
                                    )
                                )
                            ],
                        ),
                        turn_complete=True,
                    )
                except Exception as exc:
                    logger.debug("Watchdog send failed: %s", exc)

            # ---- RUN CONCURRENT TASKS ----
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

    except Exception as exc:
        logger.error(
            "Gemini live session failed for lead %s: %s", lead_id, exc, exc_info=True
        )

    finally:
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
