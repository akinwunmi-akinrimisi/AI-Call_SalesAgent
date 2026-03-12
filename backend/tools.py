"""ADK function tools for Sarah's voice agent and Supabase async helpers.

Provides two ADK-compatible function tools that Gemini calls during voice
conversations, plus two async helper functions for writing data to Supabase.

ADK Function Tools (bound to Agent):
    update_lead_profile: Stores qualification data in ToolContext state.
    determine_call_outcome: Validates and stores call outcome in ToolContext state.

Supabase Async Helpers (called during call cleanup):
    write_lead_profile_to_supabase: PATCH lead qualification fields.
    write_call_log_to_supabase: POST new call_log entry.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from google.adk.tools import ToolContext


# ---- Configuration (from environment, same pattern as logger.py) ----

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

VALID_OUTCOMES = ("COMMITTED", "FOLLOW_UP", "DECLINED")


# ---- ADK Function Tools ----


def update_lead_profile(
    role: str,
    experience_level: str,
    cloud_background: str,
    motivation: str,
    tool_context: "ToolContext",
) -> dict:
    """Update the lead's qualification profile in the database.

    Call this after gathering all four qualification fields from the lead
    during the conversation. This stores the data in the session state so
    it can be written to Supabase when the call ends.

    Args:
        role: The lead's current job role or title.
        experience_level: junior, mid, senior, or career-changer.
        cloud_background: Description of their cloud/DevOps experience.
        motivation: Why they want cloud training.
        tool_context: ADK ToolContext for session state access.

    Returns:
        Status dict indicating success.
    """
    tool_context.state["qualification"] = {
        "role": role,
        "experience_level": experience_level,
        "cloud_background": cloud_background,
        "motivation": motivation,
    }
    return {"status": "success", "message": "Lead profile updated"}


def determine_call_outcome(
    outcome: str,
    recommended_programme: str,
    qualification_summary: str,
    objections_raised: list[str],
    follow_up_preference: str = "",
    tool_context: "ToolContext" = None,
) -> dict:
    """Record the final outcome of the sales call.

    Call this at the very end of the conversation, after the commitment ask.
    The outcome must be one of COMMITTED, FOLLOW_UP, or DECLINED.

    Args:
        outcome: Must be one of COMMITTED, FOLLOW_UP, or DECLINED.
        recommended_programme: The programme recommended (cloud-security or sre-platform-engineering).
        qualification_summary: Brief summary of the lead's qualification.
        objections_raised: List of objections raised during the call.
        follow_up_preference: When the lead prefers follow-up (only for FOLLOW_UP outcome).
        tool_context: ADK ToolContext for session state access.

    Returns:
        Status dict indicating success or error with outcome.
    """
    if outcome not in VALID_OUTCOMES:
        return {"status": "error", "message": f"Invalid outcome: {outcome}. Must be one of {VALID_OUTCOMES}"}

    tool_context.state["call_outcome"] = {
        "outcome": outcome,
        "recommended_programme": recommended_programme,
        "qualification_summary": qualification_summary,
        "objections_raised": objections_raised,
        "follow_up_preference": follow_up_preference,
    }
    return {"status": "success", "outcome": outcome}


# ---- Supabase Async Helpers ----


async def write_lead_profile_to_supabase(lead_id: str, profile: dict) -> None:
    """Write lead qualification fields to Supabase leads table.

    Non-blocking helper -- fire-and-forget from tools, awaited during
    call cleanup. Uses PATCH to update an existing lead row.

    Args:
        lead_id: UUID of the lead to update.
        profile: Dict with qualification fields (role, experience_level,
                 cloud_background, motivation).
    """
    url = f"{SUPABASE_URL}/rest/v1/leads?id=eq.{lead_id}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Content-Profile": "sales_agent",
        "Prefer": "return=minimal",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=profile, headers=headers, timeout=10)
        resp.raise_for_status()


async def write_call_log_to_supabase(lead_id: str, call_data: dict) -> str:
    """Write a new call_log entry to Supabase and return the created ID.

    Uses POST with Prefer: return=representation to get the created row
    back, extracting the auto-generated UUID.

    Args:
        lead_id: UUID of the lead this call belongs to.
        call_data: Dict with call_log fields (lead_id, status, outcome,
                   transcript, qualification_summary, recommended_programme,
                   objections_raised, duration_seconds, follow_up_date).

    Returns:
        The UUID of the newly created call_log entry.
    """
    url = f"{SUPABASE_URL}/rest/v1/call_logs"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Content-Profile": "sales_agent",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=call_data, headers=headers, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        return result[0]["id"]
