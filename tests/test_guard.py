"""
Tests for @core.guard() decorator.

Covers the two key behaviours introduced in fix(guard):
1. Policy denial is logged to the backend audit trail.
2. By default (raise_on_deny=False) the guard returns a human-readable
   string instead of raising PermissionError so LangChain/CrewAI agents
   don't crash.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hashed.config import HashedConfig
from hashed.core import HashedCore
from hashed.guard import PermissionError as HashedPermissionError
from hashed.identity import IdentityManager

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_core(*, backend: bool = False) -> HashedCore:
    """
    Create a HashedCore instance with policies pre-loaded, no real HTTP.

    Args:
        backend: If True, simulate a connected backend (mocked httpx client).
    """
    config = HashedConfig(
        api_url="https://mock.api.test",
        backend_url="https://mock.api.test" if backend else None,
        api_key="test_key" if backend else None,
        timeout=5.0,
        max_retries=0,
        verify_ssl=False,
    )
    identity = IdentityManager()  # generates a fresh Ed25519 key pair
    core = HashedCore(config=config, identity=identity, agent_name="test-agent")

    # Pre-load policies directly into the engine (skip network sync)
    core.policy_engine.add_policy("allowed_tool", allowed=True)
    core.policy_engine.add_policy("denied_tool", allowed=False)
    core.policy_engine.add_policy("amount_tool", allowed=True, max_amount=100.0)

    return core


def _mock_http_client() -> MagicMock:
    """Return a mock httpx.AsyncClient that always succeeds."""
    mock = MagicMock()
    mock.post = AsyncMock(
        return_value=MagicMock(
            is_success=True,
            status_code=200,
            json=lambda: {"allowed": True, "policy": None, "message": "allowed"},
        )
    )
    mock.aclose = AsyncMock()
    return mock


# ── Tests: default raise_on_deny=False ────────────────────────────────────────


class TestGuardDefaultBehaviour:
    """Guard with raise_on_deny=False (default — safe for LangChain/CrewAI)."""

    @pytest.mark.asyncio
    async def test_allowed_operation_executes_function(self) -> None:
        """When policy allows, the decorated function runs and returns its value."""
        core = _make_core()

        @core.guard("allowed_tool")
        async def my_tool(data: str) -> str:
            return f"result: {data}"

        result = await my_tool(data="hello")
        assert result == "result: hello"

    @pytest.mark.asyncio
    async def test_denied_operation_returns_string(self) -> None:
        """
        When policy denies, guard returns a descriptive string.
        The agent (LangChain, CrewAI, …) reads this as the tool's output
        and can explain to the user — no exception, no crash.
        """
        core = _make_core()

        @core.guard("denied_tool")
        async def my_tool(data: str) -> str:
            return f"result: {data}"

        result = await my_tool(data="hello")

        # Must be a string, not an exception
        assert isinstance(result, str)
        # Must mention the tool name so the agent can explain it
        assert "denied_tool" in result
        # Must NOT execute the function body
        assert "result:" not in result

    @pytest.mark.asyncio
    async def test_denied_string_contains_governance_message(self) -> None:
        """The denial string guides the agent to inform the user."""
        core = _make_core()

        @core.guard("denied_tool")
        async def my_tool(data: str) -> str:
            return "should not run"

        result = await my_tool(data="x")
        # The string should be self-explanatory to the agent
        assert (
            "Permission denied" in result
            or "not allowed" in result
            or "BLOCKED" in result
        )

    @pytest.mark.asyncio
    async def test_denied_function_body_never_executes(self) -> None:
        """Ensure the underlying function is NOT called when denied."""
        core = _make_core()
        called = []

        @core.guard("denied_tool")
        async def side_effect_tool(data: str) -> str:
            called.append(True)
            return "ran"

        await side_effect_tool(data="test")
        assert called == [], "Function body must not execute on denial"


# ── Tests: raise_on_deny=True ─────────────────────────────────────────────────


class TestGuardRaiseOnDeny:
    """Guard with raise_on_deny=True (for non-agent code that wants exceptions)."""

    @pytest.mark.asyncio
    async def test_denied_raises_permission_error(self) -> None:
        """With raise_on_deny=True, a denied operation raises PermissionError."""
        core = _make_core()

        @core.guard("denied_tool", raise_on_deny=True)
        async def my_tool(data: str) -> str:
            return "should not run"

        with pytest.raises(HashedPermissionError):
            await my_tool(data="hello")

    @pytest.mark.asyncio
    async def test_allowed_still_works_with_raise_on_deny(self) -> None:
        """raise_on_deny=True doesn't affect allowed operations."""
        core = _make_core()

        @core.guard("allowed_tool", raise_on_deny=True)
        async def my_tool(data: str) -> str:
            return f"ok: {data}"

        result = await my_tool(data="world")
        assert result == "ok: world"


# ── Tests: amount / max_amount enforcement ────────────────────────────────────


class TestGuardAmountPolicy:

    @pytest.mark.asyncio
    async def test_amount_within_limit_allowed(self) -> None:
        """Operations within max_amount should succeed."""
        core = _make_core()

        @core.guard("amount_tool", amount_param="amount")
        async def transfer(amount: float) -> str:
            return f"transferred {amount}"

        result = await transfer(amount=50.0)
        assert result == "transferred 50.0"

    @pytest.mark.asyncio
    async def test_amount_exceeds_limit_denied_returns_string(self) -> None:
        """Operations exceeding max_amount return denial string by default."""
        core = _make_core()

        @core.guard("amount_tool", amount_param="amount")
        async def transfer(amount: float) -> str:
            return f"transferred {amount}"

        result = await transfer(amount=500.0)  # limit is 100
        assert isinstance(result, str)
        # Function should not have executed
        assert "transferred" not in result

    @pytest.mark.asyncio
    async def test_amount_exceeds_limit_raises_with_flag(self) -> None:
        """Exceeding max_amount raises PermissionError when raise_on_deny=True."""
        core = _make_core()

        @core.guard("amount_tool", amount_param="amount", raise_on_deny=True)
        async def transfer(amount: float) -> str:
            return f"transferred {amount}"

        with pytest.raises(HashedPermissionError):
            await transfer(amount=500.0)


# ── Tests: backend audit logging ──────────────────────────────────────────────


class TestGuardAuditLogging:

    @pytest.mark.asyncio
    async def test_denial_logged_to_backend(self) -> None:
        """
        When a tool is denied, the guard must POST to /log with status='denied'.
        This ensures denials appear in the dashboard audit trail.
        """
        core = _make_core(backend=True)
        mock_client = _mock_http_client()

        # Override the /guard response to say "allowed" (backend agrees with local policy
        # is NOT needed here — local policy already denies)
        # We only want to verify /log is called with status=denied
        log_calls = []

        async def capture_post(url: str, **kwargs: Any) -> MagicMock:
            payload = kwargs.get("json", {})
            log_calls.append({"url": url, "payload": payload})
            return MagicMock(
                is_success=True,
                status_code=200,
                json=lambda: {"allowed": False, "policy": "denied"},
            )

        mock_client.post = capture_post
        core._http_client = mock_client

        @core.guard("denied_tool")
        async def my_tool(data: str) -> str:
            return "should not run"

        await my_tool(data="test")

        # At least one POST to /log with status='denied'
        log_entries = [c for c in log_calls if "/log" in c["url"]]
        assert log_entries, "Expected at least one POST to /log endpoint"
        denied_entries = [
            c for c in log_entries if c["payload"].get("status") == "denied"
        ]
        assert denied_entries, "Expected log entry with status='denied'"

    @pytest.mark.asyncio
    async def test_success_logged_to_backend(self) -> None:
        """Successful operations are logged to /log with status='success'."""
        core = _make_core(backend=True)
        mock_client = _mock_http_client()

        log_calls = []

        async def capture_post(url: str, **kwargs: Any) -> MagicMock:
            payload = kwargs.get("json", {})
            log_calls.append({"url": url, "payload": payload})
            return MagicMock(
                is_success=True,
                status_code=200,
                json=lambda: {"allowed": True, "policy": None},
            )

        mock_client.post = capture_post
        core._http_client = mock_client

        @core.guard("allowed_tool")
        async def my_tool(data: str) -> str:
            return "done"

        await my_tool(data="test")

        log_entries = [c for c in log_calls if "/log" in c["url"]]
        success_entries = [
            c for c in log_entries if c["payload"].get("status") == "success"
        ]
        assert success_entries, "Expected log entry with status='success'"


# ── Tests: offline mode (no backend) ─────────────────────────────────────────


class TestGuardOfflineMode:
    """Guard should work with local-only policies when no backend is configured."""

    @pytest.mark.asyncio
    async def test_allowed_offline(self) -> None:
        core = _make_core(backend=False)

        @core.guard("allowed_tool")
        async def my_tool(data: str) -> str:
            return f"offline: {data}"

        result = await my_tool(data="test")
        assert result == "offline: test"

    @pytest.mark.asyncio
    async def test_denied_offline_returns_string(self) -> None:
        core = _make_core(backend=False)

        @core.guard("denied_tool")
        async def my_tool(data: str) -> str:
            return "should not run"

        result = await my_tool(data="test")
        assert isinstance(result, str)
        assert "denied_tool" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_uses_default_allow(self) -> None:
        """Tools with no policy use the default policy (allow by default)."""
        core = _make_core(backend=False)
        # Default policy allows everything

        @core.guard("unknown_tool_xyz")
        async def my_tool() -> str:
            return "ran"

        result = await my_tool()
        assert result == "ran"


# ── Policy dataclass unit tests ───────────────────────────────────────────────


class TestPolicy:
    """Direct unit tests for the Policy dataclass and its validate() method."""

    def test_allowed_false_returns_false(self) -> None:
        """Policy.validate() returns False when allowed=False (line 52)."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=False)
        assert p.validate() is False

    def test_allowed_true_no_amount_returns_true(self) -> None:
        """Policy.validate() returns True when allowed and no amount checked."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=True)
        assert p.validate() is True

    def test_amount_within_limit_returns_true(self) -> None:
        """Policy.validate() returns True when amount ≤ max_amount."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=True, max_amount=100.0)
        assert p.validate(amount=50.0) is True

    def test_amount_exactly_at_limit_returns_true(self) -> None:
        """Policy.validate() returns True when amount == max_amount."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=True, max_amount=100.0)
        assert p.validate(amount=100.0) is True

    def test_amount_exceeds_limit_returns_false(self) -> None:
        """Policy.validate() returns False when amount > max_amount (line 57)."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=True, max_amount=100.0)
        assert p.validate(amount=101.0) is False

    def test_amount_none_with_max_amount_returns_true(self) -> None:
        """validate(amount=None) with a max_amount skips the limit check."""
        from hashed.guard import Policy

        p = Policy(tool_name="op", allowed=True, max_amount=100.0)
        assert p.validate(amount=None) is True

    def test_metadata_defaults_to_empty_dict(self) -> None:
        """Policy.__post_init__ sets metadata={} when None is passed."""
        from hashed.guard import Policy

        p = Policy(tool_name="op")
        assert p.metadata == {}


# ── PolicyEngine unit tests ───────────────────────────────────────────────────


class TestPolicyEngine:
    """Direct unit tests for PolicyEngine methods not covered by @guard tests."""

    def _engine(self):
        from hashed.guard import PolicyEngine

        return PolicyEngine()

    # remove_policy (line 120)
    def test_remove_policy_removes_existing(self) -> None:
        engine = self._engine()
        engine.add_policy("op")
        engine.remove_policy("op")
        assert not engine.has_policy("op")

    def test_remove_policy_raises_on_missing(self) -> None:
        engine = self._engine()
        with pytest.raises(KeyError):
            engine.remove_policy("nonexistent")

    # has_policy (line 144)
    def test_has_policy_returns_true_when_present(self) -> None:
        engine = self._engine()
        engine.add_policy("pay")
        assert engine.has_policy("pay") is True

    def test_has_policy_returns_false_when_absent(self) -> None:
        engine = self._engine()
        assert engine.has_policy("ghost") is False

    # set_default_policy (line 156)
    def test_set_default_policy_deny_all(self) -> None:
        """set_default_policy(allowed=False) blocks unknown tools."""
        from hashed.guard import PermissionError as PE

        engine = self._engine()
        engine.set_default_policy(allowed=False)
        with pytest.raises(PE):
            engine.validate("unknown_tool")

    def test_set_default_policy_max_amount(self) -> None:
        """set_default_policy with max_amount enforces limit on unknown tools."""
        from hashed.guard import PermissionError as PE

        engine = self._engine()
        engine.set_default_policy(max_amount=50.0)
        assert engine.validate("tool_x", amount=10.0) is True
        with pytest.raises(PE):
            engine.validate("tool_x", amount=100.0)

    # check_permission (lines 230-233)
    def test_check_permission_returns_false_when_denied(self) -> None:
        """check_permission() returns False instead of raising (line 230-233)."""
        engine = self._engine()
        engine.add_policy("restricted", allowed=False)
        assert engine.check_permission("restricted") is False

    def test_check_permission_returns_false_on_amount_exceeded(self) -> None:
        engine = self._engine()
        engine.add_policy("transfer", max_amount=100.0)
        assert engine.check_permission("transfer", amount=999.0) is False

    def test_check_permission_returns_true_when_allowed(self) -> None:
        engine = self._engine()
        engine.add_policy("read", allowed=True)
        assert engine.check_permission("read") is True

    # list_policies (line 242)
    def test_list_policies_returns_copy(self) -> None:
        engine = self._engine()
        engine.add_policy("a")
        engine.add_policy("b")
        policies = engine.list_policies()
        assert set(policies.keys()) == {"a", "b"}
        # Mutating the returned dict must not affect the engine
        policies["a"] = None  # type: ignore
        assert engine.has_policy("a")

    # bulk_add_policies (lines 258-259)
    def test_bulk_add_policies_adds_all(self) -> None:
        engine = self._engine()
        engine.bulk_add_policies(
            {
                "wire": {"max_amount": 1000.0, "allowed": True},
                "delete": {"allowed": False},
            }
        )
        assert engine.has_policy("wire")
        assert engine.has_policy("delete")
        assert engine.get_policy("wire").max_amount == 1000.0
        assert engine.get_policy("delete").allowed is False

    # export_policies (line 273)
    def test_export_policies_returns_dict(self) -> None:
        engine = self._engine()
        engine.add_policy("pay", max_amount=500.0, allowed=True)
        exported = engine.export_policies()
        assert "pay" in exported
        assert exported["pay"]["max_amount"] == 500.0
        assert exported["pay"]["allowed"] is True

    def test_export_policies_empty_engine(self) -> None:
        engine = self._engine()
        assert engine.export_policies() == {}

    # import_policies (line 289)
    def test_import_policies_loads_correctly(self) -> None:
        engine = self._engine()
        engine.import_policies(
            {
                "send_sms": {"max_amount": None, "allowed": True},
                "nuke": {"max_amount": None, "allowed": False},
            }
        )
        assert engine.has_policy("send_sms")
        assert engine.has_policy("nuke")
        assert engine.get_policy("nuke").allowed is False

    def test_export_then_import_roundtrip(self) -> None:
        """export_policies → import_policies preserves all policy data."""
        engine_a = self._engine()
        engine_a.add_policy("transfer", max_amount=200.0)
        engine_a.add_policy("read_only", allowed=True)

        exported = engine_a.export_policies()

        engine_b = self._engine()
        engine_b.import_policies(exported)

        assert engine_b.get_policy("transfer").max_amount == 200.0
        assert engine_b.has_policy("read_only")
