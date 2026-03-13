"""FastAPI server for Cloudboosta Voice Agent (System B)."""

import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import config
from voice_handler import handle_voice_session

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


# TODO: Phase 7 — Twilio webhook routes

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
