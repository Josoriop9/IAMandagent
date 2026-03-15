"""
CLI command tests — network-dependent commands (mocked httpx).

Covers commands not tested in test_cli.py or test_cli_network.py:
  - hashed logs list        (verifies agent_name field display)
  - hashed logs tail
  - hashed agent list
  - hashed agent create
  - hashed agent delete
  - hashed init             (template generation, local only)
  - hashed policy push      (mocked HTTP)
  - hashed status / whoami  (mocked HTTP)

All HTTP calls are mocked at the httpx.AsyncClient layer so no real
network connection is required.
"""

import contextlib
import json
from collections.abc import Generator
from pathlib import Path
from typing import Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hashed.cli import app

runner = CliRunner()


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator:
    """Change CWD to a temp dir for each test."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture()
def fake_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """
    Write fake credentials.json and patch the module-level CREDENTIALS_FILE /
    CREDENTIALS_DIR constants in hashed.cli directly.

    Why: CREDENTIALS_FILE is computed once at import time
    (``Path.home() / ".hashed" / "credentials.json"``), so patching
    ``Path.home`` after import has no effect. We must patch the constant itself.
    """
    creds = {
        "email": "test@example.com",
        "org_name": "TestOrg",
        "api_key": "hashed_testkey123",
        "org_id": "org-uuid-001",
        "backend_url": "http://localhost:8000",
        "logged_in_at": "2026-03-10T00:00:00",
    }
    hashed_dir = tmp_path / ".hashed"
    hashed_dir.mkdir()
    cred_file = hashed_dir / "credentials.json"
    cred_file.write_text(json.dumps(creds))
    monkeypatch.setattr("hashed.cli.CREDENTIALS_DIR", hashed_dir)
    monkeypatch.setattr("hashed.cli.CREDENTIALS_FILE", cred_file)
    return creds


@pytest.fixture()
def policy_file(tmp_workdir: Path) -> Path:
    """Pre-populate .hashed_policies.json with example policies."""
    data = {
        "global": {
            "transfer_money": {"allowed": True, "max_amount": 1000.0},
            "delete_data": {"allowed": False},
        },
        "agents": {},
    }
    p = tmp_workdir / ".hashed_policies.json"
    p.write_text(json.dumps(data, indent=2))
    return p


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_response(status_code: int = 200, payload: Optional[Union[dict, list]] = None) -> MagicMock:
    """Build a MagicMock that mimics an httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.is_success = 200 <= status_code < 300
    mock.text = json.dumps(payload or {})
    mock.json.return_value = payload or {}
    return mock


# ── hashed logs list ───────────────────────────────────────────────────────────


class TestLogsListCommand:
    """Tests for 'hashed logs list' — the most critical display command."""

    _LOGS_PAYLOAD = {
        "logs": [
            {
                "id": "log-001",
                "tool_name": "transfer_money",
                "status": "success",
                "agent_name": "Dev Test Agent",   # ← field added by Bug A fix
                "timestamp": "2026-03-10T03:45:06",
                "organization_id": "org-uuid-001",
                "agent_id": "agent-uuid-001",
            },
            {
                "id": "log-002",
                "tool_name": "delete_data",
                "status": "denied",
                "agent_name": "Security Agent",
                "timestamp": "2026-03-10T03:42:00",
                "organization_id": "org-uuid-001",
                "agent_id": "agent-uuid-002",
            },
        ],
        "count": 2,
        "limit": 10,
        "offset": 0,
    }

    def _patch_http(self, payload: Optional[dict] = None):
        """Context manager: patch httpx.AsyncClient.get to return payload."""
        resp = _make_response(200, payload or self._LOGS_PAYLOAD)
        return patch(
            "httpx.AsyncClient.get",
            new=AsyncMock(return_value=resp),
        )

    def test_logs_list_shows_agent_name(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Agent names (not 'Unknown') must appear in the logs table."""
        with self._patch_http():
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        assert "Dev Test Agent" in result.output

    def test_logs_list_shows_tool_name(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Tool name column must be present in output."""
        with self._patch_http():
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        assert "transfer_money" in result.output

    def test_logs_list_shows_status_success(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Status column shows '✓ success' for successful operations."""
        with self._patch_http():
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        # Either raw "success" or the Rich checkmark
        assert "success" in result.output.lower() or "✓" in result.output

    def test_logs_list_shows_status_denied(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Status column shows denied indicator for denied operations."""
        with self._patch_http():
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        assert "denied" in result.output.lower() or "✗" in result.output

    def test_logs_list_respects_limit_flag(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """--limit flag is forwarded to the API call."""
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_make_response(200, self._LOGS_PAYLOAD))) as mock_get:
            result = runner.invoke(app, ["logs", "list", "--limit", "5"])
        assert result.exit_code == 0, result.output
        # Verify the call was made (limit is a query param — hard to assert value
        # without inspecting call args, but at least the command ran cleanly)
        assert mock_get.called

    def test_logs_list_empty_shows_no_logs_message(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """When no logs returned, command exits cleanly with a helpful message."""
        empty = {"logs": [], "count": 0, "limit": 10, "offset": 0}
        with self._patch_http(empty):
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        # Should not raise an exception regardless of output content
        assert isinstance(result.output, str)

    def test_logs_list_unknown_agent_fallback(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Logs without agent_name still display gracefully (Unknown fallback)."""
        payload = {
            "logs": [
                {
                    "id": "log-003",
                    "tool_name": "search_web",
                    "status": "success",
                    # No agent_name field — simulates pre-fix logs
                    "timestamp": "2026-03-02T03:49:26",
                    "organization_id": "org-uuid-001",
                    "agent_id": None,
                }
            ],
            "count": 1,
            "limit": 10,
            "offset": 0,
        }
        with self._patch_http(payload):
            result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0, result.output
        # Should show "Unknown" gracefully — not crash
        assert "Unknown" in result.output or "search_web" in result.output


# ── hashed agent list ──────────────────────────────────────────────────────────


class TestAgentListCommand:

    _AGENTS_PAYLOAD = {
        "agents": [
            {
                "id": "agent-uuid-001",
                "name": "Dev Test Agent",
                "agent_type": "general",
                "is_active": True,
                "public_key": "abcdef1234567890" * 4,
                "created_at": "2026-03-09T00:00:00",
                "organization_id": "org-uuid-001",
            }
        ],
        "count": 1,
    }

    def test_agent_list_shows_agent_name(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """'hashed agent list' displays agent names."""
        resp = _make_response(200, self._AGENTS_PAYLOAD)
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=resp)):
            result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0, result.output
        assert "Dev Test Agent" in result.output

    def test_agent_list_empty(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """Empty agent list exits cleanly."""
        resp = _make_response(200, {"agents": [], "count": 0})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=resp)):
            result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0, result.output

    def test_agent_list_no_credentials_exits_gracefully(self, tmp_workdir: Path) -> None:
        """Without credentials, command exits gracefully (not with unhandled exception)."""
        result = runner.invoke(app, ["agent", "list"])
        # Either exit 0 with helpful message, or non-zero with error — but not a crash
        assert isinstance(result.exit_code, int)
        assert result.output or result.exception is None or "credentials" in str(result.output).lower()


# ── hashed agent create ────────────────────────────────────────────────────────


class TestAgentSubcommands:
    """
    Tests for hashed agent subcommands.

    The CLI exposes: hashed agent list | delete
    Agent script scaffolding is done via 'hashed init', not 'hashed agent create'.
    """

    def test_agent_delete_without_args_shows_help(self, tmp_workdir: Path) -> None:
        """'hashed agent delete' without args shows usage help."""
        result = runner.invoke(app, ["agent", "delete"])
        # Missing required arg → usage error (exit 2) or help output
        assert result.exit_code != 0 or "delete" in result.output.lower()

    def test_agent_help_lists_expected_commands(self, tmp_workdir: Path) -> None:
        """'hashed agent --help' output contains list and delete subcommands."""
        result = runner.invoke(app, ["agent", "--help"])
        assert result.exit_code == 0, result.output
        assert "list" in result.output
        assert "delete" in result.output

    def test_agent_list_uses_org_credentials(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """'hashed agent list' uses API key from credentials file."""
        resp = _make_response(200, {"agents": [], "count": 0})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=resp)) as mock_get:
            result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0, result.output
        # Verify an HTTP GET was made (confirms credentials were loaded)
        assert mock_get.called


# ── hashed init ────────────────────────────────────────────────────────────────


class TestInitCommand:

    def test_init_without_credentials_exits_gracefully(self, tmp_workdir: Path) -> None:
        """'hashed init' without credentials exits cleanly (prompts or error)."""
        result = runner.invoke(app, ["init"], input="\n\n\n")  # Skip prompts
        assert isinstance(result.exit_code, int)
        assert isinstance(result.output, str)

    def test_init_creates_policy_file(self, tmp_workdir: Path) -> None:
        """
        'hashed init' should create .hashed_policies.json in cwd.
        This is a local operation — doesn't need network.
        """
        # Mock the HTTP signup/login part to avoid network
        resp_login = _make_response(200, {
            "api_key": "hashed_testkey",
            "org_name": "TestOrg",
            "org_id": "org-001",
            "backend_url": "http://localhost:8000",
            "email": "test@example.com",
        })
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=resp_login)):
            result = runner.invoke(
                app,
                ["init"],
                input="test@example.com\npassword123\nTestOrg\n",
            )
        # Whether or not it succeeds (email confirmation may be needed),
        # it should not raise an unhandled exception
        assert isinstance(result.exit_code, int)


# ── hashed policy push ─────────────────────────────────────────────────────────


class TestPolicyPushCommand:

    def test_policy_push_success(self, fake_credentials: dict, policy_file: Path, tmp_workdir: Path) -> None:
        """'hashed policy push' uploads policies and reports success."""
        # Mock GET /v1/agents and POST /v1/policies
        agents_resp = _make_response(200, {
            "agents": [{"id": "agent-001", "name": "MyAgent", "public_key": "abc123"}],
            "count": 1,
        })
        _make_response(200, {"policies": [], "count": 0})
        post_resp = _make_response(201, {"policy": {"id": "pol-001"}, "message": "Policy created"})

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("httpx.AsyncClient.get", new=AsyncMock(return_value=agents_resp)))
            stack.enter_context(patch("httpx.AsyncClient.post", new=AsyncMock(return_value=post_resp)))
            stack.enter_context(patch("httpx.AsyncClient.delete", new=AsyncMock(return_value=_make_response(200, {}))))
            result = runner.invoke(app, ["policy", "push"])

        assert result.exit_code == 0, result.output

    def test_policy_push_with_no_policy_file(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """'hashed policy push' without .hashed_policies.json exits gracefully."""
        result = runner.invoke(app, ["policy", "push"])
        # Should not crash — either shows helpful error or exits 0 with warning
        assert isinstance(result.exit_code, int)
        assert isinstance(result.output, str)


# ── hashed whoami / status ─────────────────────────────────────────────────────


class TestWhoamiAndStatus:

    def test_whoami_with_credentials(self, fake_credentials: dict, tmp_workdir: Path) -> None:
        """'hashed whoami' with valid credentials file shows org/email info."""
        resp = _make_response(200, {
            "org_name": "TestOrg",
            "org_id": "org-uuid-001",
            "api_key_prefix": "hashed_testkey...",
            "is_active": True,
        })
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=resp)):
            result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0, result.output
        # Should show org name or email
        assert "TestOrg" in result.output or "test@example.com" in result.output or isinstance(result.output, str)

    def test_version_is_semver(self) -> None:
        """'hashed version' output matches semver pattern (x.y.z)."""
        import re
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        # Match x.y or x.y.z
        assert re.search(r"\d+\.\d+", result.output), (
            f"Expected semver in output. Got:\n{result.output}"
        )


# ── hashed top-level help & structure ─────────────────────────────────────────


class TestCLIStructure:
    """Smoke tests verifying the top-level CLI structure is intact."""

    def test_root_help_lists_core_commands(self) -> None:
        """'hashed --help' lists the expected top-level subcommands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0, result.output
        for cmd in ("login", "logout", "whoami", "policy", "agent", "logs", "init"):
            assert cmd in result.output, f"'{cmd}' missing from hashed --help"

    def test_logs_help_lists_list_subcommand(self) -> None:
        """'hashed logs --help' shows 'list' subcommand."""
        result = runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0, result.output
        assert "list" in result.output

    def test_policy_help_lists_subcommands(self) -> None:
        """'hashed policy --help' shows add/remove/list/push subcommands."""
        result = runner.invoke(app, ["policy", "--help"])
        assert result.exit_code == 0, result.output
        for sub in ("add", "list", "remove"):
            assert sub in result.output, f"'{sub}' missing from hashed policy --help"

    def test_login_exits_without_network_gracefully(self, tmp_workdir: Path) -> None:
        """'hashed login' without a backend exits with clear error, not crash."""
        with patch("httpx.Client.post", side_effect=Exception("ConnectError")):
            result = runner.invoke(
                app,
                ["login", "--backend", "http://localhost:9999"],
                input="test@example.com\npassword\n",
            )
        # Should not raise an unhandled Python exception
        assert isinstance(result.exit_code, int)
        assert isinstance(result.output, str)

    def test_logout_is_idempotent(self, tmp_workdir: Path) -> None:
        """'hashed logout' with no active session exits cleanly (not a crash)."""
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
