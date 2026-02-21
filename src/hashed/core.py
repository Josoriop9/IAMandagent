"""
Core module integrating identity, policy engine, and ledger.

This module provides the enhanced HashedClient with the @guard decorator
that integrates identity verification, policy validation, and automatic
audit logging.
"""

import asyncio
import functools
import logging
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
            try:
                await self._register_agent()
                logger.info(f"Agent '{self._agent_name}' registered successfully")
            except Exception as e:
                logger.warning(f"Agent registration failed: {e}")
            
            # Initial policy sync
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
        self, tool_name: str, amount_param: Optional[str] = "amount"
    ) -> Callable:
        """
        Decorator that guards a function with identity, policy, and logging.

        This decorator:
        1. Signs the operation with the identity
        2. Validates the operation against policies
        3. Executes the function if allowed
        4. Logs the operation to the ledger
        5. Handles PermissionError if policy is violated

        Args:
            tool_name: Name of the tool/operation
            amount_param: Name of the parameter containing the amount value

        Returns:
            Decorator function

        Raises:
            PermissionError: If the operation violates a policy

        Example:
            >>> @core.guard("transfer", amount_param="amount")
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
                    # 1. Validate against policy
                    self._policy_engine.validate(
                        tool_name=tool_name, amount=amount, **context
                    )
                    logger.debug(f"Policy validation passed for '{tool_name}'")

                    # 2. Sign the operation
                    signed_operation = self._identity.sign_data(
                        {
                            "tool_name": tool_name,
                            "amount": amount,
                            "kwargs": {k: str(v) for k, v in kwargs.items()},
                        }
                    )

                    # 3. Execute the function
                    result = await func(*args, **kwargs)

                    # 4. Log successful operation to ledger
                    if self._ledger:
                        await self._ledger.log(
                            event_type=f"{tool_name}.success",
                            data={
                                "tool_name": tool_name,
                                "amount": amount,
                                "result": str(result)[:200],  # Truncate long results
                            },
                            metadata={
                                "signature": signed_operation["signature"],
                                "public_key": signed_operation["public_key"],
                            },
                        )

                    return result

                except PermissionError as e:
                    # Log permission error to ledger
                    if self._ledger:
                        await self._ledger.log(
                            event_type=f"{tool_name}.permission_denied",
                            data={
                                "tool_name": tool_name,
                                "amount": amount,
                                "error": str(e),
                            },
                            metadata={
                                "public_key": self._identity.public_key_hex,
                                "details": e.details,
                            },
                        )

                    logger.error(f"Permission denied for '{tool_name}': {e}")
                    raise

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

    async def _register_agent(self) -> None:
        """
        Register agent with the backend.
        
        Raises:
            Exception: If registration fails
        """
        if not self._http_client or self._agent_registered:
            return
        
        try:
            response = await self._http_client.post(
                "/v1/agents/register",
                json={
                    "name": self._agent_name,
                    "public_key": self._identity.public_key_hex,
                    "agent_type": self._agent_type,
                    "description": f"Auto-registered {self._agent_type} agent"
                }
            )
            
            if response.status_code == 409:
                # Agent already exists, that's OK
                logger.info(f"Agent already registered: {self._agent_name}")
                self._agent_registered = True
            elif response.is_success:
                self._agent_registered = True
                logger.debug(f"Agent registered: {response.json()}")
            else:
                raise Exception(f"Registration failed: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
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
