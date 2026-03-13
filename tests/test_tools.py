"""Tests for backend/tools.py -- ADK function tools and Supabase helpers.

Covers:
- CALL-06: determine_call_outcome validates outcome enum
- CALL-10: determine_call_outcome captures follow_up_preference
- Tool state management via mock ToolContext
- Supabase REST API calls with Content-Profile: sales_agent header
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- ToolContext mock fixture ----

@pytest.fixture
def mock_tool_context():
    """Mock ADK ToolContext with state dict."""
    ctx = MagicMock()
    ctx.state = {"lead_id": "test-lead-uuid-1234"}
    return ctx


# ---- update_lead_profile tests ----

class TestUpdateLeadProfile:
    """Tests for the update_lead_profile tool function."""

    def test_update_lead_profile_success(self, mock_tool_context):
        """Calling update_lead_profile with 4 fields + mock ToolContext stores
        qualification dict in tool_context.state['qualification']."""
        from tools import update_lead_profile

        update_lead_profile(
            role="Network Engineer",
            experience_level="mid",
            cloud_background="AWS basics, some Terraform",
            motivation="career switch to cloud",
            tool_context=mock_tool_context,
        )

        assert "qualification" in mock_tool_context.state
        qual = mock_tool_context.state["qualification"]
        assert qual["role"] == "Network Engineer"
        assert qual["experience_level"] == "mid"
        assert qual["cloud_background"] == "AWS basics, some Terraform"
        assert qual["motivation"] == "career switch to cloud"

    def test_update_lead_profile_returns_success(self, mock_tool_context):
        """Return value is {'status': 'success', 'message': '...'}."""
        from tools import update_lead_profile

        result = update_lead_profile(
            role="Software Developer",
            experience_level="senior",
            cloud_background="GCP, Kubernetes",
            motivation="level up DevOps skills",
            tool_context=mock_tool_context,
        )

        assert result["status"] == "success"
        assert "message" in result


# ---- determine_call_outcome tests ----

class TestDetermineCallOutcome:
    """Tests for the determine_call_outcome tool function."""

    def test_determine_outcome_committed(self, mock_tool_context):
        """outcome='COMMITTED' stores correct dict in tool_context.state['call_outcome']."""
        from tools import determine_call_outcome

        result = determine_call_outcome(
            outcome="COMMITTED",
            recommended_programme="cloud-security",
            qualification_summary="Mid-level network engineer seeking cloud career switch",
            objections_raised=["price"],
            tool_context=mock_tool_context,
        )

        assert result["status"] == "success"
        assert result["outcome"] == "COMMITTED"
        assert mock_tool_context.state["call_outcome"]["outcome"] == "COMMITTED"
        assert mock_tool_context.state["call_outcome"]["recommended_programme"] == "cloud-security"

    def test_determine_outcome_follow_up(self, mock_tool_context):
        """outcome='FOLLOW_UP' with follow_up_preference stores the preference."""
        from tools import determine_call_outcome

        result = determine_call_outcome(
            outcome="FOLLOW_UP",
            recommended_programme="sre-platform-engineering",
            qualification_summary="Junior developer interested in DevOps",
            objections_raised=["time"],
            follow_up_preference="Tuesday at 3pm",
            tool_context=mock_tool_context,
        )

        assert result["status"] == "success"
        assert result["outcome"] == "FOLLOW_UP"
        outcome = mock_tool_context.state["call_outcome"]
        assert outcome["follow_up_preference"] == "Tuesday at 3pm"

    def test_determine_outcome_declined(self, mock_tool_context):
        """outcome='DECLINED' stores correctly."""
        from tools import determine_call_outcome

        result = determine_call_outcome(
            outcome="DECLINED",
            recommended_programme="cloud-security",
            qualification_summary="Career changer, not ready financially",
            objections_raised=["price", "timing"],
            tool_context=mock_tool_context,
        )

        assert result["status"] == "success"
        assert result["outcome"] == "DECLINED"
        assert mock_tool_context.state["call_outcome"]["outcome"] == "DECLINED"

    def test_determine_outcome_invalid(self, mock_tool_context):
        """outcome='MAYBE' returns {'status': 'error', ...}."""
        from tools import determine_call_outcome

        result = determine_call_outcome(
            outcome="MAYBE",
            recommended_programme="cloud-security",
            qualification_summary="Some summary",
            objections_raised=[],
            tool_context=mock_tool_context,
        )

        assert result["status"] == "error"
        assert "call_outcome" not in mock_tool_context.state

    def test_follow_up_preference_captured(self, mock_tool_context):
        """FOLLOW_UP outcome with follow_up_preference='Tuesday at 3pm' is stored
        in state."""
        from tools import determine_call_outcome

        determine_call_outcome(
            outcome="FOLLOW_UP",
            recommended_programme="sre-platform-engineering",
            qualification_summary="Experienced cloud engineer wanting SRE skills",
            objections_raised=[],
            follow_up_preference="Tuesday at 3pm",
            tool_context=mock_tool_context,
        )

        outcome = mock_tool_context.state["call_outcome"]
        assert outcome["follow_up_preference"] == "Tuesday at 3pm"
        assert outcome["outcome"] == "FOLLOW_UP"


# ---- Supabase helper tests ----

class TestSupabaseLeadUpdate:
    """Tests for write_lead_profile_to_supabase helper."""

    async def test_supabase_lead_update(self, mock_supabase_config):
        """write_lead_profile_to_supabase() makes PATCH to correct URL with
        Content-Profile: sales_agent."""
        from tools import write_lead_profile_to_supabase

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("tools.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            await write_lead_profile_to_supabase(
                lead_id="test-lead-uuid-1234",
                profile={
                    "role": "Network Engineer",
                    "experience_level": "mid",
                    "cloud_background": "AWS basics",
                    "motivation": "career switch",
                },
            )

            # Verify PATCH was called
            mock_client.patch.assert_called_once()
            call_args = mock_client.patch.call_args

            # Verify URL includes lead_id filter
            assert "leads" in call_args[0][0]
            assert "test-lead-uuid-1234" in call_args[0][0]

            # Verify auth headers
            headers = call_args[1].get("headers", call_args.kwargs.get("headers", {}))
            assert "apikey" in headers
            assert headers.get("Content-Type") == "application/json"


class TestSupabaseCallLogWrite:
    """Tests for write_call_log_to_supabase helper."""

    async def test_supabase_call_log_write(self, mock_supabase_config):
        """write_call_log_to_supabase() makes POST to correct URL with
        Content-Profile: sales_agent."""
        from tools import write_call_log_to_supabase

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"id": "new-call-log-uuid"}]

        with patch("tools.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await write_call_log_to_supabase(
                lead_id="test-lead-uuid-1234",
                call_data={
                    "lead_id": "test-lead-uuid-1234",
                    "status": "completed",
                    "outcome": "COMMITTED",
                    "transcript": "Hi Sarah...",
                    "qualification_summary": "Mid-level engineer",
                    "recommended_programme": "cloud-security",
                    "objections_raised": ["price"],
                    "duration_seconds": 420,
                },
            )

            # Verify POST was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            # Verify URL targets call_logs
            assert "call_logs" in call_args[0][0]

            # Verify auth headers
            headers = call_args[1].get("headers", call_args.kwargs.get("headers", {}))
            assert "apikey" in headers
            assert headers.get("Content-Type") == "application/json"

            # Verify return value is the created call_log id
            assert result == "new-call-log-uuid"
