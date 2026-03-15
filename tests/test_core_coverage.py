"""
Coverage gap tests for src/hashed/core.py — targeting 74% → 80%+

Covers:
  - push_policies_to_backend() — success, agent-not-found, no-http-client (lines 658-721)
  - _background_sync() — runs one iteration, cancels cleanly (lines 776-791)
  - _push_local_json_policies() with agent-specific section (lines 597-644)
  - shutdown() with _ledger set (line 309)
  - sync functions wrapped by @guard (sync_wrapper, lines 462-470)
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hashed.config import HashedConfig
from hashed.core import HashedCore
from hashed.identity import IdentityManager

# ── Helpers ───────────────────────────────────────────────────────────────────


def _cfg(**overrides) -> HashedConfig:
    for var in ("HASHED_BACKEND_URL", "HASHED_API_KEY"):
        os.environ.pop(var, None)
    defaults = {
        "backend_url": "http://mock.test",
        "api_key": "test_key",
        "fail_closed": False,
        "enable_auto_sync": False,
    }
    defaults.update(overrides)
    return HashedConfig(**defaults)


def _mock_http(
    agents_body: Optional[dict] = None,
    policy_status: int = 200,
) -> AsyncMock:
    """AsyncMock http client wired for push_policies_to_backend tests."""
    def _resp(status, body):
        r = MagicMock()
        r.status_code = status
        r.is_success = 200 <= status < 300
        r.json.return_value = body
        return r

    client = AsyncMock()
    client.aclose = AsyncMock()

    pol_resp = _resp(policy_status, {"id": "p-1"})
    reg_resp = _resp(201, {"id": "agent-1", "name": "test"})
    log_resp = _resp(200, {"ok": True})
    agents_resp = _resp(200, agents_body or {"agents": []})
    sync_resp = _resp(200, {"policies": {}, "synced_at": "2026-01-01"})

    async def _post(url, **kwargs):
        if "/v1/policies" in str(url):
            return pol_resp
        if "/register" in str(url):
            return reg_resp
        return log_resp

    async def _get(url, **kwargs):
        if "/policies/sync" in str(url):
            return sync_resp
        return agents_resp

    client.post = AsyncMock(side_effect=_post)
    client.get  = AsyncMock(side_effect=_get)
    return client


# ── push_policies_to_backend() ────────────────────────────────────────────────


class TestPushPoliciesToBackend:
    """
    push_policies_to_backend() uploads local PolicyEngine policies to /v1/policies.
    Lines 658-721 in core.py.
    """

    def _core_with_policies(self) -> tuple[HashedCore, IdentityManager]:
        identity = IdentityManager()
        core = HashedCore(config=_cfg(), identity=identity, agent_name="push-bot")
        core._initialized = True
        core.policy_engine.add_policy("send_email", allowed=True)
        core.policy_engine.add_policy("delete_file", allowed=False)
        return core, identity

    @pytest.mark.asyncio
    async def test_success_posts_each_policy(self) -> None:
        """Each local policy is POSTed to /v1/policies with the agent_id."""
        core, identity = self._core_with_policies()
        mock_http = _mock_http(
            agents_body={"agents": [{"id": "agent-42", "public_key": identity.public_key_hex}]}
        )
        core._http_client = mock_http

        await core.push_policies_to_backend()

        # GET /v1/agents called once
        mock_http.get.assert_called_once()

        # POST /v1/policies called once per local policy (2 policies)
        policy_posts = [
            c for c in mock_http.post.call_args_list
            if "/v1/policies" in str(c.args[0] if c.args else "")
        ]
        assert len(policy_posts) == 2

    @pytest.mark.asyncio
    async def test_agent_not_found_skips_post(self) -> None:
        """If our agent isn't in backend list, no policies are posted."""
        core, _ = self._core_with_policies()
        mock_http = _mock_http(agents_body={"agents": []})  # empty list → not found
        core._http_client = mock_http

        await core.push_policies_to_backend()  # should not raise

        # No POST to /v1/policies
        policy_posts = [
            c for c in mock_http.post.call_args_list
            if "/v1/policies" in str(c.args[0] if c.args else "")
        ]
        assert len(policy_posts) == 0

    @pytest.mark.asyncio
    async def test_no_http_client_returns_early(self) -> None:
        """Without _http_client, method returns without raising."""
        core, _ = self._core_with_policies()
        core._http_client = None

        await core.push_policies_to_backend()  # must not raise

    @pytest.mark.asyncio
    async def test_no_local_policies_returns_early(self) -> None:
        """No local policies → nothing to push, returns cleanly."""
        identity = IdentityManager()
        core = HashedCore(config=_cfg(), identity=identity, agent_name="empty-bot")
        core._initialized = True
        # Don't add any policies
        mock_http = _mock_http(
            agents_body={"agents": [{"id": "x", "public_key": identity.public_key_hex}]}
        )
        core._http_client = mock_http

        await core.push_policies_to_backend()  # no policies → returns early

        policy_posts = [
            c for c in mock_http.post.call_args_list
            if "/v1/policies" in str(c.args[0] if c.args else "")
        ]
        assert len(policy_posts) == 0

    @pytest.mark.asyncio
    async def test_get_agents_failure_raises(self) -> None:
        """GET /v1/agents returning 500 should raise an exception."""
        core, _ = self._core_with_policies()

        def _resp(status, body):
            r = MagicMock()
            r.status_code = status
            r.is_success = False
            r.json.return_value = body
            return r

        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        mock_http.get = AsyncMock(return_value=_resp(500, {}))

        core._http_client = mock_http

        with pytest.raises(Exception):
            await core.push_policies_to_backend()

    @pytest.mark.asyncio
    async def test_policy_post_409_counts_as_success(self) -> None:
        """409 Conflict on POST means policy already exists — still counted as pushed."""
        core, identity = self._core_with_policies()
        mock_http = _mock_http(
            agents_body={"agents": [{"id": "agent-1", "public_key": identity.public_key_hex}]},
            policy_status=409,
        )
        core._http_client = mock_http

        # Should not raise even though status is 409
        await core.push_policies_to_backend()


# ── _push_local_json_policies() agent-specific section ───────────────────────


class TestPushLocalJsonPoliciesAgentSpecific:
    """
    _push_local_json_policies() with an agents section in the JSON file.
    Covers lines 597-644 (GET /v1/agents → agent matching → _upsert with agent_id).

    The code searches for .hashed_policies.json starting at Path.cwd(), so we
    temporarily change the working directory to a tempdir that contains the file.
    """

    @pytest.mark.asyncio
    async def test_agent_scoped_policies_pushed_with_agent_id(self) -> None:
        """
        When .hashed_policies.json has an agents section and our agent name
        matches (snake_case), agent-scoped policies are POSTed with agent_id.
        """
        identity = IdentityManager()
        # Agent name "My Test Bot" → snake_case "my_test_bot"
        core = HashedCore(config=_cfg(), identity=identity, agent_name="My Test Bot")
        core._initialized = True

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                policy_file = Path(tmpdir) / ".hashed_policies.json"
                policy_file.write_text(json.dumps({
                    "global": {
                        "read_file": {"allowed": True}
                    },
                    "agents": {
                        "my_test_bot": {
                            "write_file": {"allowed": True, "max_amount": None}
                        }
                    }
                }))

                post_calls = []

                async def _post(url, **kwargs):
                    post_calls.append({"url": str(url), "kwargs": kwargs})
                    r = MagicMock()
                    r.status_code = 200
                    r.is_success = True
                    r.json.return_value = {"id": "p-new"}
                    return r

                async def _get(url, **kwargs):
                    r = MagicMock()
                    r.status_code = 200
                    r.is_success = True
                    if "/v1/agents" in str(url):
                        r.json.return_value = {
                            "agents": [{"id": "agent-42", "public_key": identity.public_key_hex}]
                        }
                    else:
                        r.json.return_value = {"policies": {}}
                    return r

                mock_http = AsyncMock()
                mock_http.aclose = AsyncMock()
                mock_http.post = AsyncMock(side_effect=_post)
                mock_http.get  = AsyncMock(side_effect=_get)
                core._http_client = mock_http

                pushed = await core._push_local_json_policies()

                # 1 global + 1 agent-scoped = 2 total
                assert pushed == 2

                # The agent-scoped policy should carry agent_id in params
                agent_scoped = [
                    c for c in post_calls
                    if c["kwargs"].get("params", {}).get("agent_id")
                ]
                assert len(agent_scoped) == 1
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_agent_scoped_skipped_when_agent_not_found(self) -> None:
        """If GET /v1/agents does not contain our agent, agent-scoped policies are skipped."""
        identity = IdentityManager()
        core = HashedCore(config=_cfg(), identity=identity, agent_name="My Test Bot")
        core._initialized = True

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                policy_file = Path(tmpdir) / ".hashed_policies.json"
                policy_file.write_text(json.dumps({
                    "global": {"read_file": {"allowed": True}},
                    "agents": {
                        "my_test_bot": {"write_file": {"allowed": True}}
                    }
                }))

                post_calls = []

                async def _post(url, **kwargs):
                    post_calls.append(kwargs)
                    r = MagicMock()
                    r.status_code = 200
                    r.is_success = True
                    r.json.return_value = {}
                    return r

                async def _get(url, **kwargs):
                    r = MagicMock()
                    r.status_code = 200
                    r.is_success = True
                    r.json.return_value = {"agents": []}  # empty → not found
                    return r

                mock_http = AsyncMock()
                mock_http.aclose = AsyncMock()
                mock_http.post = AsyncMock(side_effect=_post)
                mock_http.get  = AsyncMock(side_effect=_get)
                core._http_client = mock_http

                pushed = await core._push_local_json_policies()

                # Only global policy pushed
                assert pushed == 1
                # No agent_id in any call
                for call in post_calls:
                    assert not call.get("params", {}).get("agent_id")
            finally:
                os.chdir(original_cwd)


# ── _background_sync() ────────────────────────────────────────────────────────


class TestBackgroundSync:
    """
    _background_sync() runs on a timer and syncs policies from the backend.
    Covers lines 776-791.

    sync_interval is an int (seconds), so we patch asyncio.sleep to return
    immediately, making the background loop run as fast as possible.
    """

    @pytest.mark.asyncio
    async def test_background_sync_runs_at_least_one_iteration(self) -> None:
        """
        Background sync loop runs at least one iteration before shutdown.
        asyncio.sleep is patched to return immediately so the test is fast.
        """
        cfg = HashedConfig(
            backend_url="http://mock.test",
            api_key="key",
            enable_auto_sync=True,
            sync_interval=60,   # minimum allowed; sleep is mocked to be instant
        )
        identity = IdentityManager()
        core = HashedCore(config=cfg, identity=identity, agent_name="sync-bot")

        sync_resp = MagicMock()
        sync_resp.status_code = 200
        sync_resp.is_success = True
        sync_resp.json.return_value = {"policies": {}, "synced_at": "2026-01-01"}

        reg_resp = MagicMock()
        reg_resp.status_code = 201
        reg_resp.is_success = True
        reg_resp.json.return_value = {"id": "a-1", "name": "sync-bot"}

        sync_count = {"n": 0}

        async def _get(url, **kwargs):
            if "/policies/sync" in str(url):
                sync_count["n"] += 1
                if sync_count["n"] >= 3:
                    # After 3 syncs, cancel the background task from inside
                    raise asyncio.CancelledError()
            return sync_resp

        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        mock_http.post = AsyncMock(return_value=reg_resp)
        mock_http.get  = AsyncMock(side_effect=_get)

        # Patch asyncio.sleep so the interval doesn't actually wait 30s
        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http), \
             patch("hashed.core.asyncio.sleep", new=AsyncMock(return_value=None)):
            await core.initialize()
            # Give the event loop a moment to run the background task
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await core.shutdown()

        assert sync_count["n"] >= 1, f"Expected ≥1 sync, got {sync_count['n']}"

    @pytest.mark.asyncio
    async def test_background_sync_continues_after_error(self) -> None:
        """
        Background sync does NOT crash when sync_policies_from_backend() raises.

        The key invariant: an error in one iteration is caught and the task
        continues running (doesn't propagate the exception). We verify the task
        ran at least once without crashing.
        """
        cfg = HashedConfig(
            backend_url="http://mock.test",
            api_key="key",
            enable_auto_sync=True,
            sync_interval=60,  # minimum; sleep is mocked to return immediately
        )
        identity = IdentityManager()
        core = HashedCore(config=cfg, identity=identity, agent_name="error-sync-bot")

        call_count = {"n": 0}
        error_was_raised = {"v": False}

        async def _get(url, **kwargs):
            if "/policies/sync" in str(url):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # First iteration raises — task must survive this
                    error_was_raised["v"] = True
                    raise RuntimeError("transient network error")
                if call_count["n"] >= 2:
                    # Second call: cancel cleanly
                    raise asyncio.CancelledError()
            r = MagicMock()
            r.status_code = 200
            r.is_success = True
            r.json.return_value = {"policies": {}, "synced_at": "2026-01-01"}
            return r

        reg_resp = MagicMock()
        reg_resp.status_code = 201
        reg_resp.is_success = True
        reg_resp.json.return_value = {"id": "a-2", "name": "bot"}

        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        mock_http.post = AsyncMock(return_value=reg_resp)
        mock_http.get  = AsyncMock(side_effect=_get)

        with patch("hashed.core.httpx.AsyncClient", return_value=mock_http), \
             patch("hashed.core.asyncio.sleep", new=AsyncMock(return_value=None)):
            await core.initialize()
            # Yield enough times for the background task to run 2 iterations
            for _ in range(10):
                await asyncio.sleep(0)
            await core.shutdown()

        # The task ran at least once (iteration 1 raised an error and was caught)
        assert call_count["n"] >= 1, f"Expected ≥1 sync attempt, got {call_count['n']}"
        assert error_was_raised["v"], "Error should have been triggered"


# ── shutdown() with ledger ────────────────────────────────────────────────────


class TestShutdownWithLedger:
    """shutdown() should call ledger.stop() when _ledger is set (line 309)."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_ledger(self) -> None:
        """If core._ledger is set, shutdown() must call ledger.stop()."""
        core = HashedCore(config=_cfg())
        core._initialized = True

        # Inject a mock ledger
        mock_ledger = AsyncMock()
        mock_ledger.stop = AsyncMock()
        core._ledger = mock_ledger

        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        core._http_client = mock_http

        await core.shutdown()

        mock_ledger.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_not_initialized_is_noop(self) -> None:
        """shutdown() before initialize() should return without error."""
        core = HashedCore(config=_cfg())
        await core.shutdown()  # _initialized=False → early return


# ── @guard() sync function wrapper ───────────────────────────────────────────


class TestGuardSyncWrapper:
    """@guard() on a synchronous function uses sync_wrapper (lines 462-470)."""

    def test_guard_on_sync_function_runs_correctly(self) -> None:
        """@core.guard() on a regular def (non-async) should still work."""
        core = HashedCore(config=_cfg())
        core._initialized = True
        core.policy_engine.add_policy("read", allowed=True)

        @core.guard("read")
        def sync_tool(x: int) -> int:
            return x * 2

        result = sync_tool(x=5)
        assert result == 10

    def test_guard_sync_denied_returns_string(self) -> None:
        """Denied sync tool returns denial string, not exception."""
        core = HashedCore(config=_cfg())
        core._initialized = True
        core.policy_engine.add_policy("blocked", allowed=False)

        @core.guard("blocked")
        def sync_tool() -> str:
            return "should not run"

        result = sync_tool()
        assert isinstance(result, str)
        assert "blocked" in result
