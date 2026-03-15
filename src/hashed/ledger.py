"""
Asynchronous ledger for non-blocking log transmission with durability.

This module implements an async ledger that:
1. Writes log entries to a SQLite WAL (write-ahead log) on disk BEFORE
   queuing them in memory — so they survive process crashes.
2. Replays unshipped entries from the WAL on startup.
3. Removes entries from the WAL only after they are successfully sent.

Producer-Consumer pattern with crash-safe durability.
"""

import asyncio
import base64
import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken

from hashed.config import HashedConfig

logger = logging.getLogger(__name__)

# Default WAL database location (relative to CWD, hidden file)
_DEFAULT_WAL_PATH = ".hashed_wal.db"

# ── WAL encryption (C-08 remediation — OWASP ASVS 4.0 L2) ───────────────────
_WAL_KDF_SALT = b"hashed-wal-v1"   # static salt — acceptable because the
                                    # API key is already 128-bit random entropy


def _derive_fernet_key(api_key: str) -> Optional[Fernet]:
    """Derive a Fernet key from the API key using PBKDF2-HMAC-SHA256.

    The derived key is deterministic given the same ``api_key``, which is
    required so the WAL can be decrypted after a process restart.

    Uses the ``cryptography`` library (already a dependency).
    Returns ``None`` if ``api_key`` is empty/None so that encryption is
    silently skipped when no key is configured.

    Security properties:
    - 128-bit base key (API key = ``hashed_`` + 32 hex chars)
    - 100 000 PBKDF2 iterations (NIST SP 800-132 recommendation)
    - AES-128-CBC + HMAC-SHA256 via Fernet
    - Threat model: attacker has the .db file but NOT the API key
    """
    if not api_key:
        return None
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        api_key.encode("utf-8"),
        _WAL_KDF_SALT,
        iterations=100_000,
        dklen=32,
    )
    return Fernet(base64.urlsafe_b64encode(raw))


# ── WAL helpers (sync, run in executor) ──────────────────────────────────────

def _wal_init(db_path: str) -> None:
    """Create the WAL table if it doesn't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wal_entries (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT    NOT NULL,
                data       TEXT    NOT NULL,
                metadata   TEXT    NOT NULL DEFAULT '{}',
                timestamp  TEXT    NOT NULL,
                sent       INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON wal_entries (sent)")
        conn.commit()


def _wal_insert(db_path: str, entry: dict[str, Any], fernet: Optional[Fernet] = None) -> int:
    """Insert a log entry into the WAL. Returns the new row id.

    If a ``Fernet`` cipher is supplied, the ``data`` and ``metadata`` fields
    are AES-encrypted before writing to disk.  The ``event_type`` and
    ``timestamp`` columns are left in plaintext (needed for replay sorting and
    operational visibility without the key).
    """
    data_str = json.dumps(entry["data"])
    metadata_str = json.dumps(entry.get("metadata", {}))

    if fernet:
        data_str = fernet.encrypt(data_str.encode("utf-8")).decode("ascii")
        metadata_str = fernet.encrypt(metadata_str.encode("utf-8")).decode("ascii")

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO wal_entries (event_type, data, metadata, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (
                entry["event_type"],
                data_str,
                metadata_str,
                entry["timestamp"],
            ),
        )
        conn.commit()
        return cur.lastrowid


def _wal_get_unsent(db_path: str) -> list[tuple]:
    """Return all unsent rows ordered by id."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT id, event_type, data, metadata, timestamp "
            "FROM wal_entries WHERE sent = 0 ORDER BY id"
        ).fetchall()


def _wal_mark_sent(db_path: str, ids: list[int]) -> None:
    """Delete sent entries from the WAL to keep the file small."""
    with sqlite3.connect(db_path) as conn:
        conn.executemany("DELETE FROM wal_entries WHERE id = ?", [(i,) for i in ids])
        conn.commit()


def _wal_rows_to_entries(
    rows: list[tuple],
    fernet: Optional[Fernet] = None,
) -> list[dict[str, Any]]:
    """Convert SQLite rows to log-entry dicts.

    If a ``Fernet`` cipher is supplied, attempts to decrypt ``data`` and
    ``metadata`` fields.  Falls back to treating them as plaintext if
    decryption fails — this enables zero-downtime migration of existing WAL
    databases that were written without encryption.
    """
    entries = []
    for row_id, event_type, data_json, metadata_json, timestamp in rows:
        if fernet:
            # Attempt decryption; fall through to plaintext on InvalidToken
            # so pre-encryption WAL rows are replayed correctly on first upgrade.
            try:
                data_json = fernet.decrypt(data_json.encode("ascii")).decode("utf-8")
            except (InvalidToken, Exception):
                pass  # already plaintext (migration path)
            try:
                metadata_json = fernet.decrypt(metadata_json.encode("ascii")).decode("utf-8")
            except (InvalidToken, Exception):
                pass

        entries.append({
            "_wal_id": row_id,
            "event_type": event_type,
            "data": json.loads(data_json),
            "metadata": json.loads(metadata_json),
            "timestamp": timestamp,
        })
    return entries


class AsyncLedger:
    """
    Crash-safe async ledger with SQLite write-ahead log.

    Write flow:
        1. ``log()`` writes to SQLite WAL (durable)
        2. ``log()`` enqueues the entry in the in-memory asyncio.Queue
        3. Background worker batches queue entries and POSTs to backend
        4. On successful send, WAL rows are deleted

    Startup recovery:
        If the process crashed mid-flight, ``start()`` reads any unsent
        rows from the WAL and re-queues them automatically.

    Example:
        >>> async with AsyncLedger(endpoint="https://api.example.com/v1/logs/batch") as ledger:
        ...     await ledger.log("transfer", {"amount": 50})
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
        wal_path: Optional[str] = None,
    ) -> None:
        """
        Initialize the async ledger.

        Args:
            endpoint: URL endpoint for batch log submission
            config: HashedConfig instance
            queue_size: Max in-memory queue size
            batch_size: Entries per network batch
            flush_interval: Seconds between automatic flushes
            agent_public_key: Ed25519 public key hex (for backend identification)
            api_key: API key for backend authentication
            wal_path: Path for the SQLite WAL database.
                      Defaults to ``.hashed_wal.db`` in CWD.
                      Set to ``None`` to disable durability (in-memory only).
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
        self._api_key = api_key or (config.api_key if config else None)
        # WAL — set to None to disable durability
        self._wal_path: Optional[str] = (
            str(Path(wal_path or _DEFAULT_WAL_PATH)) if wal_path is not False else None
        )

        # ── WAL encryption (C-08) ─────────────────────────────────────────────
        # Derive a Fernet cipher from the API key.  When the API key is not
        # configured, WAL entries are stored in plaintext and a warning is
        # emitted.  Callers should always pass api_key for production use.
        self._fernet: Optional[Fernet] = _derive_fernet_key(self._api_key)
        if self._wal_path and not self._fernet:
            logger.warning(
                "⚠️  WAL encryption DISABLED — no api_key configured. "
                "Audit log entries at %s will be stored in plaintext. "
                "Pass api_key= to AsyncLedger for AES-128 at-rest encryption "
                "(OWASP ASVS 4.0 L2 — C-08).",
                self._wal_path,
            )
        elif self._wal_path and self._fernet:
            logger.debug("WAL encryption enabled (Fernet/AES-128 — PBKDF2-SHA256 key derivation)")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the ledger worker.

        Initialises the WAL database, replays any unshipped entries from a
        previous session, then starts the background flush worker.
        """
        if self._running:
            logger.warning("Ledger is already running")
            return

        self._running = True

        # Init WAL
        if self._wal_path:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _wal_init, self._wal_path)

            # Replay crash-surviving entries (decrypt with stored Fernet key)
            unsent = await loop.run_in_executor(None, _wal_get_unsent, self._wal_path)
            if unsent:
                recovered = _wal_rows_to_entries(unsent, fernet=self._fernet)
                logger.info(f"WAL recovery: re-queuing {len(recovered)} unsent log entries")
                for entry in recovered:
                    try:
                        await self._queue.put(entry)
                    except asyncio.QueueFull:
                        logger.warning("Queue full during WAL recovery — some entries dropped")
                        break

        # Init HTTP client
        headers = {}
        if self._api_key:
            headers["X-API-KEY"] = self._api_key

        self._client = httpx.AsyncClient(
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
            headers=headers,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30,
            ),
        )

        self._worker_task = asyncio.create_task(self._worker())
        logger.info("AsyncLedger started")

    async def stop(self, flush: bool = True) -> None:
        """Stop the ledger worker, optionally flushing remaining entries."""
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

    # ── Public API ────────────────────────────────────────────────────────────

    async def log(
        self,
        event_type: str,
        data: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Durably enqueue a log entry.

        Writes to the SQLite WAL first (crash-safe), then enqueues in memory.

        Args:
            event_type: Type of event (e.g. ``transfer.success``)
            data: Event payload
            metadata: Optional metadata (signatures, context, etc.)
        """
        entry = {
            "event_type": event_type,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Write to WAL before touching the in-memory queue (encrypted if Fernet set)
        if self._wal_path:
            loop = asyncio.get_event_loop()
            wal_id = await loop.run_in_executor(
                None, _wal_insert, self._wal_path, entry, self._fernet
            )
            entry["_wal_id"] = wal_id

        try:
            await self._queue.put(entry)
            logger.debug(f"Queued log entry: {event_type}")
        except asyncio.QueueFull:
            logger.error(f"Ledger queue is full, dropping: {event_type}")
            raise

    async def flush(self) -> None:
        """Flush all buffered entries immediately."""
        if self._pending_logs:
            await self._send_batch(self._pending_logs)
            self._pending_logs.clear()

        await self._queue.join()
        logger.debug("Ledger flushed")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _worker(self) -> None:
        """Background worker: batch-collect from queue → send → mark WAL sent."""
        logger.debug("Ledger worker started")

        while self._running:
            try:
                end_time = asyncio.get_event_loop().time() + self._flush_interval

                while len(self._pending_logs) < self._batch_size:
                    remaining = max(0, end_time - asyncio.get_event_loop().time())
                    if remaining <= 0:
                        break
                    try:
                        entry = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                        self._pending_logs.append(entry)
                    except asyncio.TimeoutError:
                        break

                if self._pending_logs:
                    await self._send_batch(self._pending_logs)
                    self._pending_logs.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ledger worker error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _send_batch(self, logs: list) -> None:
        """Send a batch to the backend and remove from WAL on success."""
        if not self._client:
            logger.warning("HTTP client not initialised, skipping send")
            return

        # Strip internal WAL ids before sending
        wal_ids = [e.get("_wal_id") for e in logs if e.get("_wal_id")]
        clean_logs = [{k: v for k, v in e.items() if k != "_wal_id"} for e in logs]

        payload: dict[str, Any] = {
            "logs": clean_logs,
            "batch_size": len(clean_logs),
            "timestamp": datetime.utcnow().isoformat(),
        }
        if self._agent_public_key:
            payload["agent_public_key"] = self._agent_public_key

        try:
            response = await self._client.post(self._endpoint, json=payload)

            if response.is_success:
                logger.debug(f"Sent {len(clean_logs)} log entries to ledger")

                # Acknowledge queue tasks
                for _ in logs:
                    self._queue.task_done()

                # Remove successfully shipped entries from WAL
                if self._wal_path and wal_ids:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, _wal_mark_sent, self._wal_path, wal_ids
                    )
            else:
                logger.error(f"Ledger send failed: {response.status_code} — {response.text}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending ledger batch: {e}")
        except Exception as e:
            logger.error(f"Unexpected ledger error: {e}", exc_info=True)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def queue_size(self) -> int:
        """Current in-memory queue depth."""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        """Whether the worker is active."""
        return self._running

    async def __aenter__(self) -> "AsyncLedger":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
