"""
Tests for HashedCore with a mocked backend HTTP client.

Covers the lines in core.py that require a backend_url to be configured:
  - initialize() with HTTP client creation, _register_agent(), policy sync
  - shutdown() with running http_client and sync_task
  - _register_agent() — 409 existing / 201 new / error
  - sync_policies_from_backend() — success with policies / failure
  - _push_local_json_policies() — with .hashed_policies.json on disk
  - @guard() decorator with backend validation — allow / deny / fail_closed
"""

import json
import os
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hashed.config import HashedConfig
from hashed.core import HashedCore
from hashed.guard import PermissionError

# ── Helpers ───────────────────────────────────────────────────────────────────


def _backend_config(
    backend_url: str = "http://mock-backend.test",
    api_key: str = "test_key",
    fail_closed: bool = False,
    enable_auto_sync: bool = False,   # disable background task in most tests
) -> HashedConfig:
    """HashedConfig pointing at a fake backend. Clears real env vars."""
    for var in ("HASHED_BACKEND_URL", "HASHED_API_KEY"):
        os.environ.pop(var, None)
    return HashedConfig(
        backend_url=backend_url,
        api_key=api_key,
        fail_closed=fail_closed,
        enable_auto_sync=enable_auto_sync,
    )


def _mock_http_client(
    register_status: int = 201,
    register_body: Optional[dict] = None,
    sync_body: Optional[dict] = None,
    guard_body: Optional[dict] = None,
    agents_body: Optional[dict] = None,
) -> AsyncMock:
    """
    Build an AsyncMock httpx.AsyncClient with configurable response fixtures.

    POST /register  → register_status / register_body
    GET  /v1/policies/sync → sync_body
    POST /guard     → guard_body
    POST /log       → 200 ok
    GET  /v1/agents → agents_body
    """
    def _resp(status: int, body: dict) -> MagicMock:
        r = MagicMock()
        r.status_code = status
        r.is_success = 200 <= status < 300
        r.json.return_value = body
        r.text = json.dumps(body)
        return r

    client = AsyncMock()
    client.aclose = AsyncMock()

    # POST calls: /register, /guard, /log, /v1/policies
    reg_resp = _resp(register_status, register_body or {"id": "agent-1", "name": "Test"})
    log_resp = _resp(200, {"ok": True})
    guard_resp = _resp(200, guard_body or {"allowed": True})
    pol_resp  = _resp(200, {"id": "p-1"})

    # Side-effect by URL substring is tricky; use a simple counter approach
    post_side_effects = {
        "/register": reg_resp,
        "/guard": guard_resp,
        "/log": log_resp,
        "/v1/policies": pol_resp,
    }

    async def _post(url, **kwargs):
        for key, resp in post_side_effects.items():
            if key in str(url):
                return resp
        return log_resp   # default

    client.post = AsyncMock(side_effect=_post)

    # GET calls
    sync_resp   = _resp(200, sync_body   or {"policies": {}, "synced_at": "2026-01-01"})
    agents_resp = _resp(200, agents_body or {"agents": []})

    async def _get(url, **kwargs):
        if "/policies/sync" in str(url):
            return sync_resp
        return agents_resp

    client.get = AsyncMock(side_effect=_get)

    return client


# ── initialize() ──────────────────────────────────────────────────────────────


class TestInitializeWithBackend:
    """HashedCore.initialize() when backend_url is configured."""

    @pytest.mark.asyncio
    async def test_initialize_sets_initialized_true(self):
        """initialize() with backend should set _initialized=True."""
        cfg = _backend_config()
        core = HashedCore(config=cfg, agent_name="Test Bot")
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            assert core._initialized is True
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_creates_http_client(self):
        """initialize() should populate core._http_client."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            assert core._http_client is not None
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_twice_is_noop(self):
        """Calling initialize() a second time should be a no-op."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            await core.initialize()   # second call — should not raise
            assert core._initialized is True
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_syncs_policies_from_backend(self):
        """initialize() should call sync_policies_from_backend() and load returned policies."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client(
            sync_body={
                "policies": {"pay": {"allowed": True, "max_amount": 500.0}},
                "synced_at": "2026-01-01",
            }
        )

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            assert "pay" in core.policy_engine._policies
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_with_auto_sync_starts_background_task(self):
        """enable_auto_sync=True should start the background sync task."""
        cfg = _backend_config(enable_auto_sync=True)
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            assert core._sync_task is not None
            await core.shutdown()


# ── shutdown() ────────────────────────────────────────────────────────────────


class TestShutdownWithBackend:
    """HashedCore.shutdown() with a live http_client and sync_task."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_http_client(self):
        """shutdown() should call aclose() on the HTTP client."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            await core.shutdown()

        mock_http.aclose.assert_awaited()

    @pytest.mark.asyncio
    async def test_shutdown_sets_initialized_false(self):
        """shutdown() should reset _initialized to False."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            await core.shutdown()

        assert core._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_background_sync_task(self):
        """shutdown() should cancel the background sync task when enabled."""
        cfg = _backend_config(enable_auto_sync=True)
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            task = core._sync_task
            assert task is not None
            await core.shutdown()

        assert task.cancelled() or task.done()


# ── _register_agent() ─────────────────────────────────────────────────────────


class TestRegisterAgent:
    """Tests for the _register_agent() internal method."""

    @pytest.mark.asyncio
    async def test_register_new_agent_returns_true(self):
        """201 response means new agent — method returns True."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client(register_status=201)

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            # After initialization, _agent_registered should be True
            assert core._agent_registered is True
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_register_existing_agent_returns_false(self):
        """409 response means agent already exists — initialize continues cleanly."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client(register_status=409)

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()
            # Should still complete initialization
            assert core._initialized is True
            await core.shutdown()

    @pytest.mark.asyncio
    async def test_register_failure_does_not_crash_initialize(self):
        """Registration errors are caught — initialize() still completes."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)

        # Make register return a 500 error
        mock_http = _mock_http_client(register_status=500)

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http):
            await core.initialize()   # must not raise
            assert core._initialized is True
            await core.shutdown()


# ── sync_policies_from_backend() ─────────────────────────────────────────────


class TestSyncPoliciesFromBackend:
    """Tests for sync_policies_from_backend() called directly."""

    @pytest.mark.asyncio
    async def test_sync_loads_policies_into_engine(self):
        """sync_policies_from_backend() populates the PolicyEngine."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()
        core._http_client = mock_http   # inject directly (no initialize)

        # Override GET to return specific policies
        sync_resp = MagicMock()
        sync_resp.is_success = True
        sync_resp.status_code = 200
        sync_resp.json.return_value = {
            "policies": {
                "wire_transfer": {"allowed": True, "max_amount": 1000.0},
                "delete_user":   {"allowed": False, "max_amount": None},
            },
            "synced_at": "2026-03-01T00:00:00",
        }
        mock_http.get = AsyncMock(return_value=sync_resp)

        await core.sync_policies_from_backend()

        assert "wire_transfer" in core.policy_engine._policies
        assert core.policy_engine._policies["wire_transfer"].max_amount == 1000.0
        assert core.policy_engine._policies["delete_user"].allowed is False

    @pytest.mark.asyncio
    async def test_sync_raises_on_http_failure(self):
        """sync_policies_from_backend() raises if the HTTP response is non-success."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = AsyncMock()
        core._http_client = mock_http

        fail_resp = MagicMock()
        fail_resp.is_success = False
        fail_resp.status_code = 502
        fail_resp.text = "Bad Gateway"
        mock_http.get = AsyncMock(return_value=fail_resp)

        with pytest.raises(Exception):
            await core.sync_policies_from_backend()

    @pytest.mark.asyncio
    async def test_sync_skips_when_no_http_client(self):
        """sync_policies_from_backend() is a no-op when _http_client is None."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        core._http_client = None   # no backend

        # Should not raise — just logs a warning and returns
        await core.sync_policies_from_backend()
        # PolicyEngine should be untouched (no policies added)
        assert core.policy_engine._policies == {}


# ── _push_local_json_policies() ──────────────────────────────────────────────


class TestPushLocalJsonPolicies:
    """Tests for _push_local_json_policies() with a .hashed_policies.json file."""

    @pytest.mark.asyncio
    async def test_push_global_policies_from_file(self, tmp_path: Path, monkeypatch):
        """_push_local_json_policies() pushes global policies from JSON file."""
        monkeypatch.chdir(tmp_path)

        policy_data = {
            "global": {
                "send_email": {"allowed": True, "max_amount": None},
                "delete_all": {"allowed": False, "max_amount": None},
            },
            "agents": {},
        }
        (tmp_path / ".hashed_policies.json").write_text(json.dumps(policy_data))

        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()
        core._http_client = mock_http

        pushed = await core._push_local_json_policies()

        assert pushed == 2   # 2 global policies

    @pytest.mark.asyncio
    async def test_push_returns_zero_when_no_file(self, tmp_path: Path, monkeypatch):
        """_push_local_json_policies() returns 0 if no policy file exists."""
        monkeypatch.chdir(tmp_path)   # empty dir — no .hashed_policies.json

        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client()
        core._http_client = mock_http

        pushed = await core._push_local_json_policies()

        assert pushed == 0

    @pytest.mark.asyncio
    async def test_push_returns_zero_when_no_http_client(self):
        """_push_local_json_policies() returns 0 when _http_client is None."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        core._http_client = None

        pushed = await core._push_local_json_policies()

        assert pushed == 0


# ── @guard() decorator with backend ──────────────────────────────────────────


class TestGuardWithBackend:
    """Guard decorator when _http_client is set (backend path)."""

    def _core_with_backend(self) -> tuple:
        """Return (core, mock_http) with backend connected."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client(guard_body={"allowed": True})
        core._http_client = mock_http
        core._initialized = True
        return core, mock_http

    @pytest.mark.asyncio
    async def test_backend_allows_operation(self):
        """Guard with backend returning allowed=True executes the function."""
        core, mock_http = self._core_with_backend()

        @core.guard("send_report")
        async def send_report() -> str:
            return "report sent"

        result = await send_report()
        assert result == "report sent"

    @pytest.mark.asyncio
    async def test_backend_denies_operation_returns_string(self):
        """Guard with backend returning allowed=False returns HASHED BLOCKED."""
        cfg = _backend_config()
        core = HashedCore(config=cfg)
        mock_http = _mock_http_client(guard_body={"allowed": False, "message": "not allowed"})
        core._http_client = mock_http
        core._initialized = True

        @core.guard("risky_op")
        async def risky_op() -> str:
            return "should not run"

        result = await risky_op()
        assert isinstance(result, str)
        assert "HASHED BLOCKED" in result or "not allowed" in result.lower() or "permission" in result.lower()

    @pytest.mark.asyncio
    async def test_backend_unreachable_fail_open_allows(self):
        """fail_closed=False (default): backend unreachable → operation allowed."""
        cfg = _backend_config(fail_closed=False)
        core = HashedCore(config=cfg)
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=Exception("connection refused"))
        core._http_client = mock_http
        core._initialized = True

        @core.guard("safe_op")
        async def safe_op() -> str:
            return "executed"

        result = await safe_op()
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_backend_unreachable_fail_closed_denies(self):
        """fail_closed=True: backend unreachable → PermissionError raised."""
        cfg = _backend_config(fail_closed=True)
        core = HashedCore(config=cfg)
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=Exception("connection refused"))
        core._http_client = mock_http
        core._initialized = True

        @core.guard("sensitive_op", raise_on_deny=True)
        async def sensitive_op() -> str:
            return "should not run"

        with pytest.raises(PermissionError):
            await sensitive_op()

    @pytest.mark.asyncio
    async def test_guard_logs_success_to_backend(self):
        """A successful guarded operation should POST to /log on the backend."""
        core, mock_http = self._core_with_backend()
        log_calls = []

        original_post = mock_http.post.side_effect

        async def _tracking_post(url, **kwargs):
            if "/log" in str(url):
                log_calls.append(kwargs)
            return await original_post(url, **kwargs)

        mock_http.post = AsyncMock(side_effect=_tracking_post)

        @core.guard("transfer")
        async def transfer() -> dict:
            return {"ok": True}

        await transfer()
        assert len(log_calls) >= 1
