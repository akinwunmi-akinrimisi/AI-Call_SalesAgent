"""Twilio ConversationRelay handler — text-only bridge to Gemini Live API.

ConversationRelay handles STT (caller speech → text) and TTS (text → caller audio).
We bridge the text between ConversationRelay and Gemini Live API:

    Caller speaks → Twilio STT → {"type":"prompt","voicePrompt":"..."} → WebSocket
    → send_client_content(text=..., turn_complete=True) → Gemini Live
    → Gemini responds (text) → output_transcription / model_turn text
    → {"type":"text","token":"...","last":true} → WebSocket → Twilio TTS → Caller hears

No audio conversion needed — all text-based. Tools (update_lead_profile,
determine_call_outcome) work identically to the voice handler.

Exports:
    handle_conversation_relay: WebSocket handler for ConversationRelay protocol.
    generate_conversation_relay_twiml: TwiML with <ConversationRelay> noun.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from call_manager import CallSession, process_call_end
from config import config
from knowledge_loader import build_system_instruction, load_knowledge_base
from logger import log_event
from voice_handler import (
    TOOL_DECLARATIONS,
    WATCHDOG_SECONDS,
    _handle_tool_call,
    fetch_lead,
    get_firestore_client,
)

logger = logging.getLogger(__name__)


def generate_conversation_relay_twiml(lead_id: str, base_url: str) -> str:
    """Generate TwiML XML with <ConversationRelay> noun.

    Args:
        lead_id: UUID of the lead (passed as custom parameter).
        base_url: Service URL (https:// converted to wss:// for WebSocket).

    Returns:
        TwiML XML string.
    """
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    # Build TwiML manually since the twilio SDK may not have ConversationRelay
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<ConversationRelay url="{ws_url}/ws/conversation-relay" '
        f'voice="Google.en-US-Journey-O" '
        f'language="en-US" '
        f'ttsProvider="Google" '
        f'transcriptionProvider="Google" '
        f'interruptible="true" '
        f'welcomeGreeting="" '
        f'>'
        f'<Parameter name="lead_id" value="{lead_id}" />'
        f"</ConversationRelay>"
        "</Connect>"
        "</Response>"
    )
    return twiml


async def handle_conversation_relay(websocket: WebSocket) -> None:
    """Handle Twilio ConversationRelay WebSocket connection.

    Protocol flow:
    1. Twilio sends "setup" event with callSid, customParameters
    2. We connect to Gemini Live session using lead_id
    3. Gemini greeting is triggered via send_client_content(text="Hello")
    4. Twilio sends "prompt" events with voicePrompt (STT text)
    5. We forward text to Gemini via send_client_content
    6. Gemini text responses → send back as {"type":"text","token":"..."}
    7. Handle tool calls (update_lead_profile, determine_call_outcome)
    8. Twilio sends "interrupt" when caller interrupts TTS
    """
    await websocket.accept()
    logger.info("ConversationRelay: WebSocket connected")

    # ---- Wait for setup event ----
    call_sid: str | None = None
    lead_id: str | None = None

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") != "setup":
            logger.error("ConversationRelay: expected setup, got %s", msg.get("type"))
            await websocket.close(code=4000, reason="Expected setup message")
            return

        call_sid = msg.get("callSid", "")
        custom_params = msg.get("customParameters", {})
        lead_id = custom_params.get("lead_id", "")
        logger.info(
            "ConversationRelay setup: callSid=%s lead_id=%s from=%s to=%s",
            call_sid, lead_id, msg.get("from"), msg.get("to"),
        )
    except asyncio.TimeoutError:
        logger.error("ConversationRelay: setup timeout")
        await websocket.close(code=4000, reason="Setup timeout")
        return
    except (WebSocketDisconnect, Exception) as exc:
        logger.error("ConversationRelay: setup failed: %s", exc)
        return

    if not lead_id:
        logger.error("ConversationRelay: no lead_id in customParameters")
        await websocket.close(code=4000, reason="Missing lead_id")
        return

    # ---- Setup: fetch lead + KB ----
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set")
        await websocket.close(code=4000, reason="Missing API key")
        return

    try:
        t0 = time.time()
        fs_client = get_firestore_client()
        lead, kb_content = await asyncio.gather(
            fetch_lead(lead_id),
            load_knowledge_base(fs_client),
        )

        if lead is None:
            logger.error("Lead %s not found", lead_id)
            # Send end message before closing
            await _send_json(websocket, {"type": "end"})
            return

        lead_name = lead.get("name", "there")
        system_instruction = build_system_instruction(lead_name, kb_content)
        logger.info(
            "ConversationRelay setup in %.1fs: lead=%s (%s)",
            time.time() - t0, lead_id, lead_name,
        )
    except Exception as exc:
        logger.error("ConversationRelay setup failed: %s", exc, exc_info=True)
        await _send_json(websocket, {"type": "end"})
        return

    # ---- Gemini Live session (TEXT only) ----
    client = genai.Client(api_key=api_key)

    # ConversationRelay needs TEXT modality (Twilio handles TTS).
    # Use CR_GEMINI_MODEL env var, or fall back to gemini-2.0-flash-live-001
    # which supports TEXT output on the Live API. Native-audio models don't
    # reliably produce output_transcription after the first turn.
    model_name = os.getenv("CR_GEMINI_MODEL", "gemini-2.0-flash-live-001")

    live_config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_instruction)]
        ),
        tools=TOOL_DECLARATIONS,
    )
    logger.info("CR: model=%s (text-only mode)", model_name)

    # ---- Call session ----
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    asyncio.create_task(log_event(
        "cr_call_started",
        f"ConversationRelay call started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
        metadata={"call_sid": call_sid},
    ))

    # ---- Streaming ----
    try:
        async with client.aio.live.connect(
            model=model_name,
            config=live_config,
        ) as session:
            logger.info("Gemini Live connected (text mode) for lead=%s", lead_id)

            call_ended = asyncio.Event()

            # Send greeting trigger
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="Hello")],
                ),
                turn_complete=True,
            )
            logger.info("ConversationRelay: greeting trigger sent to Gemini")

            async def receive_from_twilio():
                """Receive ConversationRelay messages and forward to Gemini."""
                try:
                    while not call_ended.is_set():
                        raw = await websocket.receive_text()
                        msg = json.loads(raw)
                        msg_type = msg.get("type", "")

                        if msg_type == "prompt":
                            voice_prompt = msg.get("voicePrompt", "")
                            if not voice_prompt.strip():
                                continue

                            logger.info("CR >>> User said: %s", voice_prompt)
                            call_session.append_user_transcript(voice_prompt)

                            # Forward text to Gemini
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=voice_prompt)],
                                ),
                                turn_complete=True,
                            )

                        elif msg_type == "interrupt":
                            utterance = msg.get("utteranceUntilInterrupt", "")
                            logger.info(
                                "CR: caller interrupted after: %s", utterance[:80]
                            )
                            # Gemini will handle interruption naturally on next prompt

                        elif msg_type == "dtmf":
                            digit = msg.get("digit", "")
                            logger.info("CR: DTMF digit: %s", digit)

                        elif msg_type == "error":
                            desc = msg.get("description", "")
                            logger.error("CR error from Twilio: %s", desc)

                        elif msg_type == "setup":
                            # Duplicate setup, ignore
                            pass

                        else:
                            logger.debug("CR: unknown message type: %s", msg_type)

                except WebSocketDisconnect:
                    logger.info("ConversationRelay: Twilio disconnected")
                except Exception as exc:
                    logger.error("CR receive error: %s", exc, exc_info=True)
                finally:
                    call_ended.set()

            async def receive_from_gemini():
                """Receive Gemini text responses and send to ConversationRelay."""
                try:
                    async for msg in session.receive():
                        if call_ended.is_set():
                            return

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

                        # ---- TEXT RESPONSES ----
                        if msg.server_content:
                            sc = msg.server_content

                            if sc.model_turn and sc.model_turn.parts:
                                for part in sc.model_turn.parts:
                                    if hasattr(part, "text") and part.text:
                                        text = part.text
                                        logger.info("CR <<< Sarah: %s", text[:120])
                                        call_session.append_agent_transcript(text)

                                        await _send_json(websocket, {
                                            "type": "text",
                                            "token": text,
                                            "last": False,
                                        })

                            # Turn complete — mark last token
                            if hasattr(sc, "turn_complete") and sc.turn_complete:
                                logger.info("CR: Gemini turn complete")
                                await _send_json(websocket, {
                                    "type": "text",
                                    "token": "",
                                    "last": True,
                                })

                except WebSocketDisconnect:
                    logger.info("CR: WebSocket disconnected during Gemini receive")
                except Exception as exc:
                    logger.error("CR Gemini receive error: %s", exc, exc_info=True)
                finally:
                    call_ended.set()

            async def watchdog():
                """Send wrap-up signal after 8.5 minutes."""
                call_session.watchdog_task = asyncio.current_task()
                await asyncio.sleep(WATCHDOG_SECONDS)
                if call_ended.is_set():
                    return
                try:
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    text=(
                                        "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                                        "The call has reached 8.5 minutes. Begin wrapping up "
                                        "naturally. Summarize, recommend, ask for commitment, "
                                        "and close gracefully."
                                    )
                                )
                            ],
                        ),
                        turn_complete=True,
                    )
                except Exception as exc:
                    logger.debug("Watchdog send failed: %s", exc)

            # ---- Run concurrent tasks ----
            try:
                results = await asyncio.gather(
                    receive_from_twilio(),
                    receive_from_gemini(),
                    watchdog(),
                    return_exceptions=True,
                )
                task_names = ["twilio_rx", "gemini_rx", "watchdog"]
                for name, result in zip(task_names, results):
                    if isinstance(result, Exception):
                        logger.error("CR task '%s' failed: %s", name, result)
            finally:
                if call_session.watchdog_task and not call_session.watchdog_task.done():
                    call_session.watchdog_task.cancel()
                    try:
                        await call_session.watchdog_task
                    except asyncio.CancelledError:
                        pass

    except Exception as exc:
        logger.error(
            "Gemini session failed for CR call (lead=%s): %s",
            lead_id, exc, exc_info=True,
        )

    finally:
        await process_call_end(call_session)

        duration = int(call_session.elapsed_seconds)
        await log_event(
            "cr_call_ended",
            f"ConversationRelay call ended for lead {lead_id} (duration={duration}s)",
            lead_id=lead_id,
            metadata={
                "duration_seconds": duration,
                "call_sid": call_sid,
            },
        )


async def _send_json(websocket: WebSocket, data: dict) -> bool:
    """Send JSON to WebSocket, return False if disconnected."""
    try:
        await websocket.send_text(json.dumps(data))
        return True
    except (WebSocketDisconnect, Exception):
        return False
