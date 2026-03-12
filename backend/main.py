"""FastAPI server for Cloudboosta Voice Agent (System B)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config

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


# TODO: Phase 3 — ADK agent routes
# TODO: Phase 6 — Twilio webhook routes
