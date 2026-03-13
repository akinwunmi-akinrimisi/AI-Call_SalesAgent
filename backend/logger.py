"""Supabase pipeline_logs writer.

Every significant action in the backend must call log_event().
This ensures full observability across the entire pipeline.
"""

import os
from datetime import datetime, timezone

import httpx

from config import config

SUPABASE_URL = config.supabase_url
SUPABASE_SERVICE_KEY = config.supabase_service_key


async def log_event(
    event_name: str,
    message: str,
    *,
    component: str = "voice_agent",
    event_type: str = "info",
    lead_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write a single event to the pipeline_logs table in Supabase."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print(f"[LOG] {event_name}: {message} (Supabase not configured)")
        return

    payload = {
        "component": component,
        "event_type": event_type,
        "event_name": event_name,
        "message": message,
        "lead_id": lead_id,
        "metadata": metadata if metadata else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/pipeline_logs",
                json=payload,
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[LOG ERROR] Failed to write pipeline_log: {e}")
