"""
Tests for HashedCore — targeting lines missing from the 15% baseline.

Focus areas:
  - Properties: identity, policy_engine, ledger
  - create_core() factory
  - shutdown() early return (not initialized)
  - guard() decorator in offline mode (no backend_url, no ledger)
    - success path
    - policy denial (string return)
    - policy denial with raise_on_deny=True
    - async and sync guards
    - exception propagation
  - context manager (__aenter__ / __aexit__)
"""

import asyncio

import pytest

from hashed import HashedConfig, HashedCore, IdentityManager
from hashed.core import create_core
from hashed.guard import PermissionError

# ── Helpers ───────────────────────────────────────────────────────────────────

def _offline_core(**kwargs) -> HashedCore:
    """Create a HashedCore with no backend_url so no HTTP calls are made.

    HashedConfig is a frozen Pydantic model, so we pass values at
    construction time rather than setting attributes afterward.
    We also strip any HASHED_BACKEND_URL / HASHED_API_KEY env vars
    that could make the default factory pick up a real URL.
    """
    import os
    # Temporarily clear env vars so HashedConfig defaults to None
    old_backend = os.environ.pop("HASHED_BACKEND_URL", None)
    old_api_key = os.environ.pop("HASHED_API_KEY", None)
    try:
        config = HashedConfig()  # reads from env — now empty → backend_url=None
    finally:
        if old_backend is not None:
            os.environ["HASHED_BACKEND_URL"] = old_backend
        if old_api_key is not None:
            os.environ["HASHED_API_KEY"] = old_api_key
    return HashedCore(config=config, **kwargs)


# ── Properties ────────────────────────────────────────────────────────────────


class TestHashedCoreProperties:
    """Tests for identity, policy_engine, and ledger properties."""

    def test_identity_property_returns_identity_manager(self):
        core = _offline_core()
        assert isinstance(core.identity, IdentityManager)

    def test_policy_engine_property_returns_engine(self):
        from hashed.guard import PolicyEngine
        core = _offline_core()
        assert isinstance(core.policy_engine, PolicyEngine)

    def test_ledger_property_returns_none_before_init(self):
        """Ledger should be None before initialize() is called."""
        core = _offline_core()
        assert core.ledger is None

    def test_agent_name_defaults_to_unnamed(self):
        core = _offline_core()
        assert core._agent_name == "Unnamed Agent"

    def test_agent_name_can_be_set(self):
        core = _offline_core(agent_name="Test Agent")
        assert core._agent_name == "Test Agent"

    def test_initialized_is_false_before_init(self):
        core = _offline_core()
        assert core._initialized is False


# ── create_core factory ───────────────────────────────────────────────────────


class TestCreateCore:
    """Tests for the create_core() convenience function."""

    def test_create_core_returns_hashed_core(self):
        core = create_core()
        assert isinstance(core, HashedCore)

    def test_create_core_with_policies(self):
        core = create_core(
            policies={
                "transfer": {"max_amount": 500.0, "allowed": True},
                "delete": {"allowed": False},
            }
        )
        # Both policies should be loaded into the policy engine
        assert "transfer" in core.policy_engine._policies
        assert "delete" in core.policy_engine._policies

    def test_create_core_with_config(self):
        """Config passed to create_core() should be used as-is."""
        core = _offline_core()           # already builds an offline config
        core2 = create_core(config=core._config)
        assert core2._config is core._config


# ── shutdown() early return ───────────────────────────────────────────────────


class TestShutdown:
    """Tests for shutdown() — should be a no-op when not initialized."""

    def test_shutdown_when_not_initialized_does_not_raise(self):
        core = _offline_core()
        # Should return immediately without error
        asyncio.run(core.shutdown())

    def test_shutdown_sets_initialized_false(self):
        core = _offline_core()
        core._initialized = True      # force-set as if initialized
        core._ledger = None           # no real ledger
        core._http_client = None      # no real http client
        asyncio.run(core.shutdown())
        assert core._initialized is False


# ── guard() decorator — offline allow ────────────────────────────────────────


class TestGuardOfflineAllow:
    """Guard decorator with no backend: allowed operations should execute."""

    def test_async_guard_allows_operation_with_no_policy(self):
        """With no policy set, default is allow."""
        core = _offline_core()

        @core.guard("my_tool")
        async def my_tool(x: int) -> int:
            return x * 2

        result = asyncio.run(my_tool(5))
        assert result == 10

    def test_multiple_async_tools_all_allowed(self):
        """Multiple tools can be guarded on the same core instance."""
        core = _offline_core()

        @core.guard("tool_a")
        async def tool_a() -> str:
            return "a"

        @core.guard("tool_b")
        async def tool_b() -> str:
            return "b"

        assert asyncio.run(tool_a()) == "a"
        assert asyncio.run(tool_b()) == "b"

    def test_async_guard_with_allowed_policy(self):
        """Explicit allow policy should let the function run."""
        core = _offline_core()
        core.policy_engine.add_policy("transfer", allowed=True, max_amount=1000.0)

        @core.guard("transfer", amount_param="amount")
        async def transfer(amount: float, to: str) -> dict:
            return {"status": "ok", "amount": amount}

        result = asyncio.run(transfer(amount=200.0, to="Alice"))
        assert result["status"] == "ok"
        assert result["amount"] == 200.0

    def test_guard_passes_args_through(self):
        """Arguments must be passed unchanged to the wrapped function."""
        core = _offline_core()

        received = {}

        @core.guard("echo")
        async def echo(msg: str, repeat: int = 1) -> str:
            received["msg"] = msg
            received["repeat"] = repeat
            return msg * repeat

        result = asyncio.run(echo(msg="hi", repeat=3))
        assert result == "hihihi"
        assert received["msg"] == "hi"
        assert received["repeat"] == 3


# ── guard() decorator — offline deny ─────────────────────────────────────────


class TestGuardOfflineDeny:
    """Guard decorator: denied operations return string by default."""

    def test_denied_policy_returns_blocked_string(self):
        """By default (raise_on_deny=False), denial returns a string."""
        core = _offline_core()
        core.policy_engine.add_policy("dangerous_op", allowed=False)

        @core.guard("dangerous_op")
        async def dangerous_op() -> str:
            return "this should not run"

        result = asyncio.run(dangerous_op())

        assert isinstance(result, str)
        assert "HASHED BLOCKED" in result or "denied" in result.lower() or "not allowed" in result.lower()

    def test_denied_policy_with_raise_on_deny_raises_permission_error(self):
        """raise_on_deny=True should raise PermissionError instead of returning a string."""
        core = _offline_core()
        core.policy_engine.add_policy("delete_all", allowed=False)

        @core.guard("delete_all", raise_on_deny=True)
        async def delete_all() -> str:
            return "should not run"

        with pytest.raises(PermissionError):
            asyncio.run(delete_all())

    def test_amount_exceeds_max_returns_blocked_string(self):
        """Amount over max_amount should be denied."""
        core = _offline_core()
        core.policy_engine.add_policy("wire", allowed=True, max_amount=100.0)

        @core.guard("wire", amount_param="amount")
        async def wire(amount: float) -> str:
            return "sent"

        result = asyncio.run(wire(amount=9999.0))

        # Should be denied (amount exceeds limit)
        assert isinstance(result, str)
        assert "HASHED BLOCKED" in result or "denied" in result.lower()

    def test_amount_within_limit_is_allowed(self):
        """Amount under max_amount should be allowed."""
        core = _offline_core()
        core.policy_engine.add_policy("wire", allowed=True, max_amount=1000.0)

        @core.guard("wire", amount_param="amount")
        async def wire(amount: float) -> str:
            return "sent"

        result = asyncio.run(wire(amount=50.0))
        assert result == "sent"


# ── guard() decorator — exception propagation ─────────────────────────────────


class TestGuardExceptionPropagation:
    """Exceptions raised inside guarded functions should propagate."""

    def test_exception_in_tool_propagates(self):
        """If the wrapped function raises, the exception should bubble up."""
        core = _offline_core()

        @core.guard("failing_tool")
        async def failing_tool() -> str:
            raise ValueError("intentional error")

        with pytest.raises(ValueError, match="intentional error"):
            asyncio.run(failing_tool())

    def test_exception_does_not_affect_other_calls(self):
        """An exception in one call should not affect subsequent calls."""
        core = _offline_core()
        call_count = 0

        @core.guard("sometimes_fails")
        async def sometimes_fails(should_fail: bool) -> str:
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise RuntimeError("fail")
            return "ok"

        with pytest.raises(RuntimeError):
            asyncio.run(sometimes_fails(should_fail=True))

        # Second call should work fine
        result = asyncio.run(sometimes_fails(should_fail=False))
        assert result == "ok"
        assert call_count == 2


# ── context manager ───────────────────────────────────────────────────────────


class TestContextManager:
    """HashedCore as async context manager."""

    def test_async_context_manager_enters_and_exits(self):
        """async with HashedCore() should initialize and shutdown cleanly."""
        # Build offline config via the helper (handles frozen Pydantic model)
        offline = _offline_core(agent_name="ctx-test")
        config = offline._config   # already a valid offline HashedConfig

        async def run():
            async with HashedCore(config=config, agent_name="ctx-test") as core:
                assert core._initialized is True
                assert isinstance(core.identity, IdentityManager)
            # After __aexit__, should be shut down
            assert core._initialized is False

        asyncio.run(run())


# ── policy_engine integration ─────────────────────────────────────────────────


class TestPolicyEngineIntegration:
    """Tests for adding/querying policies on the live PolicyEngine."""

    def test_bulk_add_policies_via_create_core(self):
        """Policies passed to create_core() are accessible via policy_engine."""
        core = create_core(
            policies={
                "read": {"allowed": True},
                "write": {"allowed": True, "max_amount": 100.0},
                "admin": {"allowed": False},
            }
        )
        assert core.policy_engine._policies["admin"].allowed is False
        assert core.policy_engine._policies["write"].max_amount == 100.0

    def test_add_policy_after_creation(self):
        """Policies can be added to the engine after HashedCore is created."""
        core = _offline_core()
        core.policy_engine.add_policy("new_op", allowed=True, max_amount=50.0)
        assert "new_op" in core.policy_engine._policies


# ── Canonical sign_operation envelopes ───────────────────────────────────────


class TestCanonicalSignedPayload:
    """
    Verify that guard() now uses IdentityManager.sign_operation() (SPEC §2.1)
    for every lifecycle state: allowed, denied, and the /guard POST.
    """

    def test_guard_produces_canonical_payload(self):
        """
        A successful guard call must pass a sign_operation()-produced dict
        to _log_to_all_transports with all 8 canonical fields.
        """
        from unittest.mock import patch

        core = _offline_core()
        captured: dict = {}

        async def _capture(tool_name, status, amount, result_or_str, signed):
            captured["signed"] = signed

        @core.guard("canonical_test")
        async def my_tool() -> str:
            return "ok"

        with patch.object(core, "_log_to_all_transports", side_effect=_capture):
            result = asyncio.run(my_tool())

        assert result == "ok"

        signed = captured.get("signed", {})
        payload = signed.get("payload", {})

        # All 8 SPEC §2.1 canonical fields must be present
        assert payload.get("version") == 1
        assert "nonce" in payload
        assert "timestamp_ns" in payload
        assert payload.get("operation") == "canonical_test"
        assert payload.get("status") == "allowed"
        assert "agent_id" in payload
        assert "amount" in payload
        assert "context" in payload

        # The envelope must contain signature and canonical string
        assert "signature" in signed
        assert len(signed["signature"]) == 128       # Ed25519 hex = 64 bytes
        assert "canonical" in signed
        assert '"version":1' in signed["canonical"]

    def test_denial_is_also_signed_canonically(self):
        """
        A denied operation must call _log_to_all_transports with
        status='denied' and a sign_operation() envelope whose payload
        has status='denied' and all canonical fields present.
        """
        from unittest.mock import patch

        core = _offline_core()
        core.policy_engine.add_policy("blocked_op", allowed=False)
        captured: dict = {}

        async def _capture(tool_name, status, amount, result_or_str, signed):
            captured["signed"] = signed
            captured["status"] = status

        @core.guard("blocked_op")
        async def blocked() -> str:
            return "should not run"

        with patch.object(core, "_log_to_all_transports", side_effect=_capture):
            result = asyncio.run(blocked())

        # guard() returns the BLOCKED string, not the function result
        assert "HASHED BLOCKED" in result or "denied" in result.lower()

        assert captured.get("status") == "denied"

        signed = captured.get("signed", {})
        payload = signed.get("payload", {})
        assert payload.get("status") == "denied"
        assert payload.get("version") == 1
        assert "nonce" in payload
        assert "timestamp_ns" in payload
        assert len(signed.get("signature", "")) == 128

    def test_remote_guard_sends_nonce(self):
        """
        _execute_remote_guard must include nonce, timestamp_ns, signature,
        and canonical in the JSON body of the POST /guard request.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        core = _offline_core()
        posted_body: dict = {}

        async def run() -> None:
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"allowed": True}

            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            core._http_client = mock_http

            await core._execute_remote_guard(
                "send_email", 50.0, {"to": "alice@example.com"}
            )

            call_args = mock_http.post.call_args
            # Support both positional and keyword call styles
            body = (
                call_args[1].get("json")
                or (call_args[0][1] if len(call_args[0]) > 1 else {})
            )
            posted_body.update(body or {})
            core._http_client = None

        asyncio.run(run())

        assert "nonce" in posted_body,       "nonce missing from /guard POST body"
        assert "timestamp_ns" in posted_body, "timestamp_ns missing from /guard POST body"
        assert "signature" in posted_body,   "signature missing from /guard POST body"
        assert "canonical" in posted_body,   "canonical missing from /guard POST body"
        assert posted_body.get("operation") == "send_email"
        assert posted_body.get("agent_public_key") is not None
