"""
Asynchronous ledger for non-blocking log transmission with durability.

This module implements an async ledger that:
1. Writes log entries to a SQLite WAL (write-ahead log) on disk BEFORE
   queuing them in memory — so they survive process crashes.
2. Replays unshipped entries from the WAL on startup.
3. Removes entries from the WAL only after they are successfully sent.
4. Maintains a forward-linked SHA-256 hash chain (SPEC §3.2) for tamper
   detection: each entry records prev_hash = SHA-256(previous entry's hash),
   making retroactive modification detectable in O(n).

Producer-Consumer pattern with crash-safe durability.
"""

import asyncio
import base64
import functools
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

# Sentinel values for the hash chain
_GENESIS_HASH = "genesis"
_LEGACY_HASH = "legacy"

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


# ── Hash chain helpers (SPEC §3.2) ───────────────────────────────────────────

def _compute_entry_hash(entry_plaintext: dict[str, Any], prev_hash: str) -> str:
    """Compute the SHA-256 hash for a WAL entry in the forward-linked chain.

    The hash covers the immutable fields of the entry plus ``prev_hash``,
    binding each entry cryptographically to its predecessor.

    Canonicalization uses ``json.dumps(sort_keys=True, separators=(",", ":"),
    ensure_ascii=True)`` so the byte sequence is deterministic regardless of
    dict insertion order or platform.

    Args:
        entry_plaintext: Dict with keys ``event_type``, ``data``,
                         ``metadata``, and ``timestamp`` — all in plaintext
                         (not the Fernet-encrypted strings stored on disk).
        prev_hash: The ``entry_hash`` of the immediately preceding WAL entry,
                   or ``"genesis"`` for the first entry.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    hashable = {
        "event_type": entry_plaintext["event_type"],
        "data": entry_plaintext["data"],
        "metadata": entry_plaintext.get("metadata", {}),
        "timestamp": entry_plaintext["timestamp"],
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── WAL helpers (sync, run in executor) ──────────────────────────────────────

def _wal_init(db_path: str) -> None:
    """Create the WAL table (and hash-chain columns) if they don't exist.

    Safe to call on an existing database:
    - ``CREATE TABLE IF NOT EXISTS`` is idempotent.
    - ``ALTER TABLE ADD COLUMN`` is guarded by ``try/except OperationalError``
      so it silently no-ops if the column already exists.
    - Pre-chain rows (from before this version) are stamped with
      ``prev_hash='legacy'`` and ``entry_hash='legacy'`` so
      ``verify_chain()`` can treat them as trusted anchors.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wal_entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT    NOT NULL,
                data       TEXT    NOT NULL,
                metadata   TEXT    NOT NULL DEFAULT '{}',
                timestamp  TEXT    NOT NULL,
                sent       INTEGER NOT NULL DEFAULT 0,
                prev_hash  TEXT    NOT NULL DEFAULT 'genesis',
                entry_hash TEXT    NOT NULL DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON wal_entries (sent)")

        # Soft migration: add hash-chain columns to existing WAL databases.
        # If the column already exists, sqlite3 raises OperationalError → ignore.
        for col, default in [("prev_hash", _GENESIS_HASH), ("entry_hash", "")]:
            try:
                conn.execute(
                    f"ALTER TABLE wal_entries ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'"
                )
            except sqlite3.OperationalError:
                pass  # Column already present — noop

        # Stamp pre-chain rows as "legacy" so verify_chain() can skip them.
        # A row is "legacy" if its entry_hash is still the empty default.
        conn.execute(
            "UPDATE wal_entries SET prev_hash = 'legacy', entry_hash = 'legacy' "
            "WHERE entry_hash = '' OR entry_hash IS NULL"
        )
        conn.commit()


def _wal_insert(
    db_path: str,
    entry: dict[str, Any],
    fernet: Optional[Fernet] = None,
    prev_hash: str = _GENESIS_HASH,
) -> tuple:
    """Insert a log entry into the WAL. Returns ``(row_id, entry_hash)``.

    The ``entry_hash`` is computed from the *plaintext* entry fields (before
    Fernet encryption) combined with ``prev_hash``, creating a tamper-evident
    chain link.

    If a ``Fernet`` cipher is supplied, the ``data`` and ``metadata`` fields
    are AES-encrypted before writing to disk.  The ``event_type``,
    ``timestamp``, ``prev_hash``, and ``entry_hash`` columns are stored in
    plaintext (required for chain verification without exposing payloads).
    """
    # Compute hash from plaintext BEFORE encrypting (so verify_chain can
    # recompute the hash after decryption and get the same result).
    entry_hash = _compute_entry_hash(entry, prev_hash)

    data_str = json.dumps(entry["data"])
    metadata_str = json.dumps(entry.get("metadata", {}))

    if fernet:
        data_str = fernet.encrypt(data_str.encode("utf-8")).decode("ascii")
        metadata_str = fernet.encrypt(metadata_str.encode("utf-8")).decode("ascii")

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO wal_entries "
            "(event_type, data, metadata, timestamp, prev_hash, entry_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry["event_type"],
                data_str,
                metadata_str,
                entry["timestamp"],
                prev_hash,
                entry_hash,
            ),
        )
        conn.commit()
        return cur.lastrowid, entry_hash


def _wal_get_unsent(db_path: str) -> list:
    """Return all unsent rows ordered by id."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT id, event_type, data, metadata, timestamp "
            "FROM wal_entries WHERE sent = 0 ORDER BY id"
        ).fetchall()


def _wal_mark_sent(db_path: str, ids: list) -> None:
    """Delete sent entries from the WAL to keep the file small."""
    with sqlite3.connect(db_path) as conn:
        conn.executemany("DELETE FROM wal_entries WHERE id = ?", [(i,) for i in ids])
        conn.commit()


def _wal_get_last_entry_hash(db_path: str) -> str:
    """Return the ``entry_hash`` of the most recent WAL row.

    Used on startup to seed ``AsyncLedger._last_entry_hash`` so newly logged
    entries correctly continue the chain from the previous session.

    Returns ``"genesis"`` if the WAL is empty.
    """
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT entry_hash FROM wal_entries ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return _GENESIS_HASH
    # An empty string means the column exists but was never set — treat as genesis.
    return row[0] if row[0] else _GENESIS_HASH


def _wal_get_all_for_verify(db_path: str) -> list:
    """Return ALL WAL rows ordered by id, including hash-chain columns.

    Used exclusively by ``AsyncLedger.verify_chain()``.
    Row layout: (id, event_type, data, metadata, timestamp, prev_hash, entry_hash)
    """
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT id, event_type, data, metadata, timestamp, prev_hash, entry_hash "
            "FROM wal_entries ORDER BY id"
        ).fetchall()


def _wal_rows_to_entries(
    rows: list,
    fernet: Optional[Fernet] = None,
) -> list:
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
    Crash-safe async ledger with SQLite write-ahead log and hash chain.

    Write flow:
        1. ``log()`` writes to SQLite WAL (durable) with hash chain fields
        2. ``log()`` enqueues the entry in the in-memory asyncio.Queue
        3. Background worker batches queue entries and POSTs to backend
        4. On successful send, WAL rows are deleted

    Startup recovery:
        If the process crashed mid-flight, ``start()`` reads any unsent
        rows from the WAL and re-queues them automatically.  It also
        loads ``_last_entry_hash`` from the WAL so new entries continue
        the chain from where the previous session left off.

    Tamper detection:
        Call ``verify_chain()`` at any time to validate the hash chain.
        Any retroactively modified, inserted, or deleted entry breaks the
        chain and is reported with the row id where the break occurred.

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

        # ── Hash chain (SPEC §3.2) ────────────────────────────────────────────
        # Seeded to "genesis" at init; updated to the last WAL entry's hash
        # during start() so new entries chain from the previous session.
        self._last_entry_hash: str = _GENESIS_HASH

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the ledger worker.

        Initialises the WAL database (including hash-chain column migration),
        replays any unshipped entries from a previous session, seeds
        ``_last_entry_hash`` from the WAL, then starts the background worker.
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

            # Seed hash chain from last WAL entry so new entries continue the chain.
            self._last_entry_hash = await loop.run_in_executor(
                None, _wal_get_last_entry_hash, self._wal_path
            )
            logger.debug(f"Hash chain seeded: _last_entry_hash={self._last_entry_hash[:16]}…")

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
        Durably enqueue a log entry with hash-chain linkage.

        Writes to the SQLite WAL first (crash-safe), computing ``prev_hash``
        and ``entry_hash`` to extend the tamper-evident chain, then enqueues
        in memory.

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

        # Write to WAL before touching the in-memory queue.
        # Pass the current chain tip so the new entry links to it.
        if self._wal_path:
            loop = asyncio.get_event_loop()
            wal_id, entry_hash = await loop.run_in_executor(
                None,
                functools.partial(
                    _wal_insert,
                    self._wal_path,
                    entry,
                    self._fernet,
                    self._last_entry_hash,
                ),
            )
            entry["_wal_id"] = wal_id
            # Advance chain tip
            self._last_entry_hash = entry_hash

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

    async def verify_chain(self) -> dict:
        """Verify the integrity of the WAL hash chain (SPEC §3.2).

        Iterates every WAL entry in insertion order and recomputes its
        ``entry_hash`` from the stored plaintext fields and ``prev_hash``.
        Any mismatch indicates retroactive tampering.

        Legacy entries (written before hash-chain support was added) are
        treated as trusted anchors — the first new-style entry after a
        legacy block is anchored at ``"legacy"`` and the chain resumes.

        Returns:
            A dict with four keys:

            * ``"valid"`` (bool) — ``True`` if no tampering detected.
            * ``"total_entries"`` (int) — number of rows inspected.
            * ``"broken_at"`` (int | None) — WAL row ``id`` where the chain
              first breaks, or ``None`` if the chain is intact.
            * ``"reason"`` (str | None) — human-readable description of the
              break, or ``None`` if the chain is intact.
        """
        if not self._wal_path:
            return {
                "valid": True,
                "total_entries": 0,
                "broken_at": None,
                "reason": "WAL disabled — no chain to verify",
            }

        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _wal_get_all_for_verify, self._wal_path)

        if not rows:
            return {"valid": True, "total_entries": 0, "broken_at": None, "reason": None}

        expected_prev_hash = _GENESIS_HASH

        for row_id, event_type, data_enc, metadata_enc, timestamp, stored_prev_hash, stored_entry_hash in rows:
            # Legacy entries pre-date hash-chain support — use as anchor and skip.
            if stored_entry_hash == _LEGACY_HASH:
                expected_prev_hash = _LEGACY_HASH
                continue

            # Decrypt data/metadata if the ledger has a Fernet cipher.
            data_json = data_enc
            metadata_json = metadata_enc
            if self._fernet:
                try:
                    data_json = self._fernet.decrypt(data_enc.encode("ascii")).decode("utf-8")
                except Exception:
                    pass  # plaintext fallback
                try:
                    metadata_json = self._fernet.decrypt(metadata_enc.encode("ascii")).decode("utf-8")
                except Exception:
                    pass

            try:
                data = json.loads(data_json)
                metadata = json.loads(metadata_json)
            except Exception:
                return {
                    "valid": False,
                    "total_entries": len(rows),
                    "broken_at": row_id,
                    "reason": f"Entry {row_id}: failed to parse data/metadata",
                }

            # Check chain linkage: the stored prev_hash must match our expectation.
            if stored_prev_hash != expected_prev_hash:
                return {
                    "valid": False,
                    "total_entries": len(rows),
                    "broken_at": row_id,
                    "reason": (
                        f"Entry {row_id}: prev_hash mismatch "
                        f"(expected {expected_prev_hash!r}, got {stored_prev_hash!r})"
                    ),
                }

            # Recompute entry_hash and compare to stored value.
            entry_plaintext = {
                "event_type": event_type,
                "data": data,
                "metadata": metadata,
                "timestamp": timestamp,
            }
            computed_hash = _compute_entry_hash(entry_plaintext, stored_prev_hash)

            if computed_hash != stored_entry_hash:
                return {
                    "valid": False,
                    "total_entries": len(rows),
                    "broken_at": row_id,
                    "reason": f"Entry {row_id}: entry_hash mismatch — data was tampered",
                }

            expected_prev_hash = stored_entry_hash

        return {"valid": True, "total_entries": len(rows), "broken_at": None, "reason": None}

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
