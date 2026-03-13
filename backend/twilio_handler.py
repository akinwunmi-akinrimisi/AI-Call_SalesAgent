"""Twilio Media Streams integration for real phone calls.

Bridges Twilio's mulaw 8kHz audio with Gemini Live API's PCM audio.
Handles outbound call initiation, TwiML generation, Media Streams
WebSocket protocol, and interruption handling via clear events.

Audio conversion chain:
  Twilio (mulaw 8kHz) → PCM 8kHz → soxr resample → PCM 16kHz → Gemini Live API
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
import numpy as np
import soxr
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

# Shared inbound audio queues keyed by callSid.
# The <Start><Stream> one-way handler pushes audio here;
# the <Connect><Stream> bidirectional handler reads from here.
_inbound_queues: dict[str, asyncio.Queue] = {}


# ---- Audio Conversion ----

def mulaw_to_pcm16k(mulaw_bytes: bytes, ratecv_state=None):
    """Convert mulaw 8kHz → PCM16 16kHz for Gemini input.

    Uses soxr for high-quality resampling (matching Google's official
    reference implementation). The ratecv_state parameter is kept for
    API compatibility but is ignored — soxr handles state internally.
    """
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    samples_8k = np.frombuffer(pcm_8k, dtype=np.int16).astype(np.float64)
    samples_16k = soxr.resample(samples_8k, 8000, 16000)
    pcm_16k = samples_16k.astype(np.int16).tobytes()
    return pcm_16k, None


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
    """Generate TwiML XML with hybrid dual-stream architecture.

    Uses two streams to work around Twilio's bidirectional stream
    silencing inbound audio when outbound audio is being sent:

    1. <Start><Stream> (one-way monitor) — reliably receives caller audio
    2. <Connect><Stream> (bidirectional) — sends Gemini audio to caller

    Args:
        lead_id: UUID of the lead (passed as stream parameter).
        base_url: Service URL (https:// converted to wss:// for stream).

    Returns:
        TwiML XML string.
    """
    response = VoiceResponse()
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    # 1. One-way monitor — receives real inbound audio
    response.start().stream(
        url=f"{ws_url}/ws/twilio/inbound",
        track="inbound_track",
        name="inbound_monitor",
    )

    # 2. Bidirectional — for sending Gemini audio back to caller
    connect = Connect()
    stream = Stream(url=f"{ws_url}/ws/twilio/stream")
    stream.parameter(name="lead_id", value=lead_id)
    connect.append(stream)
    response.append(connect)

    return str(response)


def generate_diagnostic_twiml(base_url: str, mode: str = "oneway") -> str:
    """Generate TwiML for stream diagnostics.

    Modes:
      oneway — <Start><Stream> monitor + <Say> + <Gather>
      bidir_silent — <Connect><Stream> bidirectional, handler receives only
      bidir_hybrid — <Start><Stream> for inbound + <Connect><Stream> for outbound
    """
    response = VoiceResponse()
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    if mode == "bidir_silent":
        # Bidirectional stream but handler will NOT send audio back.
        # Tests if bidirectional setup itself silences inbound.
        connect = Connect()
        stream = Stream(url=f"{ws_url}/ws/twilio/diagnostic")
        connect.append(stream)
        response.append(connect)

    elif mode == "bidir_hybrid":
        # One-way monitor for inbound audio + bidirectional for sending
        # Gemini audio back. Two separate WebSocket connections.
        response.start().stream(
            url=f"{ws_url}/ws/twilio/diagnostic",
            track="inbound_track",
            name="inbound_monitor",
        )
        connect = Connect()
        stream = Stream(url=f"{ws_url}/ws/twilio/stream")
        stream.parameter(name="lead_id", value="9c793b38-65ce-422f-8571-718b34541fe6")
        connect.append(stream)
        response.append(connect)

    else:  # oneway
        response.start().stream(
            url=f"{ws_url}/ws/twilio/diagnostic",
            track="inbound_track",
        )
        from twilio.twiml.voice_response import Gather
        gather = Gather(
            input="speech", timeout=30,
            action=f"{base_url}/twilio/diagnostic-done",
        )
        gather.say(
            "This is a diagnostic test. Please speak now. "
            "Say anything for about ten seconds.",
            voice="Polly.Amy",
        )
        response.append(gather)
        response.say("Thank you. Diagnostic complete.", voice="Polly.Amy")

    return str(response)


async def handle_diagnostic_stream(websocket: WebSocket) -> None:
    """Lightweight WebSocket handler for one-way stream diagnostic.

    Logs raw mulaw bytes and RMS for every chunk to determine if
    Twilio sends real audio in one-way monitor mode.
    """
    await websocket.accept()
    logger.info("DIAGNOSTIC: WebSocket connected")

    chunk_count = 0
    non_silence_count = 0

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("DIAGNOSTIC: protocol=%s", msg.get("protocol"))
                continue

            if event == "start":
                start_data = msg.get("start", {})
                logger.info(
                    "DIAGNOSTIC: stream started sid=%s track=%s",
                    start_data.get("streamSid"),
                    start_data.get("tracks", []),
                )
                continue

            if event == "media":
                chunk_count += 1
                media_data = msg.get("media", {})
                payload = media_data.get("payload", "")
                mulaw_bytes = base64.b64decode(payload)
                pcm = audioop.ulaw2lin(mulaw_bytes, 2)
                rms = audioop.rms(pcm, 2)

                if rms > 50:
                    non_silence_count += 1

                # Log every chunk for first 20, then every 50th
                if chunk_count <= 20 or chunk_count % 50 == 0:
                    sample_hex = mulaw_bytes[:8].hex()
                    logger.info(
                        "DIAGNOSTIC chunk #%d: len=%d rms=%d "
                        "track=%s first_bytes=%s (non_silence=%d/%d)",
                        chunk_count, len(mulaw_bytes), rms,
                        media_data.get("track", "?"), sample_hex,
                        non_silence_count, chunk_count,
                    )

            elif event == "stop":
                logger.info(
                    "DIAGNOSTIC: stream stopped. "
                    "total_chunks=%d non_silence=%d",
                    chunk_count, non_silence_count,
                )
                break

    except WebSocketDisconnect:
        logger.info(
            "DIAGNOSTIC: disconnected. chunks=%d non_silence=%d",
            chunk_count, non_silence_count,
        )
    except Exception as exc:
        logger.error("DIAGNOSTIC error: %s", exc, exc_info=True)


# ---- Inbound Audio Monitor (one-way <Start><Stream>) ----

async def handle_inbound_monitor(websocket: WebSocket) -> None:
    """Handle one-way <Start><Stream> that receives real caller audio.

    Pushes decoded mulaw bytes into _inbound_queues[callSid] for the
    bidirectional handler to read and forward to Gemini.
    """
    await websocket.accept()
    logger.info("Inbound monitor: WebSocket connected")

    call_sid: str | None = None
    chunk_count = 0
    non_silence = 0

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("Inbound monitor: protocol=%s", msg.get("protocol"))
                continue

            if event == "start":
                start_data = msg.get("start", {})
                call_sid = start_data.get("callSid")
                # Create queue for this call
                _inbound_queues[call_sid] = asyncio.Queue(maxsize=500)
                logger.info(
                    "Inbound monitor started: callSid=%s sid=%s",
                    call_sid, start_data.get("streamSid"),
                )
                continue

            if event == "media":
                if not call_sid:
                    continue
                chunk_count += 1
                media_data = msg.get("media", {})
                payload = media_data.get("payload", "")
                mulaw_bytes = base64.b64decode(payload)

                # Push raw mulaw to shared queue (non-blocking)
                queue = _inbound_queues.get(call_sid)
                if queue:
                    try:
                        queue.put_nowait(mulaw_bytes)
                    except asyncio.QueueFull:
                        pass  # Drop oldest if overwhelmed

                # Periodic logging
                pcm = audioop.ulaw2lin(mulaw_bytes, 2)
                rms = audioop.rms(pcm, 2)
                if rms > 50:
                    non_silence += 1
                if chunk_count <= 5 or chunk_count % 100 == 0:
                    logger.info(
                        "Inbound monitor #%d: rms=%d non_silence=%d/%d",
                        chunk_count, rms, non_silence, chunk_count,
                    )

            elif event == "stop":
                logger.info(
                    "Inbound monitor stopped: chunks=%d non_silence=%d",
                    chunk_count, non_silence,
                )
                # Signal end to the queue consumer
                if call_sid and call_sid in _inbound_queues:
                    await _inbound_queues[call_sid].put(None)
                break

    except WebSocketDisconnect:
        logger.info("Inbound monitor disconnected: chunks=%d", chunk_count)
    except Exception as exc:
        logger.error("Inbound monitor error: %s", exc, exc_info=True)
    finally:
        # Clean up queue after a delay (let consumer drain)
        if call_sid and call_sid in _inbound_queues:
            await _inbound_queues[call_sid].put(None)
            await asyncio.sleep(2)
            _inbound_queues.pop(call_sid, None)


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
                silence_duration_ms=300,
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

            # Trigger Sarah's greeting via realtime input (NOT
            # send_client_content) so the session stays in realtime
            # mode. Using send_client_content followed by
            # send_realtime_input caused Gemini to ignore audio.
            await session.send_realtime_input(
                text="Hello"
            )
            logger.info("Sent greeting trigger via send_realtime_input(text)")

            # Track whether Sarah is currently speaking (for interruption detection)
            sarah_speaking = asyncio.Event()
            call_ended = asyncio.Event()

            # Gate: don't forward user audio until Sarah's greeting
            # audio starts arriving.
            greeting_started = asyncio.Event()
            upstream_forwarded = 0

            async def drain_bidir_ws():
                """Drain media events from the bidirectional WebSocket.

                The bidirectional stream's inbound audio is silence (due to
                Twilio AEC), so we just consume and discard events to keep
                the WebSocket alive. Real audio comes from the one-way
                inbound monitor via _inbound_queues.
                """
                try:
                    while not call_ended.is_set():
                        raw = await websocket.receive_text()
                        msg = json.loads(raw)
                        if msg.get("event") == "stop":
                            logger.info("Bidirectional stream stopped")
                            call_ended.set()
                            return
                except WebSocketDisconnect:
                    logger.info("Bidirectional WebSocket disconnected")
                    call_ended.set()
                except Exception as exc:
                    logger.error("Bidir drain error: %s", exc, exc_info=True)
                    call_ended.set()

            async def upstream_from_monitor():
                """Read real audio from one-way inbound monitor queue,
                resample to 16kHz PCM via soxr, send to Gemini.

                Uses high-quality soxr resampling (matching Google's official
                reference implementation) instead of audioop.ratecv which
                introduces artifacts that break Gemini's VAD.
                """
                nonlocal upstream_forwarded

                # Wait for the inbound monitor queue to appear
                queue = None
                for _ in range(50):  # up to 5 seconds
                    queue = _inbound_queues.get(call_sid)
                    if queue:
                        break
                    await asyncio.sleep(0.1)

                if not queue:
                    logger.error("No inbound monitor queue for callSid=%s", call_sid)
                    return

                logger.info("Upstream: connected to inbound monitor queue (callSid=%s)", call_sid)

                try:
                    while not call_ended.is_set():
                        # Wait for greeting to start before forwarding
                        if not greeting_started.is_set():
                            try:
                                mulaw_bytes = await asyncio.wait_for(queue.get(), timeout=0.5)
                            except asyncio.TimeoutError:
                                continue
                            if mulaw_bytes is None:
                                logger.info("Inbound monitor ended (pre-gate)")
                                call_ended.set()
                                return
                            # Discard pre-greeting audio
                            continue

                        # Read from queue with timeout
                        try:
                            mulaw_bytes = await asyncio.wait_for(queue.get(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        if mulaw_bytes is None:
                            logger.info("Inbound monitor ended")
                            call_ended.set()
                            return

                        # Decode mulaw → PCM 8kHz
                        pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)

                        # High-quality resample 8kHz → 16kHz using soxr
                        # (matches Google's official reference implementation)
                        samples_8k = np.frombuffer(pcm_8k, dtype=np.int16).astype(np.float64)
                        samples_16k = soxr.resample(samples_8k, 8000, 16000)
                        pcm_16k = samples_16k.astype(np.int16).tobytes()

                        upstream_forwarded += 1
                        if upstream_forwarded <= 20 or upstream_forwarded % 100 == 0:
                            rms = audioop.rms(pcm_16k, 2)
                            logger.info(
                                "Upstream #%d: %d bytes rms=%d (soxr 16kHz→Gemini)",
                                upstream_forwarded, len(pcm_16k), rms,
                            )

                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm_16k,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

                except Exception as exc:
                    logger.error("Upstream monitor error: %s", exc, exc_info=True)
                    call_ended.set()

            async def heartbeat():
                """Send silent audio every 5 seconds to keep Gemini stream alive.

                Google's reference implementation sends 320 bytes of zeros
                (10ms at 16kHz) as a keepalive. This prevents the session
                from timing out during pauses.
                """
                silence = bytes(320)  # 10ms of silence at 16kHz, 16-bit
                try:
                    while not call_ended.is_set():
                        await asyncio.sleep(5.0)
                        if call_ended.is_set():
                            return
                        if greeting_started.is_set():
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=silence,
                                    mime_type="audio/pcm;rate=16000",
                                )
                            )
                except Exception as exc:
                    logger.debug("Heartbeat ended: %s", exc)

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

                                # Ungate upstream on first model audio
                                # (matches browser handler behavior)
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
                                logger.info(
                                    "Sarah turn complete (was_speaking=%s, "
                                    "upstream_fwd=%d)",
                                    was_speaking, upstream_forwarded,
                                )
                                was_speaking = False
                                sarah_speaking.clear()

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
                    drain_bidir_ws(),
                    upstream_from_monitor(),
                    downstream_gemini(),
                    heartbeat(),
                    watchdog(),
                    return_exceptions=True,
                )
                task_names = ["drain_bidir", "upstream_monitor", "downstream", "heartbeat", "watchdog"]
                for name, result in zip(task_names, results):
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
