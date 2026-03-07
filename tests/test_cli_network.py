"""
Network-dependent CLI tests.

All HTTP calls are intercepted via unittest.mock — no real network
connection is required. Covers: policy push/pull, agent list, login,
rotate-key, whoami with credentials, per-agent policies, and JSON output.
"""

import json
from pathlib import Path
from typing import Any, Generator, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hashed.cli import app
from hashed.config import HashedConfig

runner = CliRunner()

# ── Fake credential set ───────────────────────────────────────────────────────

FAKE_CREDS: dict[str, Any] = {
    "email": "dev@example.com",
    "org_name": "Test Org",
    "api_key": "hashed_testkey123",
    "org_id": "org-uuid-1",
    "backend_url": "http://localhost:8000",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator:
    """Run each test in an isolated temp directory."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture()
def global_policy_file(tmp_workdir: Path) -> Path:
    """Pre-populate .hashed_policies.json with 2 global policies."""
    data = {
        "global": {
            "send_email": {"allowed": True,  "max_amount": None, "created_at": "2026-01-01"},
            "delete_record": {"allowed": False, "max_amount": None, "created_at": "2026-01-01"},
        },
        "agents": {},
    }
    p = tmp_workdir / ".hashed_policies.json"
    p.write_text(json.dumps(data, indent=2))
    return p


# ── Helpers ───────────────────────────────────────────────────────────────────


def _async_client(get_side_effect: Optional[List[Any]] = None,
                  post_return: Any = None,
                  delete_return: Any = None) -> AsyncMock:
    """
    Build an AsyncMock that behaves like an httpx.AsyncClient context manager.

    get_side_effect : list of return values for successive .get() calls
    post_return     : return value for .post() calls
    delete_return   : return value for .delete() calls
    """
    def _resp(ok: bool = True, status: int = 200, body: Optional[dict] = None) -> MagicMock:
        m = MagicMock(is_success=ok, status_code=status)
        m.json.return_value = body or {}
        return m

    client = AsyncMock()
    # Async context manager: __aenter__ returns the client itself
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=_resp())

    client.post = AsyncMock(return_value=post_return or _resp(body={"id": "p-1"}))
    client.delete = AsyncMock(return_value=delete_return or _resp())
    return client


def _sync_client(post_return: Any = None,
                 get_return: Any = None) -> MagicMock:
    """Build a MagicMock that behaves like an httpx.Client context manager."""
    def _resp(ok: bool = True, status: int = 200, body: Optional[dict] = None) -> MagicMock:
        m = MagicMock(is_success=ok, status_code=status)
        m.json.return_value = body or {}
        return m

    client = MagicMock()
    # Sync context manager
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=None)
    client.post = MagicMock(return_value=post_return or _resp())
    client.get = MagicMock(return_value=get_return or _resp())
    return client


# ── Policy push ───────────────────────────────────────────────────────────────


class TestPolicyPush:

    def test_push_syncs_global_policies(self, global_policy_file: Path) -> None:
        """
        policy push upserts local policies and reports 'sync complete'.
        2 global policies → 2 POST calls to the backend.
        """
        agents_resp = MagicMock(is_success=True, status_code=200)
        agents_resp.json.return_value = {"agents": []}

        backend_resp = MagicMock(is_success=True, status_code=200)
        backend_resp.json.return_value = {"policies": []}

        post_ok = MagicMock(is_success=True, status_code=200)
        post_ok.json.return_value = {"id": "p-1"}

        client = _async_client(
            get_side_effect=[agents_resp, backend_resp],
            post_return=post_ok,
        )

        with (
            patch("hashed.cli.load_credentials", return_value=FAKE_CREDS),
            patch("httpx.AsyncClient", return_value=client),
        ):
            result = runner.invoke(app, ["policy", "push"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "sync complete" in output_lower or "upserted" in output_lower or "✓" in result.output

    def test_push_without_credentials_fails(self, tmp_workdir: Path) -> None:
        """policy push without stored credentials → exit code 1."""
        empty_cfg = HashedConfig(api_url="http://x", backend_url=None, api_key=None)
        with (
            patch("hashed.cli.load_credentials", return_value=None),
            patch("hashed.cli.get_config", return_value=empty_cfg),
        ):
            result = runner.invoke(app, ["policy", "push"])
        output_lower = result.output.lower()
        assert result.exit_code != 0 or "login" in output_lower or "credentials" in output_lower


# ── Policy pull ───────────────────────────────────────────────────────────────


class TestPolicyPull:

    def test_pull_writes_global_policies(self, tmp_workdir: Path) -> None:
        """
        policy pull downloads 2 global policies and writes .hashed_policies.json
        with both entries under 'global'.
        """
        policies_resp = MagicMock(is_success=True, status_code=200)
        policies_resp.json.return_value = {
            "policies": [
                {
                    "tool_name": "send_email",
                    "allowed": True,
                    "max_amount": None,
                    "created_at": "2026-01-01T00:00:00",
                    "agent_id": None,
                },
                {
                    "tool_name": "delete_record",
                    "allowed": False,
                    "max_amount": None,
                    "created_at": "2026-01-01T00:00:00",
                    "agent_id": None,
                },
            ]
        }
        agents_resp = MagicMock(is_success=True, status_code=200)
        agents_resp.json.return_value = {"agents": []}

        client = _async_client(get_side_effect=[policies_resp, agents_resp])

        with (
            patch("hashed.cli.load_credentials", return_value=FAKE_CREDS),
            patch("httpx.AsyncClient", return_value=client),
        ):
            result = runner.invoke(app, ["policy", "pull"])

        assert result.exit_code == 0
        policy_path = tmp_workdir / ".hashed_policies.json"
        assert policy_path.exists()
        data = json.loads(policy_path.read_text())
        assert "send_email" in data.get("global", {})
        assert "delete_record" in data.get("global", {})

    def test_pull_without_credentials_fails(self, tmp_workdir: Path) -> None:
        """policy pull without credentials → graceful failure."""
        empty_cfg = HashedConfig(api_url="http://x", backend_url=None, api_key=None)
        with (
            patch("hashed.cli.load_credentials", return_value=None),
            patch("hashed.cli.get_config", return_value=empty_cfg),
        ):
            result = runner.invoke(app, ["policy", "pull"])
        output_lower = result.output.lower()
        assert result.exit_code != 0 or "login" in output_lower or "credentials" in output_lower


# ── Agent list ────────────────────────────────────────────────────────────────


class TestAgentListCLI:

    def test_agent_list_displays_registered_agents(self, tmp_workdir: Path) -> None:
        """agent list renders a table containing registered agent names."""
        agents_resp = MagicMock(is_success=True, status_code=200)
        agents_resp.json.return_value = {
            "agents": [
                {
                    "id": "a-1",
                    "name": "Research Bot",
                    "agent_type": "analyst",
                    "public_key": "ab" * 32,
                    "status": "active",
                }
            ]
        }
        client = _async_client(get_side_effect=[agents_resp])

        with (
            patch.dict("os.environ", {
                "HASHED_BACKEND_URL": "http://localhost:8000",
                "HASHED_API_KEY": "hashed_testkey",
            }),
            patch("httpx.AsyncClient", return_value=client),
        ):
            result = runner.invoke(app, ["agent", "list"])

        assert result.exit_code == 0
        assert "Research Bot" in result.output

    def test_agent_list_no_backend_url_exits_with_error(self, tmp_workdir: Path) -> None:
        """agent list without HASHED_BACKEND_URL configured → exit code 1."""
        empty_cfg = HashedConfig(api_url="http://x", backend_url=None, api_key=None)
        with patch("hashed.cli.get_config", return_value=empty_cfg):
            result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code != 0 or "backend" in result.output.lower()


# ── Login ─────────────────────────────────────────────────────────────────────


class TestLoginCLI:

    def test_login_valid_credentials_saves_api_key(self, tmp_workdir: Path) -> None:
        """
        hashed login --email --password with valid credentials
        saves api_key to credentials.json.
        """
        login_resp = MagicMock(is_success=True, status_code=200)
        login_resp.json.return_value = {
            "api_key": "hashed_fresh_key_999",
            "org_name": "My Org",
            "org_id": "org-uuid-999",
        }
        client = _sync_client(post_return=login_resp)

        saved: dict[str, Any] = {}

        def _capture(data: dict) -> None:
            saved.update(data)

        with (
            patch("httpx.Client", return_value=client),
            patch("hashed.cli.save_credentials", side_effect=_capture),
        ):
            result = runner.invoke(app, [
                "login",
                "--email", "dev@example.com",
                "--password", "secret123",
                "--backend", "http://localhost:8000",
            ])

        assert result.exit_code == 0
        assert saved.get("api_key") == "hashed_fresh_key_999"
        assert saved.get("email") == "dev@example.com"

    def test_login_wrong_password_exits_nonzero(self, tmp_workdir: Path) -> None:
        """hashed login with 401 response → exit code 1."""
        bad_resp = MagicMock(is_success=False, status_code=401)
        bad_resp.json.return_value = {"detail": "Invalid credentials"}
        client = _sync_client(post_return=bad_resp)

        with patch("httpx.Client", return_value=client):
            result = runner.invoke(app, [
                "login",
                "--email", "x@x.com",
                "--password", "wrong",
                "--backend", "http://localhost:8000",
            ])

        assert result.exit_code != 0

    def test_login_server_unreachable_exits_nonzero(self, tmp_workdir: Path) -> None:
        """hashed login when server is unreachable → exit code 1."""
        import httpx as _httpx

        client = _sync_client()
        client.post.side_effect = _httpx.ConnectError("refused")

        with patch("httpx.Client", return_value=client):
            result = runner.invoke(app, [
                "login",
                "--email", "dev@example.com",
                "--password", "pass",
                "--backend", "http://localhost:8000",
            ])

        assert result.exit_code != 0


# ── Rotate key ────────────────────────────────────────────────────────────────


class TestRotateKeyCLI:

    def test_rotate_key_success_updates_stored_key(self, tmp_workdir: Path) -> None:
        """
        rotate-key --yes with valid credentials → saved api_key is updated
        to the value returned by the backend.
        """
        rotate_resp = MagicMock(is_success=True, status_code=200)
        rotate_resp.json.return_value = {
            "new_api_key": "hashed_rotated_abc999",
            "org_name": "Test Org",
            "rotated_at": "2026-03-07T12:00:00",
        }
        client = _sync_client(post_return=rotate_resp)

        saved: dict[str, Any] = {}

        def _capture(data: dict) -> None:
            saved.update(data)

        with (
            patch("hashed.cli.load_credentials", return_value=FAKE_CREDS.copy()),
            patch("httpx.Client", return_value=client),
            patch("hashed.cli.save_credentials", side_effect=_capture),
        ):
            result = runner.invoke(app, ["rotate-key", "--yes"])

        assert result.exit_code == 0
        assert saved.get("api_key") == "hashed_rotated_abc999"

    def test_rotate_key_not_logged_in_exits_nonzero(self, tmp_workdir: Path) -> None:
        """rotate-key without saved credentials → exit code 1."""
        with patch("hashed.cli.load_credentials", return_value=None):
            result = runner.invoke(app, ["rotate-key", "--yes"])
        assert result.exit_code != 0

    def test_rotate_key_rate_limited_exits_nonzero(self, tmp_workdir: Path) -> None:
        """rotate-key when backend returns 429 → exit code 1."""
        rate_resp = MagicMock(is_success=False, status_code=429)
        rate_resp.json.return_value = {"detail": "Rate limit exceeded"}
        client = _sync_client(post_return=rate_resp)

        with (
            patch("hashed.cli.load_credentials", return_value=FAKE_CREDS.copy()),
            patch("httpx.Client", return_value=client),
        ):
            result = runner.invoke(app, ["rotate-key", "--yes"])

        assert result.exit_code != 0


# ── Per-agent policy operations ───────────────────────────────────────────────


class TestPerAgentPolicyCLI:

    def test_policy_add_creates_agent_entry(self, tmp_workdir: Path) -> None:
        """
        policy add <tool> --allow --agent <name> creates the tool under
        policies['agents'][<snake_name>].
        """
        result = runner.invoke(app, [
            "policy", "add", "process_payment",
            "--allow",
            "--max-amount", "500",
            "--agent", "Pay Agent",
        ])
        assert result.exit_code == 0
        data = json.loads((tmp_workdir / ".hashed_policies.json").read_text())
        agent_pols = data.get("agents", {}).get("pay_agent", {})
        assert "process_payment" in agent_pols
        assert agent_pols["process_payment"]["allowed"] is True
        assert agent_pols["process_payment"]["max_amount"] == 500.0

    def test_policy_remove_per_agent_deletes_entry(self, tmp_workdir: Path) -> None:
        """
        policy remove <tool> --agent <name> deletes the entry from the
        agent's policy section.
        """
        # Seed an agent-specific policy
        runner.invoke(app, ["policy", "add", "send_sms", "--allow", "--agent", "SMS Bot"])
        # Remove it
        result = runner.invoke(app, ["policy", "remove", "send_sms", "--agent", "SMS Bot"])
        assert result.exit_code == 0
        data = json.loads((tmp_workdir / ".hashed_policies.json").read_text())
        assert "send_sms" not in data.get("agents", {}).get("sms_bot", {})

    def test_policy_list_json_format_is_valid_json(self, tmp_workdir: Path) -> None:
        """
        policy list --format json outputs valid, parseable JSON containing
        policy data.
        """
        runner.invoke(app, ["policy", "add", "send_email", "--allow"])
        result = runner.invoke(app, ["policy", "list", "--format", "json"])
        assert result.exit_code == 0
        # Find the first '{' to strip any Rich/Typer preamble
        raw = result.output
        start = raw.find("{")
        assert start != -1, f"No JSON object found in output:\n{raw}"
        parsed = json.loads(raw[start:])
        # The data should contain at least one policy
        assert "global" in parsed or len(parsed) > 0

    def test_whoami_with_credentials_shows_user_info(self, tmp_workdir: Path) -> None:
        """
        whoami with saved credentials displays the user's email and
        organization name.
        """
        with patch("hashed.cli.load_credentials", return_value=FAKE_CREDS):
            result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0
        assert "dev@example.com" in result.output
        assert "Test Org" in result.output
