"""Minimal Gemini Live API test — strips all complexity to isolate VAD.

No tools, no KB, no Firestore, no Supabase. Just audio in/out with a
short system instruction. Used to determine whether VAD failure is caused
by our config (tools, 42K KB, long instruction) or the model itself.

Supports model override via query param:
  /ws/test/minimal?model=gemini-2.0-flash-live-001

Exports:
    handle_minimal_test: WebSocket handler for browser audio test.
    handle_minimal_twilio: WebSocket handler for Twilio audio test.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os

import audioop
import numpy as np
import soxr
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

MINIMAL_INSTRUCTION = (
    "You are a friendly assistant. Greet the user warmly and have a brief "
    "conversation. Keep responses short (1-2 sentences). Ask how their day "
    "is going after your greeting."
)


async def handle_minimal_test(websocket: WebSocket, model_override: str = "") -> None:
    """Minimal browser WebSocket test — bare Gemini Live, no tools/KB.

    Audio format: PCM 16kHz 16-bit in, PCM 24kHz 16-bit out (same as
    voice_handler.py). Logs every server message type for debugging.
    """
    await websocket.accept()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        await websocket.send_json({"error": "GOOGLE_API_KEY not set"})
        await websocket.close(code=4000)
        return

    model_name = model_override or config.gemini_model
    is_native_audio = "native-audio" in model_name
    logger.info("MINIMAL TEST: model=%s native_audio=%s", model_name, is_native_audio)

    live_config_kwargs = dict(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=MINIMAL_INSTRUCTION)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # NO tools
    )

    if is_native_audio:
        live_config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    live_config = types.LiveConnectConfig(**live_config_kwargs)
    client = genai.Client(api_key=api_key)

    try:
        async with client.aio.live.connect(
            model=model_name, config=live_config
        ) as session:
            logger.info("MINIMAL TEST: Gemini connected")

            await websocket.send_json({"type": "ready"})

            # Trigger greeting
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="Hello")],
                ),
                turn_complete=True,
            )
            logger.info("MINIMAL TEST: greeting trigger sent")

            upstream_count = 0
            downstream_count = 0
            greeting_started = asyncio.Event()

            async def upstream():
                nonlocal upstream_count
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        upstream_count += 1
                        if not greeting_started.is_set():
                            continue
                        if upstream_count <= 5 or upstream_count % 100 == 0:
                            logger.info("MINIMAL upstream #%d: %d bytes", upstream_count, len(data))
                        await session.send_realtime_input(
                            audio=types.Blob(
                                mime_type="audio/pcm;rate=16000", data=data
                            )
                        )
                except WebSocketDisconnect:
                    logger.info("MINIMAL upstream: disconnected after %d chunks", upstream_count)
                except Exception as exc:
                    logger.info("MINIMAL upstream ended: %s", exc)

            async def downstream():
                nonlocal downstream_count
                logger.info("MINIMAL downstream: listening...")
                try:
                    async for msg in session.receive():
                        downstream_count += 1

                        # Log EVERY message type for diagnosis
                        parts_info = ""
                        if msg.server_content and msg.server_content.model_turn:
                            parts = msg.server_content.model_turn.parts or []
                            parts_info = f" parts={len(parts)}"
                            for i, p in enumerate(parts):
                                if hasattr(p, "inline_data") and p.inline_data:
                                    parts_info += f" [p{i}:audio={len(p.inline_data.data)}b]"
                                elif hasattr(p, "text") and p.text:
                                    parts_info += f" [p{i}:text={p.text[:50]}]"

                        has_input_tx = (
                            msg.server_content
                            and hasattr(msg.server_content, "input_transcription")
                            and msg.server_content.input_transcription
                            and msg.server_content.input_transcription.text
                        )
                        has_output_tx = (
                            msg.server_content
                            and hasattr(msg.server_content, "output_transcription")
                            and msg.server_content.output_transcription
                            and msg.server_content.output_transcription.text
                        )
                        turn_complete = (
                            msg.server_content
                            and hasattr(msg.server_content, "turn_complete")
                            and msg.server_content.turn_complete
                        )
                        interrupted = (
                            msg.server_content
                            and hasattr(msg.server_content, "interrupted")
                            and msg.server_content.interrupted
                        )

                        logger.info(
                            "MINIMAL downstream #%d: type=%s tool=%s sc=%s%s "
                            "turn_complete=%s interrupted=%s input_tx=%s output_tx=%s",
                            downstream_count,
                            type(msg).__name__,
                            bool(msg.tool_call),
                            bool(msg.server_content),
                            parts_info,
                            turn_complete,
                            interrupted,
                            has_input_tx,
                            has_output_tx,
                        )

                        # Transcriptions
                        if has_input_tx:
                            text = msg.server_content.input_transcription.text
                            logger.info("MINIMAL >>> USER SAID: %s", text)
                            try:
                                await websocket.send_json({
                                    "type": "transcript", "speaker": "user", "text": text
                                })
                            except WebSocketDisconnect:
                                return

                        if has_output_tx:
                            text = msg.server_content.output_transcription.text
                            logger.info("MINIMAL >>> SARAH SAID: %s", text)
                            try:
                                await websocket.send_json({
                                    "type": "transcript", "speaker": "agent", "text": text
                                })
                            except WebSocketDisconnect:
                                return

                        # Audio
                        if msg.server_content and msg.server_content.model_turn:
                            if not greeting_started.is_set():
                                greeting_started.set()
                                logger.info("MINIMAL: greeting audio started, upstream ungated")

                            for part in msg.server_content.model_turn.parts or []:
                                if (
                                    hasattr(part, "inline_data")
                                    and part.inline_data
                                    and part.inline_data.data
                                ):
                                    try:
                                        await websocket.send_bytes(part.inline_data.data)
                                    except WebSocketDisconnect:
                                        return

                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    logger.info("MINIMAL downstream ended: %s", exc)

            await asyncio.gather(upstream(), downstream(), return_exceptions=True)
            logger.info(
                "MINIMAL TEST done: upstream=%d downstream=%d",
                upstream_count, downstream_count,
            )

    except Exception as exc:
        logger.error("MINIMAL TEST failed: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"error": str(exc)})
            await websocket.close(code=4000)
        except Exception:
            pass


async def handle_minimal_twilio(websocket: WebSocket, model_override: str = "") -> None:
    """Minimal Twilio WebSocket test — bare Gemini Live over Twilio audio.

    Single bidirectional stream (no dual-stream complexity). Receives
    mulaw 8kHz from Twilio, resamples to 16kHz PCM, sends to Gemini.
    Receives 24kHz PCM from Gemini, converts to mulaw 8kHz, sends back.
    """
    await websocket.accept()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("MINIMAL TWILIO: GOOGLE_API_KEY not set")
        return

    model_name = model_override or config.gemini_model
    is_native_audio = "native-audio" in model_name
    logger.info("MINIMAL TWILIO: model=%s native_audio=%s", model_name, is_native_audio)

    # Wait for Twilio start event
    stream_sid = None
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("event") == "connected":
                logger.info("MINIMAL TWILIO: connected protocol=%s", msg.get("protocol"))
            elif msg.get("event") == "start":
                start = msg.get("start", {})
                stream_sid = start.get("streamSid")
                logger.info("MINIMAL TWILIO: started sid=%s", stream_sid)
                break
    except Exception as exc:
        logger.error("MINIMAL TWILIO: handshake failed: %s", exc)
        return

    live_config_kwargs = dict(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=MINIMAL_INSTRUCTION)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    if is_native_audio:
        live_config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    live_config = types.LiveConnectConfig(**live_config_kwargs)
    client = genai.Client(api_key=api_key)

    try:
        async with client.aio.live.connect(
            model=model_name, config=live_config
        ) as session:
            logger.info("MINIMAL TWILIO: Gemini connected")

            # Trigger greeting
            await session.send_realtime_input(text="Hello")
            logger.info("MINIMAL TWILIO: greeting sent")

            call_ended = asyncio.Event()
            upstream_count = 0
            downstream_count = 0
            greeting_started = asyncio.Event()

            async def upstream():
                nonlocal upstream_count
                try:
                    while not call_ended.is_set():
                        raw = await websocket.receive_text()
                        msg = json.loads(raw)
                        event = msg.get("event")

                        if event == "stop":
                            logger.info("MINIMAL TWILIO: stream stopped")
                            call_ended.set()
                            return

                        if event != "media":
                            continue

                        if not greeting_started.is_set():
                            continue

                        upstream_count += 1
                        payload = msg.get("media", {}).get("payload", "")
                        mulaw_bytes = base64.b64decode(payload)
                        pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
                        rms = audioop.rms(pcm_8k, 2)

                        samples_8k = np.frombuffer(pcm_8k, dtype=np.int16).astype(np.float64)
                        samples_16k = soxr.resample(samples_8k, 8000, 16000)
                        pcm_16k = samples_16k.astype(np.int16).tobytes()

                        if upstream_count <= 10 or rms > 100 or upstream_count % 200 == 0:
                            logger.info(
                                "MINIMAL TWILIO upstream #%d: %d bytes rms=%d",
                                upstream_count, len(pcm_16k), rms,
                            )

                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm_16k, mime_type="audio/pcm;rate=16000"
                            )
                        )
                except WebSocketDisconnect:
                    logger.info("MINIMAL TWILIO upstream: disconnected")
                    call_ended.set()
                except Exception as exc:
                    logger.error("MINIMAL TWILIO upstream error: %s", exc)
                    call_ended.set()

            async def downstream():
                nonlocal downstream_count
                try:
                    async for msg in session.receive():
                        if call_ended.is_set():
                            return

                        downstream_count += 1

                        # Log everything
                        has_input_tx = (
                            msg.server_content
                            and hasattr(msg.server_content, "input_transcription")
                            and msg.server_content.input_transcription
                            and msg.server_content.input_transcription.text
                        )
                        has_output_tx = (
                            msg.server_content
                            and hasattr(msg.server_content, "output_transcription")
                            and msg.server_content.output_transcription
                            and msg.server_content.output_transcription.text
                        )
                        turn_complete = (
                            msg.server_content
                            and hasattr(msg.server_content, "turn_complete")
                            and msg.server_content.turn_complete
                        )

                        if downstream_count <= 10 or downstream_count % 50 == 0 or has_input_tx or has_output_tx or turn_complete:
                            logger.info(
                                "MINIMAL TWILIO downstream #%d: turn_complete=%s input_tx=%s output_tx=%s",
                                downstream_count, turn_complete, has_input_tx, has_output_tx,
                            )

                        if has_input_tx:
                            logger.info("MINIMAL TWILIO >>> USER SAID: %s", msg.server_content.input_transcription.text)
                        if has_output_tx:
                            logger.info("MINIMAL TWILIO >>> SARAH SAID: %s", msg.server_content.output_transcription.text)

                        # Audio
                        if msg.server_content and msg.server_content.model_turn:
                            if not greeting_started.is_set():
                                greeting_started.set()
                                logger.info("MINIMAL TWILIO: greeting audio started")

                            for part in msg.server_content.model_turn.parts or []:
                                if (
                                    hasattr(part, "inline_data")
                                    and part.inline_data
                                    and part.inline_data.data
                                ):
                                    pcm_24k = part.inline_data.data
                                    pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
                                    mulaw = audioop.lin2ulaw(pcm_8k, 2)
                                    payload = base64.b64encode(mulaw).decode("ascii")
                                    try:
                                        await websocket.send_text(json.dumps({
                                            "event": "media",
                                            "streamSid": stream_sid,
                                            "media": {"payload": payload},
                                        }))
                                    except Exception:
                                        call_ended.set()
                                        return

                except WebSocketDisconnect:
                    call_ended.set()
                except Exception as exc:
                    logger.info("MINIMAL TWILIO downstream ended: %s", exc)
                    call_ended.set()

            async def heartbeat():
                silence = bytes(320)
                try:
                    while not call_ended.is_set():
                        await asyncio.sleep(5.0)
                        if call_ended.is_set():
                            return
                        if greeting_started.is_set():
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=silence, mime_type="audio/pcm;rate=16000"
                                )
                            )
                except Exception:
                    pass

            await asyncio.gather(
                upstream(), downstream(), heartbeat(),
                return_exceptions=True,
            )
            logger.info(
                "MINIMAL TWILIO done: upstream=%d downstream=%d",
                upstream_count, downstream_count,
            )

    except Exception as exc:
        logger.error("MINIMAL TWILIO failed: %s", exc, exc_info=True)
