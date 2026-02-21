"""
Asynchronous ledger for non-blocking log transmission.

This module implements an async ledger that queues log entries and
sends them to a remote endpoint without blocking the main application flow.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from hashed.config import HashedConfig
from hashed.exceptions import HashedAPIError

logger = logging.getLogger(__name__)


class AsyncLedger:
    """
    Asynchronous ledger for non-blocking log transmission.

    This class uses asyncio.Queue to buffer log entries and sends them
    to a remote endpoint asynchronously without blocking the main flow.
    It follows the Producer-Consumer pattern.

    Example:
        >>> ledger = AsyncLedger(endpoint="https://api.example.com/logs")
        >>> await ledger.start()
        >>> await ledger.log("operation", {"user": "alice", "action": "transfer"})
        >>> await ledger.stop()
    """

    def __init__(
        self,
        endpoint: str,
        config: Optional[HashedConfig] = None,
        queue_size: int = 1000,
        batch_size: int = 10,
        flush_interval: float = 5.0,
        agent_public_key: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """
        Initialize the async ledger.

        Args:
            endpoint: URL endpoint to send logs to
            config: Optional HashedConfig for HTTP client settings
            queue_size: Maximum size of the internal queue
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds between automatic flushes
            agent_public_key: Agent's public key (for backend identification)
            api_key: API key for backend authentication
        """
        self._endpoint = endpoint
        self._config = config or HashedConfig()
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._pending_logs: list = []
        self._agent_public_key = agent_public_key
        self._api_key = api_key or config.api_key if config else None

    async def start(self) -> None:
        """
        Start the ledger worker.

        This starts the background task that processes the log queue.

        Example:
            >>> ledger = AsyncLedger("https://api.example.com/logs")
            >>> await ledger.start()
        """
        if self._running:
            logger.warning("Ledger is already running")
            return

        self._running = True
        
        # Build headers
        headers = {}
        if self._api_key:
            headers["X-API-KEY"] = self._api_key
        
        self._client = httpx.AsyncClient(
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
            headers=headers,
        )
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("AsyncLedger started")

    async def stop(self, flush: bool = True) -> None:
        """
        Stop the ledger worker.

        Args:
            flush: Whether to flush remaining logs before stopping

        Example:
            >>> await ledger.stop()
        """
        if not self._running:
            return

        self._running = False

        if flush:
            await self.flush()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("AsyncLedger stopped")

    async def log(
        self,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a log entry to the queue.

        This is non-blocking and returns immediately after queuing.

        Args:
            event_type: Type of event being logged
            data: Event data
            metadata: Optional metadata

        Raises:
            asyncio.QueueFull: If the queue is full

        Example:
            >>> await ledger.log("transfer", {"from": "alice", "to": "bob", "amount": 100})
        """
        if not self._running:
            logger.warning("Ledger is not running, log entry will be queued but not sent")

        log_entry = {
            "event_type": event_type,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            await self._queue.put(log_entry)
            logger.debug(f"Queued log entry: {event_type}")
        except asyncio.QueueFull:
            logger.error(f"Ledger queue is full, dropping log entry: {event_type}")
            raise

    async def flush(self) -> None:
        """
        Flush all pending logs immediately.

        This waits until the queue is empty and all logs are sent.

        Example:
            >>> await ledger.flush()
        """
        if self._pending_logs:
            await self._send_batch(self._pending_logs)
            self._pending_logs.clear()

        await self._queue.join()
        logger.debug("Ledger flushed")

    async def _worker(self) -> None:
        """
        Background worker that processes the log queue.

        This runs continuously while the ledger is active, batching
        and sending logs at regular intervals.
        """
        logger.debug("Ledger worker started")

        while self._running:
            try:
                # Try to collect a batch of logs
                timeout = self._flush_interval
                end_time = asyncio.get_event_loop().time() + timeout

                while len(self._pending_logs) < self._batch_size:
                    timeout = max(0, end_time - asyncio.get_event_loop().time())
                    if timeout <= 0:
                        break

                    try:
                        log_entry = await asyncio.wait_for(
                            self._queue.get(), timeout=timeout
                        )
                        self._pending_logs.append(log_entry)
                    except asyncio.TimeoutError:
                        break

                # Send the batch if we have logs
                if self._pending_logs:
                    await self._send_batch(self._pending_logs)
                    self._pending_logs.clear()

            except asyncio.CancelledError:
                logger.debug("Ledger worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in ledger worker: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retrying

    async def _send_batch(self, logs: list) -> None:
        """
        Send a batch of logs to the endpoint.

        Args:
            logs: List of log entries to send
        """
        if not self._client:
            logger.warning("HTTP client not initialized, skipping send")
            return

        try:
            payload = {
                "logs": logs,
                "batch_size": len(logs),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Add agent_public_key if available (for backend identification)
            if self._agent_public_key:
                payload["agent_public_key"] = self._agent_public_key

            response = await self._client.post(self._endpoint, json=payload)

            if response.is_success:
                logger.debug(f"Successfully sent {len(logs)} logs to ledger")
                # Mark tasks as done
                for _ in logs:
                    self._queue.task_done()
            else:
                logger.error(
                    f"Failed to send logs to ledger: {response.status_code} - {response.text}"
                )
                raise HashedAPIError(
                    f"Ledger request failed: {response.status_code}",
                    status_code=response.status_code,
                )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending logs to ledger: {e}")
            # Don't mark as done so they can be retried
        except Exception as e:
            logger.error(f"Unexpected error sending logs to ledger: {e}", exc_info=True)

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        """Check if the ledger is running."""
        return self._running

    async def __aenter__(self) -> "AsyncLedger":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
