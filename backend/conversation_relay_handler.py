"""Twilio ConversationRelay handler — text bridge to Gemini Chat API.

Bridges text between ConversationRelay and Gemini Chat API with:
- Sentence-level TTS for immediate playback
- Interrupt handling with cancel events
- Multi-stage watchdog (10m, 15m, 19:20) with silent Gemini nudges
- Silent watchdog: signals go to Gemini but response is NOT sent to TTS

Exports:
    handle_conversation_relay: WebSocket handler for ConversationRelay protocol.
    generate_conversation_relay_twiml: TwiML with <ConversationRelay> noun.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
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
    WATCHDOG_15_SECONDS,
    WATCHDOG_FINAL_SECONDS,
    _handle_tool_call,
    fetch_lead,
    get_firestore_client,
)

logger = logging.getLogger(__name__)

# Sentence boundary for TTS chunking
_SENTENCE_SPLIT = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z"\'])'
    r'|(?<=\.\.\.)\s+'
    r'|(?<=[.!?])\s*$'
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for chunked TTS delivery."""
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def generate_conversation_relay_twiml(lead_id: str, base_url: str) -> str:
    """Generate TwiML XML with <ConversationRelay> noun."""
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    # Chirp3-HD: Google's most human-like generative voice
    # Testing Orus — confident, professional male voice
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<ConversationRelay url="{ws_url}/ws/conversation-relay" '
        f'voice="en-US-Chirp3-HD-Orus" '
        f'language="en-US" '
        f'ttsProvider="google" '
        f'transcriptionProvider="google" '
        f'interruptible="true" '
        f'welcomeGreeting="" '
        f">"
        f'<Parameter name="lead_id" value="{lead_id}" />'
        f"</ConversationRelay>"
        "</Connect>"
        "</Response>"
    )
    return twiml


async def handle_conversation_relay(websocket: WebSocket) -> None:
    """Handle Twilio ConversationRelay WebSocket connection."""
    await websocket.accept()
    logger.info("CR: WebSocket connected")

    # ---- Wait for setup event ----
    call_sid: str | None = None
    lead_id: str | None = None

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") != "setup":
            logger.error("CR: expected setup, got %s", msg.get("type"))
            await websocket.close(code=4000, reason="Expected setup message")
            return

        call_sid = msg.get("callSid", "")
        custom_params = msg.get("customParameters", {})
        lead_id = custom_params.get("lead_id", "")
        logger.info(
            "CR setup: callSid=%s lead_id=%s", call_sid, lead_id,
        )
    except asyncio.TimeoutError:
        logger.error("CR: setup timeout")
        await websocket.close(code=4000, reason="Setup timeout")
        return
    except (WebSocketDisconnect, Exception) as exc:
        logger.error("CR: setup failed: %s", exc)
        return

    if not lead_id:
        logger.error("CR: no lead_id")
        await websocket.close(code=4000, reason="Missing lead_id")
        return

    # ---- Fetch lead + KB ----
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
            await _send_json(websocket, {"type": "end"})
            return

        lead_name = lead.get("name", "there")
        system_instruction = build_system_instruction(lead_name, kb_content)
        logger.info(
            "CR setup in %.1fs: lead=%s (%s)",
            time.time() - t0, lead_id, lead_name,
        )
    except Exception as exc:
        logger.error("CR setup failed: %s", exc, exc_info=True)
        await _send_json(websocket, {"type": "end"})
        return

    # ---- Gemini Chat session ----
    model_name = os.getenv("CR_GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)

    chat = client.aio.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=TOOL_DECLARATIONS,
        ),
    )
    logger.info("CR: Gemini Chat created (model=%s)", model_name)

    # ---- Call session ----
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    asyncio.create_task(log_event(
        "cr_call_started",
        f"CR call started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
        metadata={"call_sid": call_sid},
    ))

    # ---- Cancel tracking ----
    cancel_event = asyncio.Event()

    # ---- Greeting ----
    try:
        await _gemini_respond(chat, "Hello", call_session, websocket, cancel_event)
    except Exception as exc:
        logger.error("CR: greeting failed: %s", exc, exc_info=True)
        await _send_json(websocket, {"type": "end"})
        return

    # ---- Message loop + watchdogs ----
    call_ended = asyncio.Event()
    chat_lock = asyncio.Lock()

    async def message_loop():
        nonlocal cancel_event
        try:
            while not call_ended.is_set():
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "prompt":
                    voice_prompt = msg.get("voicePrompt", "")
                    if not voice_prompt.strip():
                        continue

                    logger.info("CR >>> User: %s", voice_prompt)
                    call_session.append_user_transcript(voice_prompt)

                    cancel_event.set()
                    cancel_event = asyncio.Event()

                    async with chat_lock:
                        await _gemini_respond(
                            chat, voice_prompt, call_session, websocket,
                            cancel_event,
                        )

                elif msg_type == "interrupt":
                    utterance = msg.get("utteranceUntilInterrupt", "")
                    logger.info("CR: interrupted after: '%s'", utterance[:100])
                    cancel_event.set()

                elif msg_type == "dtmf":
                    logger.info("CR: DTMF: %s", msg.get("digit", ""))

                elif msg_type == "error":
                    logger.error("CR error: %s", msg.get("description", ""))

                elif msg_type != "setup":
                    logger.debug("CR: unknown: %s", msg_type)

        except WebSocketDisconnect:
            logger.info("CR: Twilio disconnected")
        except Exception as exc:
            logger.error("CR receive error: %s", exc, exc_info=True)
        finally:
            call_ended.set()

    async def watchdog_10min():
        """At 10 min: silent nudge to Gemini (NOT sent to TTS)."""
        await asyncio.sleep(WATCHDOG_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 10min watchdog")
        try:
            async with chat_lock:
                await _gemini_silent_nudge(
                    chat,
                    "You have been on the call for 10 minutes. You have up to "
                    "20 minutes total. If you haven't made a programme "
                    "recommendation yet, begin transitioning toward it. "
                    "Continue naturally — do not rush or mention time to the caller.",
                )
        except Exception as exc:
            logger.debug("10min watchdog failed: %s", exc)

    async def watchdog_15min():
        """At 15 min: silent nudge to begin wrapping up."""
        await asyncio.sleep(WATCHDOG_15_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 15min watchdog")
        try:
            async with chat_lock:
                await _gemini_silent_nudge(
                    chat,
                    "The call has reached 15 minutes. Begin wrapping up "
                    "naturally now. Summarize, make your recommendation "
                    "if not done, and move toward the commitment ask. "
                    "About 5 minutes left. Do not mention time to the caller.",
                )
        except Exception as exc:
            logger.debug("15min watchdog failed: %s", exc)

    async def watchdog_final():
        """At 19:20: silent nudge to close or offer callback."""
        await asyncio.sleep(WATCHDOG_FINAL_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 19:20 final watchdog")
        try:
            async with chat_lock:
                await _gemini_silent_nudge(
                    chat,
                    "The call is approaching 20 minutes. You MUST wrap up "
                    "within 30 seconds. If still covering important ground, "
                    "offer to call back. Otherwise close warmly. "
                    "ALWAYS call determine_call_outcome before ending.",
                )
        except Exception as exc:
            logger.debug("Final watchdog failed: %s", exc)

    # ---- Run tasks ----
    try:
        results = await asyncio.gather(
            message_loop(),
            watchdog_10min(),
            watchdog_15min(),
            watchdog_final(),
            return_exceptions=True,
        )
        for name, result in zip(
            ["rx", "wd10", "wd15", "wdF"], results
        ):
            if isinstance(result, Exception):
                logger.error("CR '%s' failed: %s", name, result)
    finally:
        if call_session.watchdog_task and not call_session.watchdog_task.done():
            call_session.watchdog_task.cancel()
            try:
                await call_session.watchdog_task
            except asyncio.CancelledError:
                pass

        await process_call_end(call_session)
        duration = int(call_session.elapsed_seconds)
        await log_event(
            "cr_call_ended",
            f"CR call ended for lead {lead_id} (duration={duration}s)",
            lead_id=lead_id,
            metadata={"duration_seconds": duration, "call_sid": call_sid},
        )


# ---------------------------------------------------------------------------
# Gemini response handling
# ---------------------------------------------------------------------------


async def _gemini_respond(
    chat,
    text: str,
    call_session: CallSession,
    websocket: WebSocket,
    cancel_event: asyncio.Event,
) -> None:
    """Send text to Gemini, send response sentence-by-sentence to CR TTS."""
    response = await chat.send_message(text)

    # Handle tool call chains
    max_rounds = 5
    for _ in range(max_rounds):
        fcs = _extract_function_calls(response)
        if not fcs:
            break

        fr_parts = []
        for fc in fcs:
            result = _handle_tool_call(fc.name, fc.args or {}, call_session)
            logger.info("CR tool: %s -> %s", fc.name, result)
            fr_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response=result,
                    )
                )
            )
        response = await chat.send_message(fr_parts)

    # Extract text
    try:
        text_response = response.text
    except (ValueError, AttributeError):
        text_response = None

    if not text_response:
        logger.warning("CR: empty response")
        return

    if cancel_event.is_set():
        logger.info("CR: response cancelled, not sending TTS")
        call_session.append_agent_transcript(text_response)
        return

    # Send sentence-by-sentence for immediate TTS
    sentences = _split_sentences(text_response)
    if not sentences:
        sentences = [text_response]

    for sentence in sentences:
        if cancel_event.is_set():
            break
        await _send_json(websocket, {
            "type": "text",
            "token": sentence,
            "last": True,
        })

    logger.info("CR <<< Sarah: %s", text_response[:200])
    call_session.append_agent_transcript(text_response)


async def _gemini_silent_nudge(chat, signal: str) -> None:
    """Send a silent signal to Gemini — response is NOT sent to TTS.

    The signal adjusts Gemini's behavior for subsequent turns.
    Gemini's response is consumed (kept in chat history) but discarded.
    """
    response = await chat.send_message(
        f"[SYSTEM SIGNAL — INTERNAL ONLY, NEVER SPEAK THIS] {signal}"
    )

    # Handle any tool calls triggered by the nudge
    max_rounds = 3
    for _ in range(max_rounds):
        fcs = _extract_function_calls(response)
        if not fcs:
            break
        # Tool calls from nudge — unlikely but handle gracefully
        fr_parts = []
        for fc in fcs:
            logger.info("CR nudge triggered tool: %s", fc.name)
            fr_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"status": "acknowledged"},
                    )
                )
            )
        response = await chat.send_message(fr_parts)

    # Log but do NOT send to TTS
    try:
        nudge_response = response.text
        logger.info("CR nudge response (silent): %s", nudge_response[:100])
    except (ValueError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_function_calls(response) -> list:
    """Extract FunctionCall objects from a GenerateContentResponse."""
    calls = []
    try:
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            calls.append(part.function_call)
    except Exception as exc:
        logger.warning("CR: extract fc failed: %s", exc)
    return calls


async def _send_json(websocket: WebSocket, data: dict) -> bool:
    """Send JSON to WebSocket, return False if disconnected."""
    try:
        await websocket.send_text(json.dumps(data))
        return True
    except (WebSocketDisconnect, Exception):
        return False
