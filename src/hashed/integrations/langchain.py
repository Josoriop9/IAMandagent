"""
Hashed SDK — LangChain integration.

Provides :class:`HashedCallbackHandler`, a ``BaseCallbackHandler`` that
enforces Hashed governance policies on every tool call made by a LangChain
agent.

Installation
------------
::

    pip install hashed-sdk[langchain]

Quick start
-----------
::

    from langchain.agents import AgentExecutor, create_openai_tools_agent
    from hashed import HashedCore, HashedConfig
    from hashed.integrations.langchain import HashedCallbackHandler

    core = HashedCore(config=HashedConfig(), agent_name="my-agent")
    await core.initialize()
    core.policy_engine.add_policy("send_email", allowed=True, max_amount=10)

    handler = HashedCallbackHandler(core=core)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        callbacks=[handler],
    )

What the handler does on each tool call
----------------------------------------
1. ``on_tool_start`` — validates the tool name and optional amount against
   the local ``PolicyEngine`` (synchronous, no network call).  If the policy
   denies the operation and ``raise_on_deny=True`` (default), re-raises
   :class:`hashed.guard.PermissionError` so LangChain aborts the tool call.

2. ``on_tool_end`` — logs a ``status="success"`` audit entry via
   :meth:`HashedCore._log_to_all_transports` using a canonical Ed25519-signed
   envelope (SPEC §2.1).

3. ``on_tool_error`` — logs a ``status="error"`` audit entry with the error
   string captured in the signed context.

Logging is **best-effort and non-blocking**: if an asyncio event loop is
already running the coroutine is scheduled as a background task; otherwise
``asyncio.run()`` is used.  A logging failure never propagates to the agent.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Optional, Union

from hashed.guard import PermissionError

if TYPE_CHECKING:
    from hashed.core import HashedCore

logger = logging.getLogger(__name__)

# ── Lazy LangChain import ────────────────────────────────────────────────────

try:
    from langchain_core.callbacks import BaseCallbackHandler as _Base  # type: ignore[import]
    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _Base = object  # type: ignore[assignment, misc]
    _LANGCHAIN_AVAILABLE = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_amount(input_str: Any) -> Optional[float]:
    """
    Best-effort extraction of a numeric ``amount`` from a tool's input.

    LangChain passes the tool input as a string (often JSON).  We try to
    parse it and look for an ``"amount"`` key.  Returns ``None`` on any
    parse failure so the policy check falls back to amount-agnostic mode.
    """
    if input_str is None:
        return None
    try:
        data = json.loads(input_str) if isinstance(input_str, str) else input_str
        if isinstance(data, dict):
            val = data.get("amount")
            return float(val) if val is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _schedule_log(coro: Any) -> None:
    """
    Schedule an async logging coroutine without blocking the calling thread.

    - If an event loop is running (e.g. inside an async LangChain agent),
      the coroutine is added as a background task.
    - Otherwise ``asyncio.run()`` is used to drain it synchronously.
    - Any exception in the logging path is swallowed and logged at WARNING
      level so it never propagates to the agent.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running event loop — execute synchronously
        try:
            asyncio.run(coro)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"[hashed] Async log scheduling failed: {exc}")


# ── HashedCallbackHandler ────────────────────────────────────────────────────

class HashedCallbackHandler(_Base):  # type: ignore[misc]
    """
    LangChain ``BaseCallbackHandler`` that enforces Hashed governance policies.

    Parameters
    ----------
    core:
        An initialized (or at least constructed) :class:`~hashed.core.HashedCore`
        instance.  The handler accesses ``core.policy_engine``,
        ``core.identity``, and ``core._log_to_all_transports`` directly.
    raise_on_deny:
        If ``True`` (default), a policy denial in ``on_tool_start`` raises
        :class:`~hashed.guard.PermissionError` so LangChain aborts the call.
        If ``False``, the denial is silently recorded and the tool is allowed
        to run (useful for audit-only mode).
    """

    def __init__(
        self,
        core: "HashedCore",
        raise_on_deny: bool = True,
    ) -> None:
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain integration requires `pip install hashed-sdk[langchain]`. "
                "Run: pip install hashed-sdk[langchain]"
            )
        super().__init__()
        self._core = core
        self._raise_on_deny = raise_on_deny
        self._last_tool_name: Optional[str] = None
        self._denied: set = set()

    # ── LangChain lifecycle hooks ────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict,
        input_str: Union[str, dict],
        **kwargs: Any,
    ) -> None:
        """
        Called by LangChain before a tool executes.

        Validates the operation against the local ``PolicyEngine``.  If the
        policy denies it and ``raise_on_deny=True``, re-raises
        :class:`~hashed.guard.PermissionError`.

        Parameters
        ----------
        serialized:
            LangChain tool metadata dict (contains ``"name"`` key).
        input_str:
            The tool's input, either a JSON string or a dict.
        """
        tool_name: str = serialized.get("name", "unknown_tool") if serialized else "unknown_tool"
        self._last_tool_name = tool_name
        amount = _extract_amount(input_str)

        try:
            self._core.policy_engine.validate(tool_name=tool_name, amount=amount)
            logger.debug(f"[hashed] Policy OK for tool '{tool_name}'")
        except PermissionError as e:
            self._denied.add(tool_name)
            logger.warning(f"[hashed] Policy DENIED for tool '{tool_name}': {e}")
            if self._raise_on_deny:
                raise

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """
        Called by LangChain after a tool executes successfully.

        Logs a ``status="success"`` audit entry with a canonical Ed25519
        signed envelope.
        """
        tool_name = self._last_tool_name or "unknown_tool"
        try:
            signed = self._core.identity.sign_operation(
                operation=tool_name,
                status="success",
                context={"source": "langchain_callback"},
            )
            _schedule_log(
                self._core._log_to_all_transports(
                    tool_name, "success", None, str(output)[:200], signed
                )
            )
            logger.debug(f"[hashed] Logged success for tool '{tool_name}'")
        except Exception as exc:
            logger.warning(f"[hashed] Failed to log tool success: {exc}")

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        **kwargs: Any,
    ) -> None:
        """
        Called by LangChain when a tool raises an exception.

        Logs a ``status="error"`` audit entry with the error captured in the
        signed context.
        """
        tool_name = self._last_tool_name or "unknown_tool"
        try:
            signed = self._core.identity.sign_operation(
                operation=tool_name,
                status="error",
                context={
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "source": "langchain_callback",
                },
            )
            _schedule_log(
                self._core._log_to_all_transports(
                    tool_name, "error", None, str(error)[:200], signed
                )
            )
            logger.debug(f"[hashed] Logged error for tool '{tool_name}'")
        except Exception as exc:
            logger.warning(f"[hashed] Failed to log tool error: {exc}")
