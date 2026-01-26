"""Tests for agents API router."""

import json
from pathlib import Path

from fastapi.testclient import TestClient


class TestGetAuditEntries:
    """Tests for GET /api/projects/{project_name}/audit endpoint."""

    def test_get_audit_entries_empty(self, client_with_mocks: TestClient):
        """Test getting audit entries when none exist."""
        response = client_with_mocks.get("/api/projects/test-project/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []
        assert data["total"] == 0


class TestGetAuditStatistics:
    """Tests for GET /api/projects/{project_name}/audit/statistics endpoint."""

    def test_get_audit_statistics(self, client_with_mocks: TestClient):
        """Test getting audit statistics."""
        response = client_with_mocks.get("/api/projects/test-project/audit/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["success_rate"] == 0.0


class TestGetSessions:
    """Tests for GET /api/projects/{project_name}/sessions endpoint."""

    def test_get_sessions_empty(self, client_with_mocks: TestClient):
        """Test getting sessions when none exist."""
        response = client_with_mocks.get("/api/projects/test-project/sessions")

        assert response.status_code == 200
        data = response.json()
        assert data["sessions"] == []

    def test_get_sessions_with_sessions(
        self,
        temp_project_dir: Path,
        client_with_mocks: TestClient,
    ):
        """Test getting sessions when they exist."""
        # Create session file in temp directory
        sessions_dir = temp_project_dir / ".workflow" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        session_data = {
            "session_id": "sess1",
            "task_id": "T1",
            "agent": "claude",
            "created_at": "2026-01-26T10:00:00",
            "last_active": "2026-01-26T10:05:00",
            "iteration": 3,
            "active": True,
        }
        (sessions_dir / "sess1.json").write_text(json.dumps(session_data))

        response = client_with_mocks.get("/api/projects/test-project/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "sess1"
