"""FastAPI server for Cloudboosta Voice Agent (System B)."""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config import config
from voice_handler import handle_voice_session

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


# TODO: Phase 6 — Twilio webhook routes
