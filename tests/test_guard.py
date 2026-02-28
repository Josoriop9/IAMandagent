"""
Tests for @core.guard() decorator.

Covers the two key behaviours introduced in fix(guard):
1. Policy denial is logged to the backend audit trail.
2. By default (raise_on_deny=False) the guard returns a human-readable
   string instead of raising PermissionError so LangChain/CrewAI agents
   don't crash.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
    mock.post = AsyncMock(return_value=MagicMock(
        is_success=True,
        status_code=200,
        json=lambda: {"allowed": True, "policy": None, "message": "allowed"},
    ))
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
        assert "Permission denied" in result or "not allowed" in result or "BLOCKED" in result

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
            c for c in log_entries
            if c["payload"].get("status") == "denied"
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
            c for c in log_entries
            if c["payload"].get("status") == "success"
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
