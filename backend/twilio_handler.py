"""Twilio Media Streams integration for real phone calls.

Bridges Twilio's mulaw 8kHz audio with Gemini Live API's PCM audio.
Handles outbound call initiation, TwiML generation, Media Streams
WebSocket protocol, and interruption handling via clear events.

Audio conversion chain:
  Twilio (mulaw 8kHz) → PCM 16kHz → Gemini Live API input
  Gemini output (PCM 24kHz) → mulaw 8kHz → Twilio playback

Exports:
    initiate_call: Start an outbound call via Twilio REST API.
    generate_twiml: Generate TwiML XML for Media Streams.
    handle_twilio_stream: WebSocket handler for Twilio ↔ Gemini bridging.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time

import audioop
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, VoiceResponse, Stream

from call_manager import CallSession, process_call_end
from config import config
from knowledge_loader import build_system_instruction, load_knowledge_base
from logger import log_event
from voice_handler import (
    TOOL_DECLARATIONS,
    VALID_OUTCOMES,
    WATCHDOG_SECONDS,
    _handle_tool_call,
    fetch_lead,
    get_firestore_client,
)

logger = logging.getLogger(__name__)


# ---- Audio Conversion ----

def mulaw_to_pcm16k(mulaw_bytes: bytes, ratecv_state=None):
    """Convert mulaw 8kHz → PCM16 16kHz for Gemini input.

    Returns (pcm_bytes, new_state). Pass state between calls for
    continuous resampling without discontinuities at chunk boundaries.
    """
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm_16k, new_state = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, ratecv_state)
    return pcm_16k, new_state


def pcm24k_to_mulaw8k(pcm_bytes: bytes) -> bytes:
    """Convert PCM16 24kHz from Gemini → mulaw 8kHz for Twilio.

    Uses audioop.ratecv for resampling (stdlib, no numpy/soxr needed).
    """
    pcm_8k, _ = audioop.ratecv(pcm_bytes, 2, 1, 24000, 8000, None)
    return audioop.lin2ulaw(pcm_8k, 2)


# ---- Twilio REST API ----

def get_twilio_client() -> TwilioClient:
    """Create Twilio REST client from config."""
    return TwilioClient(config.twilio_account_sid, config.twilio_auth_token)


async def initiate_call(lead_id: str, to_number: str, base_url: str) -> dict:
    """Initiate an outbound call via Twilio.

    Args:
        lead_id: UUID of the lead to call.
        to_number: Phone number in E.164 format (e.g., +447123456789).
        base_url: Service base URL for TwiML and status callbacks.

    Returns:
        Dict with call_sid and status.
    """
    client = get_twilio_client()

    twiml_url = f"{base_url}/twilio/voice?lead_id={lead_id}"

    # Run synchronous Twilio SDK call in thread pool
    call = await asyncio.to_thread(
        client.calls.create,
        to=to_number,
        from_=config.twilio_phone_number,
        url=twiml_url,
        record=True,
        recording_status_callback=f"{base_url}/twilio/recording?lead_id={lead_id}",
        status_callback=f"{base_url}/twilio/status?lead_id={lead_id}",
        status_callback_event=["completed", "failed", "busy", "no-answer"],
    )

    await log_event(
        "call_initiated",
        f"Outbound call to {to_number} for lead {lead_id}",
        lead_id=lead_id,
        metadata={"call_sid": call.sid, "to_number": to_number},
    )

    return {"call_sid": call.sid, "status": call.status}


def generate_twiml(lead_id: str, base_url: str) -> str:
    """Generate TwiML XML that connects to Media Streams.

    Args:
        lead_id: UUID of the lead (passed as stream parameter).
        base_url: Service URL (https:// converted to wss:// for stream).

    Returns:
        TwiML XML string.
    """
    response = VoiceResponse()
    connect = Connect()

    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream = Stream(url=f"{ws_url}/ws/twilio/stream")
    stream.parameter(name="lead_id", value=lead_id)

    connect.append(stream)
    response.append(connect)

    return str(response)


# ---- Twilio Media Streams WebSocket Handler ----

async def handle_twilio_stream(websocket: WebSocket) -> None:
    """Handle Twilio Media Streams WebSocket connection.

    Protocol flow:
    1. Twilio sends "connected" event
    2. Twilio sends "start" event with streamSid, callSid, customParameters
    3. We set up Gemini Live session using lead_id from parameters
    4. Twilio sends "media" events (base64 mulaw audio) → convert → Gemini
    5. Gemini audio → convert → send as "media" events back to Twilio
    6. Twilio sends "stop" when call ends

    Interruption handling:
    - When Gemini detects barge-in and stops generating, we send a "clear"
      event to Twilio to flush any queued audio, ensuring crisp interruption.
    """
    await websocket.accept()
    logger.info("Twilio Media Streams WebSocket connected")

    stream_sid: str | None = None
    call_sid: str | None = None
    lead_id: str | None = None

    # ---- Wait for start event ----
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("Twilio stream: connected (protocol=%s)", msg.get("protocol"))
                continue

            if event == "start":
                start_data = msg.get("start", {})
                stream_sid = start_data.get("streamSid")
                call_sid = start_data.get("callSid")
                custom_params = start_data.get("customParameters", {})
                lead_id = custom_params.get("lead_id", "")
                logger.info(
                    "Twilio stream started: streamSid=%s callSid=%s lead_id=%s",
                    stream_sid, call_sid, lead_id,
                )
                break

            logger.debug("Twilio stream: ignoring event '%s' before start", event)
    except (WebSocketDisconnect, Exception) as exc:
        logger.error("Twilio stream: failed during handshake: %s", exc)
        return

    if not lead_id:
        logger.error("Twilio stream: no lead_id in start parameters")
        await websocket.close(code=4000, reason="Missing lead_id")
        return

    # ---- Setup: fetch lead + KB (parallel) ----
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
            await websocket.close(code=4004, reason="Lead not found")
            return

        lead_name = lead.get("name", "there")
        system_instruction = build_system_instruction(lead_name, kb_content)
        logger.info(
            "Twilio call setup in %.1fs: lead=%s (%s)",
            time.time() - t0, lead_id, lead_name,
        )
    except Exception as exc:
        logger.error("Twilio call setup failed: %s", exc, exc_info=True)
        await websocket.close(code=4000, reason=str(exc)[:120])
        return

    # ---- Gemini Live session ----
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
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=TOOL_DECLARATIONS,
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=20,
                silence_duration_ms=500,
            ),
        ),
    )

    if is_native_audio:
        live_config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    live_config = types.LiveConnectConfig(**live_config_kwargs)

    # ---- Call session ----
    call_session = CallSession(lead_id=lead_id, lead_name=lead_name)

    asyncio.create_task(log_event(
        "twilio_call_started",
        f"Twilio voice call started for lead {lead_id} ({lead_name})",
        lead_id=lead_id,
        metadata={"call_sid": call_sid, "stream_sid": stream_sid},
    ))

    # ---- Streaming ----
    try:
        async with client.aio.live.connect(
            model=model_name,
            config=live_config,
        ) as session:
            logger.info("Gemini Live connected for Twilio call (lead=%s)", lead_id)

            # Trigger Sarah's greeting
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="Hello")],
                ),
                turn_complete=True,
            )

            # Track whether Sarah is currently speaking (for interruption detection)
            sarah_speaking = asyncio.Event()
            call_ended = asyncio.Event()

            # Gate: don't forward user audio until Sarah's greeting
            # finishes (turn_complete). Sending phone audio during the
            # greeting causes echo (phone mic picks up Sarah's voice)
            # which confuses Gemini's VAD and prevents it from responding.
            greeting_done = asyncio.Event()
            upstream_forwarded = 0
            upstream_discarded = 0

            # Buffer 5 Twilio chunks (~100ms) and send as one batch.
            # Reduces send rate from 50/sec to 10/sec, matching browser.
            UPSTREAM_BUFFER_CHUNKS = 5

            async def upstream_twilio():
                """Receive mulaw from Twilio → gate → buffer → convert → Gemini."""
                nonlocal upstream_forwarded, upstream_discarded
                mulaw_buffer = bytearray()
                chunk_count = 0
                ratecv_state = None  # preserve resampling state across batches
                try:
                    while not call_ended.is_set():
                        raw = await websocket.receive_text()
                        msg = json.loads(raw)
                        event = msg.get("event")

                        if event == "media":
                            # Discard all audio until greeting finishes
                            if not greeting_done.is_set():
                                upstream_discarded += 1
                                continue

                            payload = msg["media"]["payload"]
                            mulaw_buffer.extend(base64.b64decode(payload))
                            chunk_count += 1

                            if chunk_count >= UPSTREAM_BUFFER_CHUNKS:
                                pcm_16k, ratecv_state = mulaw_to_pcm16k(
                                    bytes(mulaw_buffer), ratecv_state
                                )
                                upstream_forwarded += 1
                                rms = audioop.rms(pcm_16k, 2)
                                if upstream_forwarded <= 10 or upstream_forwarded % 20 == 0:
                                    logger.info(
                                        "Twilio upstream batch #%d: %d bytes "
                                        "rms=%d (discarded %d during greeting)",
                                        upstream_forwarded, len(pcm_16k),
                                        rms, upstream_discarded,
                                    )
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=pcm_16k,
                                    )
                                )
                                mulaw_buffer.clear()
                                chunk_count = 0

                        elif event == "stop":
                            # Flush remaining buffer
                            if mulaw_buffer:
                                pcm_16k, _ = mulaw_to_pcm16k(
                                    bytes(mulaw_buffer), ratecv_state
                                )
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=pcm_16k,
                                    )
                                )
                            logger.info(
                                "Twilio stream stopped (fwd=%d, discarded=%d)",
                                upstream_forwarded, upstream_discarded,
                            )
                            call_ended.set()
                            return

                except WebSocketDisconnect:
                    logger.info("Twilio WebSocket disconnected (upstream, fwd=%d)",
                                upstream_forwarded)
                    call_ended.set()
                except Exception as exc:
                    logger.error("Twilio upstream error: %s", exc, exc_info=True)
                    call_ended.set()

            downstream_count = 0

            async def downstream_gemini():
                """Receive Gemini audio → convert → send to Twilio as mulaw."""
                nonlocal downstream_count
                was_speaking = False
                logger.info("Downstream: listening for Gemini responses...")
                try:
                    async for msg in session.receive():
                        if call_ended.is_set():
                            return

                        downstream_count += 1
                        if downstream_count <= 5 or downstream_count % 50 == 0:
                            logger.info(
                                "Twilio downstream msg #%d: %s",
                                downstream_count, type(msg).__name__,
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

                            # Audio from Gemini → convert and send to Twilio
                            if sc.model_turn and sc.model_turn.parts:
                                if not was_speaking:
                                    was_speaking = True
                                    sarah_speaking.set()

                                for part in sc.model_turn.parts:
                                    if (
                                        hasattr(part, "inline_data")
                                        and part.inline_data
                                        and part.inline_data.data
                                    ):
                                        mulaw = pcm24k_to_mulaw8k(
                                            part.inline_data.data
                                        )
                                        payload = base64.b64encode(mulaw).decode(
                                            "ascii"
                                        )
                                        try:
                                            await websocket.send_text(
                                                json.dumps(
                                                    {
                                                        "event": "media",
                                                        "streamSid": stream_sid,
                                                        "media": {
                                                            "payload": payload
                                                        },
                                                    }
                                                )
                                            )
                                        except (WebSocketDisconnect, Exception) as exc:
                                            logger.info("Twilio send failed: %s", exc)
                                            call_ended.set()
                                            return

                            # Turn complete — Sarah stopped speaking
                            if hasattr(sc, "turn_complete") and sc.turn_complete:
                                logger.info("Sarah turn complete (was_speaking=%s)", was_speaking)
                                was_speaking = False
                                sarah_speaking.clear()
                                # Ungate upstream audio now that greeting is done
                                if not greeting_done.is_set():
                                    greeting_done.set()
                                    logger.info(
                                        "Greeting done, upstream ungated "
                                        "(discarded %d chunks during greeting)",
                                        upstream_discarded,
                                    )
                                    # Nudge Gemini to listen for realtime audio
                                    # after the text-triggered greeting exchange
                                    try:
                                        await session.send_realtime_input(
                                            text="[listening]"
                                        )
                                        logger.info("Sent realtime text nudge")
                                    except Exception as exc:
                                        logger.warning("Realtime text nudge failed: %s", exc)

                            # Interruption: Gemini detected user barge-in
                            if hasattr(sc, "interrupted") and sc.interrupted:
                                logger.info("Barge-in detected, clearing Twilio buffer")
                                was_speaking = False
                                sarah_speaking.clear()
                                # Send clear event to flush Twilio's audio buffer
                                try:
                                    await websocket.send_text(
                                        json.dumps(
                                            {
                                                "event": "clear",
                                                "streamSid": stream_sid,
                                            }
                                        )
                                    )
                                except (WebSocketDisconnect, Exception) as exc:
                                    logger.info("Clear event send failed: %s", exc)
                                    call_ended.set()
                                    return

                            # User speech transcription
                            if (
                                hasattr(sc, "input_transcription")
                                and sc.input_transcription
                                and sc.input_transcription.text
                            ):
                                logger.info("User said: %s", sc.input_transcription.text)
                                call_session.append_user_transcript(
                                    sc.input_transcription.text
                                )

                            # Agent speech transcription
                            if (
                                hasattr(sc, "output_transcription")
                                and sc.output_transcription
                                and sc.output_transcription.text
                            ):
                                logger.info("Sarah said: %s", sc.output_transcription.text)
                                call_session.append_agent_transcript(
                                    sc.output_transcription.text
                                )

                except WebSocketDisconnect:
                    logger.info("Twilio downstream: WebSocket disconnected")
                except Exception as exc:
                    logger.error("Gemini downstream error: %s", exc, exc_info=True)

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
                    upstream_twilio(),
                    downstream_gemini(),
                    watchdog(),
                    return_exceptions=True,
                )
                # Log any exceptions from the tasks
                for i, (name, result) in enumerate(
                    zip(["upstream", "downstream", "watchdog"], results)
                ):
                    if isinstance(result, Exception):
                        logger.error(
                            "Twilio task '%s' failed: %s", name, result,
                            exc_info=(type(result), result, result.__traceback__),
                        )
                logger.info(
                    "Twilio call tasks ended (upstream=%d, downstream=%d)",
                    upstream_forwarded, downstream_count,
                )
            finally:
                if call_session.watchdog_task and not call_session.watchdog_task.done():
                    call_session.watchdog_task.cancel()
                    try:
                        await call_session.watchdog_task
                    except asyncio.CancelledError:
                        pass

    except Exception as exc:
        logger.error(
            "Gemini session failed for Twilio call (lead=%s): %s",
            lead_id, exc, exc_info=True,
        )

    finally:
        await process_call_end(call_session)

        duration = int(call_session.elapsed_seconds)
        await log_event(
            "twilio_call_ended",
            f"Twilio call ended for lead {lead_id} (duration={duration}s)",
            lead_id=lead_id,
            metadata={
                "duration_seconds": duration,
                "call_sid": call_sid,
                "stream_sid": stream_sid,
            },
        )
