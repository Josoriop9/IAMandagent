"""
Core module integrating identity, policy engine, and ledger.

Refactored for Principal-Engineer quality (Sprint 7):
  - SRP: guard() decomposed into focused private helpers
  - Circuit Breaker: protects backend calls from cascading failures
  - Performance tracking: DEBUG log of governance overhead per call
  - Async/sync interop: safe in FastAPI / Jupyter (no RuntimeError)
  - Exponential backoff: background sync respects failing backends
  - Encapsulation: all internal state private; public via @property
"""

import asyncio
import concurrent.futures
import functools
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from hashed.config import HashedConfig
from hashed.guard import PermissionError, PolicyEngine
from hashed.identity import IdentityManager
from hashed.ledger import AsyncLedger

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Circuit Breaker
# ──────────────────────────────────────────────────────────────────────────────

class _CircuitBreaker:
    """
    Simple state-machine circuit breaker for backend HTTP calls.

    States:
      Closed  → normal operation, failures tracked
      Open    → backend assumed down; HTTP calls skipped for ``cooldown_s``
      (Half-Open is implicit: first call after cooldown probes the backend)

    Args:
        failure_threshold: Consecutive failures before opening. Default 3.
        cooldown_s: Seconds to stay open before auto-reset. Default 60.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_s: float = 60.0) -> None:
        self._failures = 0
        self._threshold = failure_threshold
        self._cooldown = cooldown_s
        self._opened_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """True if the circuit is open (backend calls should be skipped)."""
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._cooldown:
            # Auto-reset: transition Open → Closed (half-open probe)
            self._failures = 0
            self._opened_at = None
            logger.info("Circuit breaker CLOSED (cooldown elapsed — probing backend)")
            return False
        return True

    def record_success(self) -> None:
        """Reset failure count on a successful backend call."""
        if self._failures > 0:
            logger.debug("Circuit breaker: success recorded, failure counter reset")
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Increment failure count; open circuit if threshold reached."""
        self._failures += 1
        if self._failures >= self._threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning(
                f"Circuit breaker OPEN after {self._failures} consecutive failures "
                f"(cooldown: {self._cooldown}s)"
            )


# ──────────────────────────────────────────────────────────────────────────────
# HashedCore
# ──────────────────────────────────────────────────────────────────────────────

class HashedCore:
    """
    Core client integrating identity, policies, and ledger.

    This class orchestrates all security and auditing components to provide
    a comprehensive governance layer for AI agent operations.

    Example:
        >>> core = HashedCore(config=config, agent_name="MyAgent")
        >>> await core.initialize()
        >>> core.policy_engine.add_policy("transfer", max_amount=1000.0)
        >>>
        >>> @core.guard("transfer")
        >>> async def transfer(amount: float, to: str):
        ...     return {"status": "success", "amount": amount, "to": to}
    """

    def __init__(
        self,
        config: Optional[HashedConfig] = None,
        ledger_endpoint: Optional[str] = None,
        identity: Optional[IdentityManager] = None,
        agent_name: Optional[str] = None,
        agent_type: str = "general",
    ) -> None:
        self._config = config or HashedConfig()

        # Identity resolution (priority: explicit > env var > ephemeral)
        if identity is not None:
            self._identity = identity
        else:
            from hashed.identity_store import load_identity_from_env
            _env_identity = load_identity_from_env()
            self._identity = _env_identity if _env_identity is not None else IdentityManager()

        self._policy_engine = PolicyEngine()
        self._ledger: Optional[AsyncLedger] = None
        self._ledger_endpoint = ledger_endpoint or (
            f"{self._config.backend_url}{self._config.ledger_endpoint}"
            if self._config.backend_url else None
        )
        self._agent_name = agent_name or "Unnamed Agent"
        self._agent_type = agent_type
        self._initialized = False
        self._sync_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._agent_registered = False
        self._circuit_breaker = _CircuitBreaker(
            failure_threshold=3,
            cooldown_s=60.0,
        )

    # ── Public properties ────────────────────────────────────────────────────

    @property
    def identity(self) -> IdentityManager:
        """Agent's Ed25519 identity manager."""
        return self._identity

    @property
    def policy_engine(self) -> PolicyEngine:
        """Local policy engine (validate + manage policies)."""
        return self._policy_engine

    @property
    def ledger(self) -> Optional[AsyncLedger]:
        """Async audit ledger (None until initialized)."""
        return self._ledger

    @property
    def circuit_breaker(self) -> _CircuitBreaker:
        """Circuit breaker protecting backend HTTP calls."""
        return self._circuit_breaker

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Initialize all core components.

        Steps:
        1. Register agent with backend (if backend_url configured)
        2. Auto-push local JSON policies on first run
        3. Sync policies from backend
        4. Start background policy sync (if enabled)
        5. Start the audit ledger
        """
        if self._initialized:
            logger.warning("Core already initialized")
            return

        if self._config.backend_url:
            self._http_client = httpx.AsyncClient(
                base_url=self._config.backend_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers={
                    "X-API-KEY": self._config.api_key or "",
                    "Content-Type": "application/json",
                },
            )

            is_new_agent = False
            try:
                is_new_agent = await self._register_agent()
                logger.info(
                    f"Agent '{self._agent_name}' "
                    f"{'registered for the first time' if is_new_agent else 'already registered'}"
                )
            except Exception as e:
                logger.warning(f"Agent registration failed: {e}")

            if is_new_agent:
                try:
                    pushed = await self._push_local_json_policies()
                    if pushed > 0:
                        logger.info(f"First-run auto-push: {pushed} policies uploaded to backend")
                except Exception as e:
                    logger.warning(f"First-run policy push failed (non-fatal): {e}")

            try:
                await self.sync_policies_from_backend()
                logger.info("Initial policy sync completed")
            except Exception as e:
                logger.warning(f"Initial policy sync failed: {e}")

            if self._config.enable_auto_sync:
                self._sync_task = asyncio.create_task(self._background_sync())
                logger.info(f"Background policy sync started (interval: {self._config.sync_interval}s)")

        if self._ledger_endpoint:
            self._ledger = AsyncLedger(
                endpoint=self._ledger_endpoint,
                config=self._config,
                agent_public_key=self._identity.public_key_hex,
                api_key=self._config.api_key,
            )
            await self._ledger.start()
            logger.info("Ledger initialized and started")

        self._initialized = True
        logger.info("HashedCore initialized")

    async def shutdown(self) -> None:
        """Gracefully stop background tasks, ledger, and HTTP client."""
        if not self._initialized:
            return

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            logger.info("Background sync stopped")

        if self._ledger:
            await self._ledger.stop()
            logger.info("Ledger stopped")

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            logger.info("HTTP client closed")

        self._initialized = False
        logger.info("HashedCore shutdown")

    # ── @guard decorator ─────────────────────────────────────────────────────

    def guard(
        self,
        tool_name: str,
        amount_param: Optional[str] = "amount",
        raise_on_deny: bool = False,
    ) -> Callable:
        """
        Decorator that governs a function with identity, policy, and logging.

        Governance pipeline (each step is a focused private method):
          1. ``_validate_local_policy``  — fast local check
          2. ``_execute_remote_guard``   — backend check w/ circuit breaker
          3. Sign the operation (Ed25519)
          4. Execute the wrapped function
          5. ``_log_to_all_transports``  — backend → local ledger fallback

        On denial: returns a human-readable string by default so that
        LangChain/CrewAI/AutoGen agents respond gracefully, or raises
        ``PermissionError`` when ``raise_on_deny=True``.

        Args:
            tool_name: Logical name for the operation (used in policy + logs).
            amount_param: kwarg name holding the numeric amount (for max_amount policies).
            raise_on_deny: Raise ``PermissionError`` on denial (default: return string).
        """

        def decorator(func: Callable) -> Callable:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                amount = kwargs.get(amount_param) if amount_param else None
                context = {
                    "args": args,
                    "kwargs": kwargs,
                    "public_key": self._identity.public_key_hex,
                }
                t0 = time.perf_counter()

                try:
                    # ── Step 1: local policy ─────────────────────────────
                    self._validate_local_policy(tool_name, amount, context)

                    # ── Step 2: remote guard (circuit-breaker protected) ─
                    await self._execute_remote_guard(tool_name, amount, kwargs)

                    # ── Step 3: sign the operation (SPEC §2.1 canonical) ─
                    signed = self._identity.sign_operation(
                        operation=tool_name,
                        amount=amount,
                        context={"kwargs": {k: str(v) for k, v in kwargs.items()}},
                        status="allowed",
                    )

                    # ── Step 4: execute function (async or sync) ─────────
                    result = func(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result

                    # ── Step 5: audit log (success) ──────────────────────
                    await self._log_to_all_transports(
                        tool_name, "success", amount, result, signed
                    )

                    overhead_ms = (time.perf_counter() - t0) * 1000
                    logger.debug(
                        f"[hashed] '{tool_name}' governance overhead: {overhead_ms:.1f}ms"
                    )

                    return result

                except PermissionError as e:
                    await self._log_denial(tool_name, amount, e)
                    logger.warning(f"Permission denied for '{tool_name}': {e}")

                    if raise_on_deny:
                        raise
                    return (
                        f"[HASHED BLOCKED] Permission denied for '{tool_name}': "
                        f"This operation is not allowed by the agent's governance policies. "
                        f"Inform the user you cannot perform this action."
                    )

                except Exception as e:
                    await self._log_error(tool_name, amount, e)
                    logger.error(f"Error in '{tool_name}': {e}", exc_info=True)
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                """
                Sync shim that is safe in running-loop environments
                (FastAPI, Jupyter, etc.) via a background thread.
                """
                try:
                    asyncio.get_running_loop()
                    # A loop is already running — dispatch to a dedicated thread
                    # to avoid RuntimeError: "This event loop is already running."
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(asyncio.run, async_wrapper(*args, **kwargs))
                        return future.result()
                except RuntimeError:
                    # No running loop — safe to call asyncio.run directly
                    return asyncio.run(async_wrapper(*args, **kwargs))

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    # ── Context manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "HashedCore":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    # ── Private guard helpers (SRP) ──────────────────────────────────────────

    def _validate_local_policy(
        self, tool_name: str, amount: Any, context: dict
    ) -> None:
        """
        Validate operation against the in-memory PolicyEngine.

        Raises:
            PermissionError: If the local policy denies the operation.
        """
        self._policy_engine.validate(tool_name=tool_name, amount=amount, **context)
        logger.debug(f"Local policy validation passed for '{tool_name}'")

    async def _execute_remote_guard(
        self, tool_name: str, amount: Any, kwargs: dict
    ) -> None:
        """
        Call the backend ``/guard`` endpoint.

        Respects the circuit breaker:
          - Circuit OPEN + fail_closed → raises PermissionError
          - Circuit OPEN + fail_open   → skips HTTP call (continues)
          - Circuit CLOSED             → normal HTTP call

        Records success/failure on the circuit breaker accordingly.

        Raises:
            PermissionError: If backend denies the operation or circuit is open
                             in fail_closed mode.
        """
        if not self._http_client:
            return

        if self._circuit_breaker.is_open:
            if self._config.fail_closed:
                raise PermissionError(
                    f"Operation '{tool_name}' blocked: circuit breaker OPEN "
                    f"(backend unavailable). "
                    f"Set HASHED_FAIL_CLOSED=false to allow offline execution.",
                    details={
                        "tool_name": tool_name,
                        "reason": "circuit_open",
                        "fail_closed": True,
                    },
                )
            logger.debug(
                f"Circuit breaker OPEN — skipping backend guard for '{tool_name}'"
            )
            return

        try:
            _guard_signed = self._identity.sign_operation(
                operation=tool_name,
                amount=amount,
                context={"kwargs": {k: str(v) for k, v in kwargs.items()}},
                status="pending",
            )

            response = await self._http_client.post(
                "/guard",
                json={
                    "operation": tool_name,
                    "agent_public_key": self._identity.public_key_hex,
                    "signature": _guard_signed["signature"],
                    "nonce": _guard_signed["payload"]["nonce"],
                    "timestamp_ns": _guard_signed["payload"]["timestamp_ns"],
                    "canonical": _guard_signed["canonical"],
                    "data": {
                        "amount": amount,
                        **{k: str(v) for k, v in kwargs.items()},
                    },
                },
            )

            if response.is_success:
                self._circuit_breaker.record_success()
                guard_result = response.json()
                if not guard_result.get("allowed", False):
                    raise PermissionError(
                        f"Operation '{tool_name}' denied by backend policy",
                        details={
                            "tool_name": tool_name,
                            "policy": guard_result.get("policy"),
                            "message": guard_result.get("message"),
                        },
                    )
                logger.debug(f"Backend policy validation passed for '{tool_name}'")
            else:
                self._circuit_breaker.record_failure()
                logger.warning(
                    f"Backend guard returned {response.status_code} for '{tool_name}'"
                )

        except PermissionError:
            raise
        except Exception as e:
            self._circuit_breaker.record_failure()
            if self._config.fail_closed:
                raise PermissionError(
                    f"Operation '{tool_name}' blocked: backend unreachable "
                    f"in fail-closed mode. "
                    f"Set HASHED_FAIL_CLOSED=false to allow offline execution.",
                    details={
                        "tool_name": tool_name,
                        "reason": "backend_unreachable",
                        "fail_closed": True,
                        "error": str(e),
                    },
                )
            logger.warning(f"Backend guard check error (continuing): {e}")

    async def _log_to_all_transports(
        self,
        tool_name: str,
        status: str,
        amount: Any,
        result_or_str: Any,
        signed: dict,
    ) -> None:
        """
        Emit an audit log entry to backend (preferred) or local ledger (fallback).

        Only one transport is used per call:
          - Backend HTTP POST → local ledger fallback if backend fails.

        Args:
            tool_name: Operation name.
            status: "success" | "denied" | "error".
            amount: Numeric amount involved (may be None).
            result_or_str: Result object or error string (truncated to 200 chars).
            signed: Full dict from IdentityManager.sign_operation() containing
                    ``payload``, ``canonical``, ``signature``, ``public_key``.
        """
        logged = False
        _sig = signed.get("signature", "") if isinstance(signed, dict) else ""
        _payload = signed.get("payload", {}) if isinstance(signed, dict) else {}
        _canonical = signed.get("canonical", "") if isinstance(signed, dict) else ""

        if self._http_client:
            try:
                await self._http_client.post(
                    "/log",
                    json={
                        "operation": tool_name,
                        "agent_public_key": self._identity.public_key_hex,
                        "status": status,
                        "data": {
                            "tool_name": tool_name,
                            "amount": amount,
                            "result": str(result_or_str)[:200],
                        },
                        "metadata": {
                            "signature": _sig,
                            "nonce": _payload.get("nonce"),
                            "timestamp_ns": _payload.get("timestamp_ns"),
                            "version": _payload.get("version", 1),
                        },
                    },
                )
                logger.debug(f"Operation '{tool_name}' ({status}) logged to backend")
                logged = True
            except Exception as e:
                logger.warning(
                    f"Failed to log '{tool_name}' ({status}) to backend: {e}"
                )

        if not logged and self._ledger:
            try:
                await self._ledger.log(
                    event_type=f"{tool_name}.{status}",
                    data={
                        "tool_name": tool_name,
                        "amount": amount,
                        "result": str(result_or_str)[:200],
                    },
                    metadata={
                        "signature": _sig,
                        "public_key": self._identity.public_key_hex,
                        "nonce": _payload.get("nonce"),
                        "timestamp_ns": _payload.get("timestamp_ns"),
                        "canonical": _canonical,
                        "version": _payload.get("version", 1),
                    },
                )
                logger.debug(
                    f"Operation '{tool_name}' ({status}) logged to local ledger"
                )
            except Exception as e:
                logger.warning(f"Failed to log '{tool_name}' to local ledger: {e}")

    async def _log_denial(
        self, tool_name: str, amount: Any, error: PermissionError
    ) -> None:
        """Log a policy denial to all transports with a canonical signed envelope."""
        signed = self._identity.sign_operation(
            operation=tool_name,
            amount=amount,
            context={"error": str(error)},
            status="denied",
        )
        await self._log_to_all_transports(
            tool_name, "denied", amount, str(error), signed
        )

    async def _log_error(
        self, tool_name: str, amount: Any, error: Exception
    ) -> None:
        """Log an unexpected error to the local ledger with a canonical signed envelope."""
        if self._ledger:
            try:
                signed = self._identity.sign_operation(
                    operation=tool_name,
                    amount=amount,
                    context={
                        "error": str(error),
                        "error_type": type(error).__name__,
                    },
                    status="error",
                )
                await self._ledger.log(
                    event_type=f"{tool_name}.error",
                    data={
                        "tool_name": tool_name,
                        "amount": amount,
                        "error": str(error),
                        "error_type": type(error).__name__,
                    },
                    metadata={
                        "signature": signed["signature"],
                        "public_key": self._identity.public_key_hex,
                        "nonce": signed["payload"]["nonce"],
                        "timestamp_ns": signed["payload"]["timestamp_ns"],
                        "canonical": signed["canonical"],
                        "version": signed["payload"]["version"],
                    },
                )
            except Exception:
                pass

    # ── Backend helpers ──────────────────────────────────────────────────────

    async def _register_agent(self) -> bool:
        """
        Register agent with the backend.

        Returns:
            True if newly registered (first run), False if already existed.
        """
        if not self._http_client or self._agent_registered:
            return False

        try:
            response = await self._http_client.post(
                "/register",
                json={
                    "name": self._agent_name,
                    "public_key": self._identity.public_key_hex,
                    "agent_type": self._agent_type,
                    "description": f"Auto-registered {self._agent_type} agent",
                },
            )

            if response.status_code == 409:
                self._agent_registered = True
                return False
            elif response.is_success:
                self._agent_registered = True
                logger.debug(f"Agent registered: {response.json()}")
                return True
            else:
                raise Exception(
                    f"Registration failed: {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            raise

    async def _push_local_json_policies(self) -> int:
        """
        Read ``.hashed_policies.json`` and push all entries to the backend.

        Called automatically on first run so dashboard reflects local policies
        without a manual ``hashed policy push``.

        Returns:
            Number of policies successfully pushed.
        """
        if not self._http_client:
            return 0

        policy_file = None
        for candidate in [
            Path(".hashed_policies.json"),
            Path("../.hashed_policies.json"),
        ]:
            if candidate.exists():
                policy_file = candidate
                break

        if not policy_file:
            logger.debug("No .hashed_policies.json found — skipping first-run push")
            return 0

        try:
            raw = json.loads(policy_file.read_text())
        except Exception as e:
            logger.warning(f"Could not read {policy_file}: {e}")
            return 0

        if "global" not in raw and "agents" not in raw:
            raw = {"global": raw, "agents": {}}

        global_pols: dict = raw.get("global", {})
        agents_pols: dict = raw.get("agents", {})

        try:
            agents_resp = await self._http_client.get("/v1/agents")
            our_agent_id: Optional[str] = None
            if agents_resp.is_success:
                for a in agents_resp.json().get("agents", []):
                    if a["public_key"] == self._identity.public_key_hex:
                        our_agent_id = a["id"]
                        break
        except Exception as e:
            logger.warning(f"Could not fetch agent list: {e}")
            our_agent_id = None

        def _snake(name: str) -> str:
            cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", name)
            return re.sub(r"\s+", "_", cleaned.strip()).lower()

        agent_snake = _snake(self._agent_name)
        pushed = 0

        async def _upsert(tool_name: str, pol: dict, agent_id: Optional[str]) -> None:
            nonlocal pushed
            params = {"agent_id": agent_id} if agent_id else {}
            try:
                resp = await self._http_client.post(
                    "/v1/policies",
                    params=params,
                    json={
                        "tool_name": tool_name,
                        "allowed": pol.get("allowed", True),
                        "max_amount": pol.get("max_amount"),
                        "metadata": {"source": "first_run_auto_push"},
                    },
                )
                if resp.is_success or resp.status_code == 409:
                    pushed += 1
            except Exception as exc:
                logger.warning(f"Error auto-pushing policy '{tool_name}': {exc}")

        for tool_name, pol in global_pols.items():
            await _upsert(tool_name, pol, agent_id=None)

        if our_agent_id and agent_snake in agents_pols:
            for tool_name, pol in agents_pols[agent_snake].items():
                await _upsert(tool_name, pol, agent_id=our_agent_id)

        return pushed

    async def push_policies_to_backend(self) -> None:
        """
        Push all local PolicyEngine policies to the backend.

        Makes local policies visible in the dashboard.
        """
        if not self._http_client:
            logger.warning("HTTP client not initialized, skipping policy push")
            return

        try:
            agent_response = await self._http_client.get("/v1/agents")
            if not agent_response.is_success:
                raise Exception(f"Failed to get agent info: {agent_response.status_code}")

            our_agent = next(
                (a for a in agent_response.json().get("agents", [])
                 if a["public_key"] == self._identity.public_key_hex),
                None,
            )

            if not our_agent:
                logger.error("Agent not found in backend, cannot push policies")
                return

            agent_id = our_agent["id"]
            local_policies = self._policy_engine._policies

            if not local_policies:
                logger.info("No local policies to push")
                return

            pushed_count = 0
            for tool_name, policy in local_policies.items():
                try:
                    response = await self._http_client.post(
                        "/v1/policies",
                        params={"agent_id": agent_id},
                        json={
                            "tool_name": tool_name,
                            "allowed": policy.allowed,
                            "max_amount": policy.max_amount,
                            "requires_approval": policy.metadata.get("requires_approval", False),
                            "metadata": policy.metadata,
                        },
                    )
                    if response.is_success or response.status_code == 409:
                        pushed_count += 1
                except Exception as e:
                    logger.warning(f"Error pushing policy '{tool_name}': {e}")

            logger.info(f"Pushed {pushed_count}/{len(local_policies)} policies to backend")

        except Exception as e:
            logger.error(f"Failed to push policies: {e}")
            raise

    async def sync_policies_from_backend(self) -> None:
        """Download current policies from backend and update local PolicyEngine."""
        if not self._http_client:
            logger.warning("HTTP client not initialized, skipping policy sync")
            return

        try:
            response = await self._http_client.get(
                "/v1/policies/sync",
                params={"agent_public_key": self._identity.public_key_hex},
            )

            if not response.is_success:
                raise Exception(
                    f"Policy sync failed: {response.status_code} - {response.text}"
                )

            data = response.json()
            policies = data.get("policies", {})

            for tool_name, policy_data in policies.items():
                self._policy_engine.add_policy(
                    tool_name=tool_name,
                    max_amount=policy_data.get("max_amount"),
                    allowed=policy_data.get("allowed", True),
                    **{k: v for k, v in policy_data.items()
                       if k not in ["max_amount", "allowed"]},
                )

            logger.info(f"Synced {len(policies)} policies from backend")

        except Exception as e:
            logger.error(f"Failed to sync policies: {e}")
            raise

    async def _background_sync(self) -> None:
        """
        Periodic policy sync with exponential backoff on failures.

        On repeated failures the sleep before each retry grows:
          10s → 20s → 40s → … up to 300s (5 min), then resets on success.
        This prevents log spam and backend hammering when the server is down.
        """
        backoff: float = 0.0
        _max_backoff: float = 300.0
        _backoff_base: float = 10.0

        logger.debug("Background policy sync task started")

        while self._initialized:
            try:
                await asyncio.sleep(self._config.sync_interval + backoff)

                if not self._initialized:
                    break

                logger.debug("Running scheduled policy sync…")
                await self.sync_policies_from_backend()
                backoff = 0.0  # reset on success

            except asyncio.CancelledError:
                logger.debug("Background sync cancelled")
                break
            except Exception as e:
                backoff = min(
                    backoff * 2 + _backoff_base if backoff > 0 else _backoff_base,
                    _max_backoff,
                )
                logger.warning(
                    f"Policy sync failed (next retry in "
                    f"{self._config.sync_interval + backoff:.0f}s): {e}"
                )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience factory
# ──────────────────────────────────────────────────────────────────────────────

def create_core(
    ledger_endpoint: Optional[str] = None,
    config: Optional[HashedConfig] = None,
    policies: Optional[dict] = None,
) -> HashedCore:
    """
    Create and optionally pre-configure a ``HashedCore`` instance.

    Args:
        ledger_endpoint: Override ledger endpoint.
        config: SDK configuration (defaults to environment variables).
        policies: Dict of ``{tool_name: {max_amount, allowed, …}}`` to
                  bulk-load into the local PolicyEngine before first use.

    Returns:
        A ``HashedCore`` instance ready for ``await core.initialize()``.

    Example:
        >>> core = create_core(
        ...     policies={
        ...         "transfer": {"max_amount": 1000.0, "allowed": True},
        ...         "delete":   {"allowed": False},
        ...     }
        ... )
        >>> await core.initialize()
    """
    core = HashedCore(config=config, ledger_endpoint=ledger_endpoint)

    if policies:
        core.policy_engine.bulk_add_policies(policies)

    return core
