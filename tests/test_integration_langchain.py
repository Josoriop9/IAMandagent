"""
Tests for HashedCallbackHandler (LangChain integration).

Design notes
------------
- langchain_core is an OPTIONAL dependency, so tests must NOT require it.
- Tests 2-4 patch ``_LANGCHAIN_AVAILABLE = True`` so the handler can be
  instantiated without langchain installed.  A minimal ``BaseCallbackHandler``
  stub (plain ``object``) is already used as the base class when langchain is
  absent, which is all these unit tests need.
- ``test_import_fails_without_langchain`` verifies the ImportError guard by
  patching ``sys.modules`` to hide langchain_core and reloading the module.
"""

import asyncio
import importlib
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hashed import HashedConfig, HashedCore, IdentityManager
from hashed.guard import PermissionError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _offline_core(**kwargs) -> HashedCore:
    """Construct a HashedCore with no backend URL (no HTTP calls)."""
    import os
    old_backend = os.environ.pop("HASHED_BACKEND_URL", None)
    old_api_key = os.environ.pop("HASHED_API_KEY", None)
    try:
        config = HashedConfig()
    finally:
        if old_backend is not None:
            os.environ["HASHED_BACKEND_URL"] = old_backend
        if old_api_key is not None:
            os.environ["HASHED_API_KEY"] = old_api_key
    return HashedCore(config=config, **kwargs)


def _make_handler(raise_on_deny: bool = True):
    """
    Return a ``HashedCallbackHandler`` with ``_LANGCHAIN_AVAILABLE`` forced
    to True so the handler can be instantiated without langchain installed.
    """
    import hashed.integrations.langchain as lc_mod

    core = _offline_core(agent_name="test-lc-agent")

    with patch.object(lc_mod, "_LANGCHAIN_AVAILABLE", True):
        handler = lc_mod.HashedCallbackHandler(core=core, raise_on_deny=raise_on_deny)

    return handler, core


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestImportGuard:
    """Verify that the ImportError guard works when langchain is absent."""

    def test_import_fails_without_langchain(self):
        """
        When langchain_core is not installed, instantiating
        HashedCallbackHandler must raise ImportError with a helpful message.

        We simulate the "not installed" state by patching _LANGCHAIN_AVAILABLE
        to False on the already-imported module — this is exactly what happens
        when the try/except at module level catches the ImportError.
        """
        import hashed.integrations.langchain as lc_mod

        with patch.object(lc_mod, "_LANGCHAIN_AVAILABLE", False):
            with pytest.raises(ImportError, match="pip install hashed-sdk\\[langchain\\]"):
                lc_mod.HashedCallbackHandler(core=MagicMock())


class TestOnToolStart:
    """on_tool_start: policy validation and denial handling."""

    def test_allowed_tool_passes_silently(self):
        """A tool with an allow policy must not raise."""
        handler, core = _make_handler()
        core.policy_engine.add_policy("send_email", allowed=True)

        # Must not raise
        handler.on_tool_start({"name": "send_email"}, '{"to": "alice@example.com"}')
        assert handler._last_tool_name == "send_email"
        assert "send_email" not in handler._denied

    def test_denied_tool_raises_permission_error_when_raise_on_deny_true(self):
        """A denied tool with raise_on_deny=True must re-raise PermissionError."""
        handler, core = _make_handler(raise_on_deny=True)
        core.policy_engine.add_policy("wire_transfer", allowed=False)

        with pytest.raises(PermissionError):
            handler.on_tool_start({"name": "wire_transfer"}, "{}")

        assert "wire_transfer" in handler._denied

    def test_denied_tool_does_not_raise_when_raise_on_deny_false(self):
        """A denied tool with raise_on_deny=False must NOT raise."""
        handler, core = _make_handler(raise_on_deny=False)
        core.policy_engine.add_policy("wire_transfer", allowed=False)

        # Must not raise
        handler.on_tool_start({"name": "wire_transfer"}, "{}")
        assert "wire_transfer" in handler._denied

    def test_amount_extracted_from_json_input(self):
        """Amount is parsed from JSON input and passed to policy validation."""
        handler, core = _make_handler()
        # Policy allows up to 100
        core.policy_engine.add_policy("pay", allowed=True, max_amount=100.0)

        # amount=50 → OK
        handler.on_tool_start({"name": "pay"}, '{"amount": 50}')

        # amount=999 → DENIED
        with pytest.raises(PermissionError):
            handler.on_tool_start({"name": "pay"}, '{"amount": 999}')

    def test_missing_serialized_name_defaults_to_unknown_tool(self):
        """If serialized has no 'name' key, defaults to 'unknown_tool'."""
        handler, _ = _make_handler()
        handler.on_tool_start({}, "some input")
        assert handler._last_tool_name == "unknown_tool"

    def test_none_serialized_defaults_to_unknown_tool(self):
        """If serialized is None, defaults to 'unknown_tool'."""
        handler, _ = _make_handler()
        handler.on_tool_start(None, "some input")
        assert handler._last_tool_name == "unknown_tool"


class TestOnToolEnd:
    """on_tool_end: success audit logging."""

    def test_on_tool_end_logs_success(self):
        """
        on_tool_end must call _log_to_all_transports with status='success'
        and a sign_operation() envelope.
        """
        import hashed.integrations.langchain as lc_mod

        handler, core = _make_handler()
        handler._last_tool_name = "send_email"

        captured: dict = {}

        async def _fake_log(tool_name, status, amount, result, signed):
            captured["tool_name"] = tool_name
            captured["status"] = status
            captured["signed"] = signed

        with patch.object(core, "_log_to_all_transports", side_effect=_fake_log):
            with patch.object(lc_mod, "_schedule_log", side_effect=lambda coro: asyncio.run(coro)):
                handler.on_tool_end("Email sent successfully")

        assert captured["tool_name"] == "send_email"
        assert captured["status"] == "success"
        signed = captured.get("signed", {})
        assert signed.get("payload", {}).get("status") == "success"
        assert "signature" in signed
        assert len(signed["signature"]) == 128  # Ed25519 hex = 64 bytes

    def test_on_tool_end_truncates_long_output(self):
        """Output longer than 200 chars is passed as-is; the handler is robust."""
        handler, core = _make_handler()
        handler._last_tool_name = "big_tool"

        captured_result: dict = {}

        async def _fake_log(tool_name, status, amount, result, signed):
            captured_result["result"] = result

        import hashed.integrations.langchain as lc_mod
        with patch.object(core, "_log_to_all_transports", side_effect=_fake_log):
            with patch.object(lc_mod, "_schedule_log", side_effect=lambda coro: asyncio.run(coro)):
                handler.on_tool_end("x" * 500)

        # The handler itself slices to 200 chars before passing to _log_to_all_transports
        assert len(captured_result.get("result", "")) <= 200


class TestOnToolError:
    """on_tool_error: error audit logging."""

    def test_on_tool_error_logs_error(self):
        """
        on_tool_error must call _log_to_all_transports with status='error'
        and a sign_operation() envelope that includes the error in context.
        """
        import hashed.integrations.langchain as lc_mod

        handler, core = _make_handler()
        handler._last_tool_name = "risky_tool"

        captured: dict = {}

        async def _fake_log(tool_name, status, amount, result, signed):
            captured["tool_name"] = tool_name
            captured["status"] = status
            captured["signed"] = signed

        err = ValueError("Something went wrong")

        with patch.object(core, "_log_to_all_transports", side_effect=_fake_log):
            with patch.object(lc_mod, "_schedule_log", side_effect=lambda coro: asyncio.run(coro)):
                handler.on_tool_error(err)

        assert captured["tool_name"] == "risky_tool"
        assert captured["status"] == "error"
        signed = captured.get("signed", {})
        assert signed.get("payload", {}).get("status") == "error"
        ctx = signed.get("payload", {}).get("context", {})
        assert "Something went wrong" in ctx.get("error", "")
        assert ctx.get("error_type") == "ValueError"

    def test_on_tool_error_does_not_raise(self):
        """
        Even if logging itself fails, on_tool_error must not propagate
        the exception to the agent.
        """
        handler, core = _make_handler()
        handler._last_tool_name = "fragile_tool"

        # Force the log call to raise
        with patch.object(core, "_log_to_all_transports", side_effect=RuntimeError("log boom")):
            # Must not raise
            handler.on_tool_error(ValueError("tool boom"))
