"""
Core module integrating identity, policy engine, and ledger.

This module provides the enhanced HashedClient with the @guard decorator
that integrates identity verification, policy validation, and automatic
audit logging.
"""

import asyncio
import functools
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from hashed.config import HashedConfig
from hashed.guard import PermissionError, PolicyEngine
from hashed.identity import IdentityManager
from hashed.ledger import AsyncLedger

logger = logging.getLogger(__name__)


class HashedCore:
    """
    Core client integrating identity, policies, and ledger.

    This class brings together all the security and auditing components
    to provide a comprehensive solution for secure operations.

    Example:
        >>> core = HashedCore(ledger_endpoint="https://api.example.com/logs")
        >>> await core.initialize()
        >>> core.policy_engine.add_policy("transfer", max_amount=1000.0)
        >>> 
        >>> @core.guard("transfer")
        >>> async def transfer(amount: float, to: str):
        ...     # Transfer logic here
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
        """
        Initialize the core client.

        Args:
            config: Optional configuration
            ledger_endpoint: Endpoint for the audit ledger (deprecated, use config.backend_url)
            identity: Optional existing identity manager
            agent_name: Name of the agent (for auto-registration)
            agent_type: Type of agent (e.g., 'customer_service', 'data_analysis')
        """
        self._config = config or HashedConfig()
        self._identity = identity or IdentityManager()
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

    @property
    def identity(self) -> IdentityManager:
        """Get the identity manager."""
        return self._identity

    @property
    def policy_engine(self) -> PolicyEngine:
        """Get the policy engine."""
        return self._policy_engine

    @property
    def ledger(self) -> Optional[AsyncLedger]:
        """Get the ledger (if initialized)."""
        return self._ledger

    async def initialize(self) -> None:
        """
        Initialize the core components.

        This performs:
        1. Registers agent with backend (if backend_url configured)
        2. Syncs policies from backend
        3. Starts the ledger
        4. Starts background policy sync (if enabled)

        Example:
            >>> core = HashedCore(config=config, agent_name="MyAgent")
            >>> await core.initialize()
        """
        if self._initialized:
            logger.warning("Core already initialized")
            return

        # Initialize HTTP client
        if self._config.backend_url:
            self._http_client = httpx.AsyncClient(
                base_url=self._config.backend_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers={
                    "X-API-KEY": self._config.api_key or "",
                    "Content-Type": "application/json",
                }
            )
            
            # Auto-register agent
            is_new_agent = False
            try:
                is_new_agent = await self._register_agent()
                if is_new_agent:
                    logger.info(f"Agent '{self._agent_name}' registered for the first time")
                else:
                    logger.info(f"Agent '{self._agent_name}' already registered")
            except Exception as e:
                logger.warning(f"Agent registration failed: {e}")

            # On first run: push local JSON policies to backend automatically
            # so the user doesn't need to stop → push → restart the agent.
            if is_new_agent:
                try:
                    pushed = await self._push_local_json_policies()
                    if pushed > 0:
                        logger.info(
                            f"First-run auto-push: {pushed} policies uploaded to backend"
                        )
                except Exception as e:
                    logger.warning(f"First-run policy push failed (non-fatal): {e}")

            # Initial policy sync (backend → in-memory PolicyEngine)
            try:
                await self.sync_policies_from_backend()
                logger.info("Initial policy sync completed")
            except Exception as e:
                logger.warning(f"Initial policy sync failed: {e}")
            
            # Start background sync
            if self._config.enable_auto_sync:
                self._sync_task = asyncio.create_task(self._background_sync())
                logger.info(f"Background policy sync started (interval: {self._config.sync_interval}s)")

        # Start ledger
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
        """
        Shutdown the core components.

        This stops the ledger, background tasks, and cleans up resources.

        Example:
            >>> await core.shutdown()
        """
        if not self._initialized:
            return

        # Stop background sync
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            logger.info("Background sync stopped")

        # Stop ledger
        if self._ledger:
            await self._ledger.stop()
            logger.info("Ledger stopped")

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            logger.info("HTTP client closed")

        self._initialized = False
        logger.info("HashedCore shutdown")

    def guard(
        self,
        tool_name: str,
        amount_param: Optional[str] = "amount",
        raise_on_deny: bool = False,
    ) -> Callable:
        """
        Decorator that guards a function with identity, policy, and logging.

        This decorator:
        1. Validates the operation against local + backend policies
        2. Signs the operation with the identity
        3. Executes the function if allowed
        4. Logs the operation (success OR denial) to the audit trail
        5. On denial: returns a human-readable string by default so that
           LangChain/CrewAI/AutoGen agents can respond gracefully, or
           raises PermissionError if raise_on_deny=True.

        Args:
            tool_name: Name of the tool/operation
            amount_param: Name of the parameter containing the amount value
            raise_on_deny: If True, raise PermissionError on policy denial
                           (for non-agent code). Default False returns a
                           denial string so framework agents don't crash.

        Returns:
            Decorator function

        Example:
            >>> @core.guard("transfer")           # returns string on deny (safe for agents)
            >>> @core.guard("transfer", raise_on_deny=True)  # raises PermissionError
            >>> async def transfer(amount: float, to: str):
            ...     return {"status": "success"}
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract amount if specified
                amount = kwargs.get(amount_param) if amount_param else None

                # Create operation context
                context = {
                    "args": args,
                    "kwargs": kwargs,
                    "public_key": self._identity.public_key_hex,
                }

                try:
                    # 1. Validate against LOCAL policy first
                    self._policy_engine.validate(
                        tool_name=tool_name, amount=amount, **context
                    )
                    logger.debug(f"Local policy validation passed for '{tool_name}'")
                    
                    # 2. Validate against BACKEND policy (if connected)
                    if self._http_client:
                        try:
                            # Sign the guard request so the backend can verify
                            # this request comes from the legitimate agent.
                            _guard_canonical = {
                                "operation": tool_name,
                                "agent_public_key": self._identity.public_key_hex,
                            }
                            _guard_signed = self._identity.sign_data(_guard_canonical)

                            guard_response = await self._http_client.post(
                                "/guard",
                                json={
                                    "operation": tool_name,
                                    "agent_public_key": self._identity.public_key_hex,
                                    "signature": _guard_signed.get("signature"),
                                    "data": {
                                        "amount": amount,
                                        **{k: str(v) for k, v in kwargs.items()}
                                    }
                                }
                            )
                            
                            if guard_response.is_success:
                                guard_result = guard_response.json()
                                if not guard_result.get("allowed", False):
                                    raise PermissionError(
                                        f"Operation '{tool_name}' is not allowed by backend policy",
                                        details={
                                            "tool_name": tool_name,
                                            "policy": guard_result.get("policy"),
                                            "message": guard_result.get("message")
                                        }
                                    )
                                logger.debug(f"Backend policy validation passed for '{tool_name}'")
                            else:
                                logger.warning(f"Backend guard check failed: {guard_response.status_code}")
                        except PermissionError:
                            raise
                        except Exception as e:
                            logger.warning(f"Backend guard check error (continuing): {e}")

                    # 3. Sign the operation
                    signed_operation = self._identity.sign_data(
                        {
                            "tool_name": tool_name,
                            "amount": amount,
                            "kwargs": {k: str(v) for k, v in kwargs.items()},
                        }
                    )

                    # 4. Execute the function
                    result = await func(*args, **kwargs)

                    # 5. Log successful operation (backend OR local ledger, not both)
                    logged = False
                    
                    # Prefer backend logging if available
                    if self._http_client:
                        try:
                            await self._http_client.post(
                                "/log",
                                json={
                                    "operation": tool_name,
                                    "agent_public_key": self._identity.public_key_hex,
                                    "status": "success",
                                    "data": {
                                        "tool_name": tool_name,
                                        "amount": amount,
                                        "result": str(result)[:200],
                                    },
                                    "metadata": {
                                        "signature": signed_operation["signature"],
                                    }
                                }
                            )
                            logger.debug(f"Operation '{tool_name}' logged to backend")
                            logged = True
                        except Exception as e:
                            logger.warning(f"Failed to log to backend: {e}")
                    
                    # Fallback to local ledger only if backend logging failed
                    if not logged and self._ledger:
                        await self._ledger.log(
                            event_type=f"{tool_name}.success",
                            data={
                                "tool_name": tool_name,
                                "amount": amount,
                                "result": str(result)[:200],
                            },
                            metadata={
                                "signature": signed_operation["signature"],
                                "public_key": signed_operation["public_key"],
                            },
                        )
                        logger.debug(f"Operation '{tool_name}' logged to local ledger")

                    return result

                except PermissionError as e:
                    # ── Audit log the denial ──────────────────────────────
                    # 1. Log to backend (appears in dashboard)
                    if self._http_client:
                        try:
                            await self._http_client.post(
                                "/log",
                                json={
                                    "operation": tool_name,
                                    "agent_public_key": self._identity.public_key_hex,
                                    "status": "denied",
                                    "data": {
                                        "tool_name": tool_name,
                                        "amount": amount,
                                        "reason": str(e),
                                    },
                                    "metadata": {
                                        "policy": "denied",
                                    },
                                },
                            )
                            logger.debug(f"Denial for '{tool_name}' logged to backend")
                        except Exception as log_err:
                            logger.warning(f"Failed to log denial to backend: {log_err}")

                    # 2. Fallback to local ledger
                    if self._ledger:
                        try:
                            await self._ledger.log(
                                event_type=f"{tool_name}.permission_denied",
                                data={
                                    "tool_name": tool_name,
                                    "amount": amount,
                                    "error": str(e),
                                },
                                metadata={
                                    "public_key": self._identity.public_key_hex,
                                    "details": getattr(e, "details", {}),
                                },
                            )
                        except Exception:
                            pass

                    logger.warning(f"Permission denied for '{tool_name}': {e}")

                    # ── Return or raise based on raise_on_deny ────────────
                    if raise_on_deny:
                        raise
                    # Default: return human-readable string so LangChain/CrewAI
                    # agents can explain the denial to the user instead of crashing.
                    return (
                        f"[HASHED BLOCKED] Permission denied for '{tool_name}': "
                        f"This operation is not allowed by the agent's governance policies. "
                        f"Inform the user you cannot perform this action."
                    )

                except Exception as e:
                    # Log unexpected errors to ledger
                    if self._ledger:
                        await self._ledger.log(
                            event_type=f"{tool_name}.error",
                            data={
                                "tool_name": tool_name,
                                "amount": amount,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                            metadata={
                                "public_key": self._identity.public_key_hex,
                            },
                        )

                    logger.error(f"Error in '{tool_name}': {e}", exc_info=True)
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # For sync functions, run in event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                return loop.run_until_complete(async_wrapper(*args, **kwargs))

            # Return async wrapper if function is async, else sync wrapper
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    async def __aenter__(self) -> "HashedCore":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()

    async def _register_agent(self) -> bool:
        """
        Register agent with the backend.

        Returns:
            True if the agent was newly registered (first time),
            False if it already existed (409 Conflict).

        Raises:
            Exception: If registration fails for an unexpected reason.
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
                # Agent already existed — not a first run
                logger.info(f"Agent already registered: {self._agent_name}")
                self._agent_registered = True
                return False
            elif response.is_success:
                # Freshly created — first run!
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
        Read .hashed_policies.json and push all policies to the backend.

        Called automatically on first run (newly registered agent) so that
        policies defined before the first launch are visible immediately in
        the dashboard without requiring a separate 'hashed policy push'.

        Returns:
            Number of policies successfully pushed.
        """
        if not self._http_client:
            return 0

        # Locate .hashed_policies.json — search CWD and parent dirs
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

        # Normalize flat vs structured format
        if "global" not in raw and "agents" not in raw:
            raw = {"global": raw, "agents": {}}

        global_pols: dict = raw.get("global", {})
        agents_pols: dict = raw.get("agents", {})

        # Find our agent's ID from the backend (needed for agent-scoped policies)
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

        # Helper to convert "My Agent Name" → "my_agent_name"
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
                    logger.debug(f"Auto-pushed policy '{tool_name}' (agent_id={agent_id})")
                else:
                    logger.warning(
                        f"Auto-push failed for '{tool_name}': {resp.status_code}"
                    )
            except Exception as exc:
                logger.warning(f"Error auto-pushing policy '{tool_name}': {exc}")

        # Push global policies
        for tool_name, pol in global_pols.items():
            await _upsert(tool_name, pol, agent_id=None)

        # Push this agent's specific policies (matched by snake_case name)
        if our_agent_id and agent_snake in agents_pols:
            for tool_name, pol in agents_pols[agent_snake].items():
                await _upsert(tool_name, pol, agent_id=our_agent_id)

        return pushed

    async def push_policies_to_backend(self) -> None:
        """
        Push local policies to the backend.
        
        Uploads all local policies to the backend database so they're
        visible in the dashboard.
        
        Raises:
            Exception: If push fails
        """
        if not self._http_client:
            logger.warning("HTTP client not initialized, skipping policy push")
            return
        
        try:
            # First, get the agent_id from the backend using our public key
            agent_response = await self._http_client.get("/v1/agents")
            if not agent_response.is_success:
                raise Exception(f"Failed to get agent info: {agent_response.status_code}")
            
            agents_data = agent_response.json()
            agents = agents_data.get("agents", [])
            
            # Find our agent by public key
            our_agent = next(
                (agent for agent in agents if agent["public_key"] == self._identity.public_key_hex),
                None
            )
            
            if not our_agent:
                logger.error("Agent not found in backend, cannot push policies")
                return
            
            agent_id = our_agent["id"]
            logger.debug(f"Found agent_id: {agent_id}")
            
            # Get all local policies
            local_policies = self._policy_engine._policies
            
            if not local_policies:
                logger.info("No local policies to push")
                return
            
            # Push each policy to backend with agent_id
            pushed_count = 0
            for tool_name, policy in local_policies.items():
                try:
                    response = await self._http_client.post(
                        "/v1/policies",
                        params={"agent_id": agent_id},  # Send agent_id as query param
                        json={
                            "tool_name": tool_name,
                            "allowed": policy.allowed,
                            "max_amount": policy.max_amount,
                            "requires_approval": policy.metadata.get("requires_approval", False),
                            "metadata": policy.metadata,
                        }
                    )
                    
                    if response.is_success or response.status_code == 409:  # 409 = already exists
                        pushed_count += 1
                        logger.debug(f"Policy '{tool_name}' pushed to backend")
                    else:
                        logger.warning(f"Failed to push policy '{tool_name}': {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"Error pushing policy '{tool_name}': {e}")
                    continue
            
            logger.info(f"Pushed {pushed_count}/{len(local_policies)} policies to backend")
            
        except Exception as e:
            logger.error(f"Failed to push policies: {e}")
            raise

    async def sync_policies_from_backend(self) -> None:
        """
        Sync policies from the backend.
        
        Downloads current policies and updates the local PolicyEngine.
        
        Raises:
            Exception: If sync fails
        """
        if not self._http_client:
            logger.warning("HTTP client not initialized, skipping policy sync")
            return
        
        try:
            response = await self._http_client.get(
                "/v1/policies/sync",
                params={"agent_public_key": self._identity.public_key_hex}
            )
            
            if not response.is_success:
                raise Exception(f"Policy sync failed: {response.status_code} - {response.text}")
            
            data = response.json()
            policies = data.get("policies", {})
            
            # Clear existing policies and load new ones
            # Note: This is a simple implementation. In production, you might want
            # to merge policies more intelligently.
            for tool_name, policy_data in policies.items():
                self._policy_engine.add_policy(
                    tool_name=tool_name,
                    max_amount=policy_data.get("max_amount"),
                    allowed=policy_data.get("allowed", True),
                    **{k: v for k, v in policy_data.items() 
                       if k not in ["max_amount", "allowed"]}
                )
            
            logger.info(f"Synced {len(policies)} policies from backend")
            logger.debug(f"Sync metadata: {data.get('synced_at')}")
        
        except Exception as e:
            logger.error(f"Failed to sync policies: {e}")
            raise

    async def _background_sync(self) -> None:
        """
        Background task that periodically syncs policies.
        
        Runs until cancelled or core is shutdown.
        """
        logger.debug("Background policy sync task started")
        
        while self._initialized:
            try:
                await asyncio.sleep(self._config.sync_interval)
                
                if not self._initialized:
                    break
                
                logger.debug("Running scheduled policy sync...")
                await self.sync_policies_from_backend()
                
            except asyncio.CancelledError:
                logger.debug("Background sync cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background sync: {e}")
                # Continue running even if sync fails
                continue


# Convenience function to create a configured core instance
def create_core(
    ledger_endpoint: Optional[str] = None,
    config: Optional[HashedConfig] = None,
    policies: Optional[dict] = None,
) -> HashedCore:
    """
    Create and configure a HashedCore instance.

    Args:
        ledger_endpoint: Optional ledger endpoint
        config: Optional configuration
        policies: Optional dict of policies to add

    Returns:
        Configured HashedCore instance

    Example:
        >>> core = create_core(
        ...     ledger_endpoint="https://api.example.com/logs",
        ...     policies={
        ...         "transfer": {"max_amount": 1000.0, "allowed": True},
        ...         "delete": {"allowed": False},
        ...     }
        ... )
        >>> await core.initialize()
    """
    core = HashedCore(config=config, ledger_endpoint=ledger_endpoint)

    if policies:
        core.policy_engine.bulk_add_policies(policies)

    return core
