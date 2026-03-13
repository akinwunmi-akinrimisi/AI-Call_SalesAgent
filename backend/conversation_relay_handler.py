"""Twilio ConversationRelay handler — streaming text bridge to Gemini Chat API.

ConversationRelay handles STT (caller speech -> text) and TTS (text -> caller audio).
We bridge text between ConversationRelay and Gemini Chat API with:

- **Streaming**: Uses Gemini send_message_stream for low-latency first response
- **Sentence-level TTS**: Sends each sentence with last=true for immediate playback
- **Interrupt handling**: Cancels current response when caller interrupts;
  asks caller to repeat if interrupt was unclear
- **Multi-stage watchdog**: 10min nudge, 15min wrap-up, 19:20 callback offer

    Caller speaks -> Twilio STT -> {"type":"prompt","voicePrompt":"..."} -> WebSocket
    -> chat.send_message_stream(text) -> Gemini
    -> sentence chunks -> {"type":"text","token":"sentence","last":true} x N
    -> Twilio TTS -> Caller hears each sentence immediately

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

# Sentence boundary: punctuation followed by space + capital letter or quote
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

    # Voice: Google Chirp3-HD — most human-like generative voice
    # Kore = warm, conversational female voice. No "Google." prefix for CR.
    # Fallback order if needed: Aoede, Leda, Zephyr (all female Chirp3-HD)
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<ConversationRelay url="{ws_url}/ws/conversation-relay" '
        f'voice="en-US-Chirp3-HD-Kore" '
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
    logger.info("ConversationRelay: WebSocket connected")

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
            "CR setup: callSid=%s lead_id=%s from=%s to=%s",
            call_sid, lead_id, msg.get("from"), msg.get("to"),
        )
    except asyncio.TimeoutError:
        logger.error("CR: setup timeout")
        await websocket.close(code=4000, reason="Setup timeout")
        return
    except (WebSocketDisconnect, Exception) as exc:
        logger.error("CR: setup failed: %s", exc)
        return

    if not lead_id:
        logger.error("CR: no lead_id in customParameters")
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
    logger.info("CR: Gemini Chat created (model=%s, streaming)", model_name)

    # ---- Call session ----
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    asyncio.create_task(log_event(
        "cr_call_started",
        f"ConversationRelay call started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
        metadata={"call_sid": call_sid},
    ))

    # ---- Interrupt / cancel tracking ----
    cancel_event = asyncio.Event()

    # ---- Send greeting ----
    try:
        await _gemini_respond(chat, "Hello", call_session, websocket, cancel_event)
    except Exception as exc:
        logger.error("CR: greeting failed: %s", exc, exc_info=True)
        await _send_json(websocket, {"type": "end"})
        return

    # ---- Message loop + multi-stage watchdog ----
    call_ended = asyncio.Event()
    chat_lock = asyncio.Lock()

    async def message_loop():
        """Receive ConversationRelay messages and forward to Gemini."""
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

                    logger.info("CR >>> User said: %s", voice_prompt)
                    call_session.append_user_transcript(voice_prompt)

                    # Cancel any ongoing response
                    cancel_event.set()
                    cancel_event = asyncio.Event()

                    async with chat_lock:
                        await _gemini_respond(
                            chat, voice_prompt, call_session, websocket,
                            cancel_event,
                        )

                elif msg_type == "interrupt":
                    utterance = msg.get("utteranceUntilInterrupt", "")
                    logger.info(
                        "CR: interrupted after: '%s'", utterance[:100],
                    )
                    # Stop current TTS output
                    cancel_event.set()

                elif msg_type == "dtmf":
                    logger.info("CR: DTMF digit: %s", msg.get("digit", ""))

                elif msg_type == "error":
                    logger.error("CR error: %s", msg.get("description", ""))

                elif msg_type == "setup":
                    pass

                else:
                    logger.debug("CR: unknown msg type: %s", msg_type)

        except WebSocketDisconnect:
            logger.info("CR: Twilio disconnected")
        except Exception as exc:
            logger.error("CR receive error: %s", exc, exc_info=True)
        finally:
            call_ended.set()

    async def watchdog_10min():
        """At 10 minutes: gentle time-check nudge."""
        await asyncio.sleep(WATCHDOG_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 10-minute watchdog fired")
        try:
            async with chat_lock:
                await _gemini_respond(
                    chat,
                    (
                        "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                        "The call has reached 10 minutes. You have up to 20 "
                        "minutes total. If you haven't made a programme "
                        "recommendation yet, begin transitioning toward it. "
                        "Continue naturally — do not rush or mention time."
                    ),
                    call_session,
                    websocket,
                    cancel_event,
                )
        except Exception as exc:
            logger.debug("10min watchdog failed: %s", exc)

    async def watchdog_15min():
        """At 15 minutes: begin wrapping up."""
        await asyncio.sleep(WATCHDOG_15_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 15-minute watchdog fired")
        try:
            async with chat_lock:
                await _gemini_respond(
                    chat,
                    (
                        "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                        "The call has reached 15 minutes. Begin wrapping up "
                        "naturally now. Summarize what you've discussed, make "
                        "your recommendation if not done, and move toward the "
                        "commitment ask. You have about 5 minutes left."
                    ),
                    call_session,
                    websocket,
                    cancel_event,
                )
        except Exception as exc:
            logger.debug("15min watchdog failed: %s", exc)

    async def watchdog_final():
        """At 19:20: offer to call back if needed."""
        await asyncio.sleep(WATCHDOG_FINAL_SECONDS)
        if call_ended.is_set():
            return
        logger.info("CR: 19:20 final watchdog fired")
        try:
            async with chat_lock:
                await _gemini_respond(
                    chat,
                    (
                        "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
                        "The call is approaching the 20-minute limit. You "
                        "MUST wrap up within 30 seconds. If you still have "
                        "important things to cover, say something like: "
                        "'I'm conscious of your time — would it be okay if "
                        "I called you right back so we can finish up properly?' "
                        "If the conversation is naturally concluding, just "
                        "close warmly. ALWAYS call determine_call_outcome "
                        "before the call ends."
                    ),
                    call_session,
                    websocket,
                    cancel_event,
                )
        except Exception as exc:
            logger.debug("Final watchdog failed: %s", exc)

    # ---- Run concurrent tasks ----
    watchdog_tasks = []
    try:
        results = await asyncio.gather(
            message_loop(),
            watchdog_10min(),
            watchdog_15min(),
            watchdog_final(),
            return_exceptions=True,
        )
        for name, result in zip(
            ["twilio_rx", "wd_10m", "wd_15m", "wd_final"], results
        ):
            if isinstance(result, Exception):
                logger.error("CR task '%s' failed: %s", name, result)
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
            f"ConversationRelay call ended for lead {lead_id} (duration={duration}s)",
            lead_id=lead_id,
            metadata={
                "duration_seconds": duration,
                "call_sid": call_sid,
            },
        )


# ---------------------------------------------------------------------------
# Gemini response handling — streaming with sentence-level TTS
# ---------------------------------------------------------------------------


async def _gemini_respond(
    chat,
    text: str,
    call_session: CallSession,
    websocket: WebSocket,
    cancel_event: asyncio.Event,
) -> None:
    """Send text to Gemini, stream response sentence-by-sentence to CR.

    Uses send_message_stream for low first-token latency. Falls back
    to non-streaming if streaming fails.
    """
    try:
        await _gemini_stream_respond(
            chat, text, call_session, websocket, cancel_event,
        )
    except Exception as exc:
        logger.warning("CR: streaming failed (%s), falling back", exc)
        await _gemini_nonstream_respond(
            chat, text, call_session, websocket, cancel_event,
        )


async def _gemini_stream_respond(
    chat,
    text: str,
    call_session: CallSession,
    websocket: WebSocket,
    cancel_event: asyncio.Event,
) -> None:
    """Stream Gemini response sentence-by-sentence for minimum latency."""
    buffer = ""
    all_sent: list[str] = []
    function_calls: list = []
    cancelled = False

    # FIX: await the stream coroutine, THEN iterate
    stream = await chat.send_message_stream(text)
    async for chunk in stream:
        # Always consume full stream for chat history consistency
        if cancel_event.is_set():
            cancelled = True

        if cancelled:
            continue

        # Detect function calls
        _collect_function_calls(chunk, function_calls)

        # Extract text
        try:
            chunk_text = chunk.text
        except (ValueError, AttributeError):
            continue

        if not chunk_text:
            continue

        buffer += chunk_text

        # Send complete sentences immediately for low-latency TTS
        while not cancelled:
            sentence, rest = _pop_sentence(buffer)
            if sentence is None:
                break
            buffer = rest
            all_sent.append(sentence)

            if not await _send_json(websocket, {
                "type": "text",
                "token": sentence,
                "last": True,
            }):
                cancelled = True
                break

    # Handle tool calls (non-streaming for tool responses)
    if function_calls and not cancel_event.is_set():
        tool_text = await _handle_tool_rounds(
            chat, function_calls, call_session,
        )
        if tool_text and not cancel_event.is_set():
            buffer += tool_text

    # Flush remaining buffer
    remaining = buffer.strip()
    if remaining and not cancel_event.is_set():
        all_sent.append(remaining)
        await _send_json(websocket, {
            "type": "text",
            "token": remaining,
            "last": True,
        })

    # Record transcript
    full_text = " ".join(all_sent)
    if full_text:
        logger.info("CR <<< Sarah: %s", full_text[:200])
        call_session.append_agent_transcript(full_text)
    elif not cancelled:
        logger.warning("CR: Gemini returned no text")


async def _gemini_nonstream_respond(
    chat,
    text: str,
    call_session: CallSession,
    websocket: WebSocket,
    cancel_event: asyncio.Event,
) -> None:
    """Fallback: non-streaming response with sentence-level TTS."""
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
                        name=fc.name,
                        response=result,
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
        logger.warning("CR: empty non-streaming response")
        await _send_json(websocket, {"type": "text", "token": "", "last": True})
        return

    if cancel_event.is_set():
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


# ---------------------------------------------------------------------------
# Tool call handling
# ---------------------------------------------------------------------------


async def _handle_tool_rounds(
    chat,
    function_calls: list,
    call_session: CallSession,
) -> str | None:
    """Execute tool calls and return final text response."""
    max_rounds = 5
    for _ in range(max_rounds):
        fr_parts = []
        for fc in function_calls:
            result = _handle_tool_call(fc.name, fc.args or {}, call_session)
            logger.info("CR tool: %s -> %s", fc.name, result)
            fr_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response=result,
                    )
                )
            )

        function_calls = []
        response = await chat.send_message(fr_parts)

        new_fcs = _extract_function_calls(response)
        if new_fcs:
            function_calls = new_fcs
            continue

        try:
            return response.text
        except (ValueError, AttributeError):
            return None

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pop_sentence(text: str) -> tuple[str | None, str]:
    """Extract first complete sentence from buffer.

    Returns (sentence, remainder) or (None, text) if none found yet.
    """
    patterns = [
        r'([^.!?]*[.!?]+)\s+(?=[A-Z"\'])',
        r'(.*?\.\.\.)\s+',
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            sentence = match.group(1).strip()
            rest = text[match.end():].lstrip()
            if sentence:
                return sentence, rest
    return None, text


def _collect_function_calls(chunk, dest: list) -> None:
    """Extract function calls from a streaming chunk."""
    try:
        if chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            dest.append(part.function_call)
    except Exception:
        pass


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
        logger.warning("CR: extract function calls failed: %s", exc)
    return calls


async def _send_json(websocket: WebSocket, data: dict) -> bool:
    """Send JSON to WebSocket, return False if disconnected."""
    try:
        await websocket.send_text(json.dumps(data))
        return True
    except (WebSocketDisconnect, Exception):
        return False
