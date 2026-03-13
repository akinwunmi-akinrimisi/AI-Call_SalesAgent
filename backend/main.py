"""FastAPI server for Cloudboosta Voice Agent (System B)."""

import logging
import sys
from pathlib import Path

# Configure root logger so all module loggers (twilio_handler, voice_handler, etc.)
# write to stderr which Cloud Run captures and displays.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)

import httpx
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from config import config
from voice_handler import handle_voice_session
from minimal_test import handle_minimal_test, handle_minimal_twilio, handle_manual_vad_twilio
import twilio_handler
from conversation_relay_handler import (
    handle_conversation_relay,
    generate_conversation_relay_twiml,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cloudboosta Voice Agent",
    description="AI sales call agent powered by Gemini Live API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    missing = config.validate()
    return {
        "status": "ok" if not missing else "degraded",
        "service": "cloudboosta-voice-agent",
        "missing_config": missing,
    }


@app.websocket("/ws/voice/{lead_id}")
async def voice_call(websocket: WebSocket, lead_id: str):
    """WebSocket endpoint for browser voice sessions with Sarah."""
    await handle_voice_session(websocket, lead_id)


@app.get("/api/leads")
async def list_leads():
    """Return list of leads from Supabase for the browser UI."""
    url = (
        f"{config.supabase_url}/rest/v1/leads"
        "?select=id,name,phone,email,call_outcome,status&order=name"
    )
    headers = {
        "apikey": config.supabase_service_key,
        "Authorization": f"Bearer {config.supabase_service_key}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch leads: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch leads: {exc}"},
        )


@app.get("/api/call/{lead_id}/latest")
async def get_latest_call(lead_id: str):
    """Return the most recent call log for a lead."""
    url = (
        f"{config.supabase_url}/rest/v1/call_logs"
        f"?lead_id=eq.{lead_id}&order=created_at.desc&limit=1"
    )
    headers = {
        "apikey": config.supabase_service_key,
        "Authorization": f"Bearer {config.supabase_service_key}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data:
                return data[0]
            return {"error": "No call logs found"}
    except Exception as exc:
        logger.error("Failed to fetch call log for %s: %s", lead_id, exc)
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch call log: {exc}"},
        )


# ---- Debug Endpoints (temporary) ----


@app.get("/debug/audio")
async def debug_audio():
    """Serve the debug audio file captured during last call."""
    debug_path = Path("/tmp/debug_inbound.raw")
    if debug_path.exists():
        return FileResponse(
            str(debug_path),
            media_type="application/octet-stream",
            filename="debug_inbound.raw",
        )
    return JSONResponse(status_code=404, content={"error": "No debug audio file"})


# ---- Minimal Test Endpoints (VAD debugging) ----


@app.websocket("/ws/test/minimal")
async def test_minimal(websocket: WebSocket):
    """Minimal browser test — bare Gemini Live, no tools/KB.
    Query params: ?model=gemini-2.0-flash-live-001 to override model.
    """
    model = websocket.query_params.get("model", "")
    await handle_minimal_test(websocket, model_override=model)


@app.websocket("/ws/test/minimal-twilio")
async def test_minimal_twilio(websocket: WebSocket):
    """Minimal Twilio test — bare Gemini Live over Twilio audio."""
    model = websocket.query_params.get("model", "")
    await handle_minimal_twilio(websocket, model_override=model)


@app.api_route("/twilio/test-minimal", methods=["GET", "POST"])
async def twilio_test_minimal_voice(request: Request):
    """TwiML for minimal Twilio test — single bidirectional stream."""
    base_url = str(request.base_url).rstrip("/").replace("http://", "https://")
    ws_url = base_url.replace("https://", "wss://")
    model = request.query_params.get("model", "")
    model_param = f"?model={model}" if model else ""

    response = twilio_handler.VoiceResponse()
    connect = twilio_handler.Connect()
    stream = twilio_handler.Stream(url=f"{ws_url}/ws/test/minimal-twilio{model_param}")
    connect.append(stream)
    response.append(connect)

    twiml = str(response)
    logger.info("Minimal test TwiML: %s", twiml)
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/test/manual-vad")
async def test_manual_vad(websocket: WebSocket):
    """Manual VAD Twilio test — bypasses Gemini's broken speech detection."""
    model = websocket.query_params.get("model", "")
    await handle_manual_vad_twilio(websocket, model_override=model)


@app.api_route("/twilio/test-manual-vad", methods=["GET", "POST"])
async def twilio_test_manual_vad_voice(request: Request):
    """TwiML for manual VAD test — uses send_client_content instead of VAD."""
    base_url = str(request.base_url).rstrip("/").replace("http://", "https://")
    ws_url = base_url.replace("https://", "wss://")

    response = twilio_handler.VoiceResponse()
    connect = twilio_handler.Connect()
    stream = twilio_handler.Stream(url=f"{ws_url}/ws/test/manual-vad")
    connect.append(stream)
    response.append(connect)

    twiml = str(response)
    logger.info("Manual VAD TwiML: %s", twiml)
    return Response(content=twiml, media_type="application/xml")


# ---- Twilio Integration ----


@app.post("/api/call/initiate")
async def initiate_call(request: Request):
    """Trigger an outbound Twilio call to a lead."""
    body = await request.json()
    lead_id = body.get("lead_id")
    phone = body.get("phone")

    if not lead_id or not phone:
        return JSONResponse(
            status_code=400,
            content={"error": "lead_id and phone are required"},
        )

    if not config.twilio_account_sid or not config.twilio_auth_token:
        return JSONResponse(
            status_code=503,
            content={"error": "Twilio not configured"},
        )

    base_url = str(request.base_url).rstrip("/")
    # Cloud Run terminates TLS; force HTTPS for Twilio callbacks
    base_url = base_url.replace("http://", "https://")

    try:
        result = await twilio_handler.initiate_call(lead_id, phone, base_url)
        return result
    except Exception as exc:
        logger.error("Failed to initiate call for %s: %s", lead_id, exc)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to initiate call: {exc}"},
        )


@app.api_route("/twilio/voice", methods=["GET", "POST"])
async def twilio_voice(request: Request):
    """TwiML webhook — returns Media Streams connection instructions."""
    lead_id = request.query_params.get("lead_id", "")
    base_url = str(request.base_url).rstrip("/")
    base_url = base_url.replace("http://", "https://")
    twiml = twilio_handler.generate_twiml(lead_id, base_url)
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/twilio/inbound")
async def twilio_inbound_monitor(websocket: WebSocket):
    """One-way inbound audio monitor — receives real caller audio."""
    await twilio_handler.handle_inbound_monitor(websocket)


@app.websocket("/ws/twilio/stream")
async def twilio_stream(websocket: WebSocket):
    """Twilio Media Streams WebSocket — bridges phone audio with Gemini."""
    await twilio_handler.handle_twilio_stream(websocket)


@app.websocket("/ws/twilio/diagnostic")
async def twilio_diagnostic_stream(websocket: WebSocket):
    """One-way diagnostic stream to test if Twilio sends real audio."""
    await twilio_handler.handle_diagnostic_stream(websocket)


@app.api_route("/twilio/diagnostic", methods=["GET", "POST"])
async def twilio_diagnostic_voice(request: Request):
    """Diagnostic TwiML — accepts ?mode=oneway|bidir_silent|bidir_hybrid."""
    base_url = str(request.base_url).rstrip("/")
    base_url = base_url.replace("http://", "https://")
    mode = request.query_params.get("mode", "oneway")
    twiml = twilio_handler.generate_diagnostic_twiml(base_url, mode=mode)
    logger.info("Diagnostic TwiML mode=%s: %s", mode, twiml)
    return Response(content=twiml, media_type="application/xml")


@app.api_route("/twilio/diagnostic-done", methods=["GET", "POST"])
async def twilio_diagnostic_done(request: Request):
    """Gather callback for diagnostic — just hang up."""
    response = twilio_handler.VoiceResponse()
    response.say("Diagnostic complete. Goodbye.", voice="Polly.Amy")
    response.hangup()
    return Response(content=str(response), media_type="application/xml")


@app.api_route("/twilio/recording", methods=["GET", "POST"])
async def twilio_recording(request: Request):
    """Twilio recording status callback — stores recording URL."""
    form = await request.form()
    lead_id = request.query_params.get("lead_id", "")
    recording_url = form.get("RecordingUrl", "")
    recording_sid = form.get("RecordingSid", "")

    if recording_url and lead_id:
        # Update the latest call_log with the recording URL
        url = (
            f"{config.supabase_url}/rest/v1/call_logs"
            f"?lead_id=eq.{lead_id}&order=created_at.desc&limit=1"
        )
        headers = {
            "apikey": config.supabase_service_key,
            "Authorization": f"Bearer {config.supabase_service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Get the latest call log
                resp = await client.get(
                    url,
                    headers={
                        "apikey": config.supabase_service_key,
                        "Authorization": f"Bearer {config.supabase_service_key}",
                        "Accept": "application/json",
                    },
                    timeout=10,
                )
                data = resp.json()
                if data:
                    call_log_id = data[0]["id"]
                    patch_url = (
                        f"{config.supabase_url}/rest/v1/call_logs"
                        f"?id=eq.{call_log_id}"
                    )
                    await client.patch(
                        patch_url,
                        json={"recording_url": f"{recording_url}.mp3"},
                        headers=headers,
                        timeout=10,
                    )
                    logger.info(
                        "Recording URL saved for lead %s: %s",
                        lead_id, recording_url,
                    )
        except Exception as exc:
            logger.error("Failed to save recording URL: %s", exc)

    return {"status": "ok"}


@app.api_route("/twilio/status", methods=["GET", "POST"])
async def twilio_status(request: Request):
    """Twilio call status callback — logs call completion/failure."""
    form = await request.form()
    lead_id = request.query_params.get("lead_id", "")
    call_status = form.get("CallStatus", "")
    call_duration = form.get("CallDuration", "0")
    call_sid = form.get("CallSid", "")

    from logger import log_event as _log

    await _log(
        "twilio_status",
        f"Twilio call {call_sid} status: {call_status} (duration={call_duration}s)",
        lead_id=lead_id if lead_id else None,
        metadata={
            "call_sid": call_sid,
            "call_status": call_status,
            "call_duration": call_duration,
        },
    )

    return {"status": "ok"}


# ---- ConversationRelay Integration ----


@app.api_route("/twilio/conversation-relay", methods=["GET", "POST"])
async def twilio_conversation_relay_voice(request: Request):
    """TwiML webhook — returns ConversationRelay connection instructions.

    Point Twilio webhook here for ConversationRelay-based calls.
    Twilio handles STT/TTS; we bridge text to Gemini Live API.
    """
    lead_id = request.query_params.get("lead_id", "")
    base_url = str(request.base_url).rstrip("/")
    base_url = base_url.replace("http://", "https://")
    twiml = generate_conversation_relay_twiml(lead_id, base_url)
    logger.info("ConversationRelay TwiML: %s", twiml)
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/conversation-relay")
async def conversation_relay_ws(websocket: WebSocket):
    """ConversationRelay WebSocket — bridges Twilio STT/TTS with Gemini Live."""
    await handle_conversation_relay(websocket)


# --- Serve frontend static files (production) ---
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    _assets_dir = _static_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: serve index.html for all non-API/WS routes."""
        file_path = (_static_dir / full_path).resolve()
        static_root = _static_dir.resolve()
        if file_path.is_relative_to(static_root) and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_static_dir / "index.html"))
