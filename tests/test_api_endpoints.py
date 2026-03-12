"""Integration tests for REST API endpoints (Phase 4).

Tests GET /api/leads and GET /api/call/{lead_id}/latest endpoints
using FastAPI TestClient with mocked httpx to avoid real Supabase calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _mock_api_deps(monkeypatch):
    """Patch environment variables for API tests."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "fake-service-key-for-testing")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")


@pytest.fixture
def test_client(_mock_api_deps):
    """Create a TestClient for the FastAPI app."""
    from main import app

    return TestClient(app)


class TestListLeads:
    """Tests for GET /api/leads endpoint."""

    def test_list_leads(self, test_client):
        """GET /api/leads returns JSON array of leads with correct fields."""
        mock_leads = [
            {
                "id": "1",
                "name": "Test Lead",
                "phone": "+447700900001",
                "email": "test@example.com",
                "call_outcome": None,
                "status": "new",
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_leads
        mock_response.raise_for_status = MagicMock()

        with patch("main.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            resp = test_client.get("/api/leads")

            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["id"] == "1"
            assert data[0]["name"] == "Test Lead"
            assert data[0]["phone"] == "+447700900001"
            assert data[0]["email"] == "test@example.com"
            assert data[0]["call_outcome"] is None
            assert data[0]["status"] == "new"

    def test_list_leads_error(self, test_client):
        """GET /api/leads returns 502 if Supabase is unreachable."""
        with patch("main.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            resp = test_client.get("/api/leads")

            assert resp.status_code == 502
            data = resp.json()
            assert "error" in data


class TestLatestCall:
    """Tests for GET /api/call/{lead_id}/latest endpoint."""

    def test_latest_call(self, test_client):
        """GET /api/call/{lead_id}/latest returns most recent call_log entry."""
        mock_call_log = [
            {
                "lead_id": "1",
                "outcome": "COMMITTED",
                "duration_seconds": 300,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_call_log
        mock_response.raise_for_status = MagicMock()

        with patch("main.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            resp = test_client.get("/api/call/1/latest")

            assert resp.status_code == 200
            data = resp.json()
            assert data["lead_id"] == "1"
            assert data["outcome"] == "COMMITTED"
            assert data["duration_seconds"] == 300

    def test_latest_call_not_found(self, test_client):
        """GET /api/call/{lead_id}/latest returns error when no logs exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("main.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            resp = test_client.get("/api/call/nonexistent/latest")

            assert resp.status_code == 200
            data = resp.json()
            assert data["error"] == "No call logs found"
