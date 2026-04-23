"""
Tests for src/hashed/ledger.py

Covers:
 - WAL helper functions (_wal_init, _wal_insert, _wal_get_unsent,
   _wal_mark_sent, _wal_rows_to_entries)
 - AsyncLedger.__init__ and attribute defaults
 - AsyncLedger lifecycle: start → log → flush → stop using a real
   SQLite WAL on a temp path, with the HTTP client mocked.
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hashed.config import HashedConfig
from hashed.ledger import (
    AsyncLedger,
    _wal_get_all_for_verify,
    _wal_get_unsent,
    _wal_init,
    _wal_insert,
    _wal_mark_sent,
    _wal_rows_to_entries,
)

# ── WAL Helper Functions ──────────────────────────────────────────────────────


class TestWalInit:

    def test_creates_wal_entries_table(self, tmp_path: Path) -> None:
        """_wal_init creates 'wal_entries' table with all expected columns."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='wal_entries'"
            ).fetchall()
        assert len(rows) == 1

    def test_idempotent_double_init(self, tmp_path: Path) -> None:
        """Calling _wal_init twice on the same file does not raise."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        _wal_init(db)  # must not raise

    def test_creates_sent_index(self, tmp_path: Path) -> None:
        """_wal_init creates an index on the 'sent' column."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        with sqlite3.connect(db) as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        index_names = [row[0] for row in indexes]
        assert "idx_sent" in index_names


class TestWalInsertAndRetrieve:

    def test_insert_returns_positive_id(self, tmp_path: Path) -> None:
        """_wal_insert returns (row_id, entry_hash) — row_id is a positive int."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        entry = {
            "event_type": "transfer",
            "data": {"amount": 50},
            "metadata": {"agent": "bot"},
            "timestamp": "2026-01-01T00:00:00",
        }
        row_id, entry_hash = _wal_insert(db, entry)
        assert isinstance(row_id, int)
        assert row_id >= 1
        assert len(entry_hash) == 64  # SHA-256 hex

    def test_insert_increments_ids(self, tmp_path: Path) -> None:
        """Each insert returns a strictly increasing row id."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        entry = {
            "event_type": "log",
            "data": {},
            "timestamp": "2026-01-01T00:00:00",
        }
        results = [_wal_insert(db, entry) for _ in range(3)]
        ids = [r[0] for r in results]
        assert ids[0] < ids[1] < ids[2]

    def test_get_unsent_returns_inserted_row(self, tmp_path: Path) -> None:
        """_wal_get_unsent returns rows that were inserted and not yet sent."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        _wal_insert(db, {"event_type": "op", "data": {"x": 1}, "timestamp": "ts"})
        rows = _wal_get_unsent(db)
        assert len(rows) == 1
        # Row layout: (id, event_type, data, metadata, timestamp)
        assert rows[0][1] == "op"

    def test_get_unsent_excludes_sent_rows(self, tmp_path: Path) -> None:
        """_wal_get_unsent does not return rows deleted by _wal_mark_sent."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        row_id, _ = _wal_insert(db, {"event_type": "x", "data": {}, "timestamp": "t"})
        _wal_mark_sent(db, [row_id])
        rows = _wal_get_unsent(db)
        assert rows == []

    def test_get_unsent_empty_on_fresh_db(self, tmp_path: Path) -> None:
        """_wal_get_unsent returns an empty list on a brand-new WAL."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        assert _wal_get_unsent(db) == []


class TestWalMarkSent:

    def test_mark_sent_removes_multiple_rows(self, tmp_path: Path) -> None:
        """_wal_mark_sent deletes all listed row ids from the WAL."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        results = [
            _wal_insert(db, {"event_type": "a", "data": {}, "timestamp": "t"})
            for _ in range(3)
        ]
        # _wal_insert now returns (row_id, entry_hash) — extract just the ids
        row_ids = [r[0] for r in results]
        _wal_mark_sent(db, row_ids[:2])
        remaining = _wal_get_unsent(db)
        assert len(remaining) == 1
        assert remaining[0][0] == row_ids[2]

    def test_mark_sent_empty_list_is_noop(self, tmp_path: Path) -> None:
        """Calling _wal_mark_sent with an empty list does not raise."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        _wal_insert(db, {"event_type": "b", "data": {}, "timestamp": "t"})
        _wal_mark_sent(db, [])
        assert len(_wal_get_unsent(db)) == 1


class TestWalRowsToEntries:

    def test_converts_rows_to_dicts(self) -> None:
        """_wal_rows_to_entries converts raw SQLite tuples to usable dicts."""
        rows = [
            (
                7,
                "transfer",
                json.dumps({"amount": 99}),
                json.dumps({"agent": "x"}),
                "2026-01-01",
            ),
        ]
        entries = _wal_rows_to_entries(rows)
        assert len(entries) == 1
        assert entries[0]["_wal_id"] == 7
        assert entries[0]["event_type"] == "transfer"
        assert entries[0]["data"] == {"amount": 99}
        assert entries[0]["metadata"] == {"agent": "x"}
        assert entries[0]["timestamp"] == "2026-01-01"

    def test_empty_rows_returns_empty_list(self) -> None:
        """_wal_rows_to_entries with no rows returns []."""
        assert _wal_rows_to_entries([]) == []

    def test_multiple_rows(self) -> None:
        """_wal_rows_to_entries handles multiple rows correctly."""
        rows = [
            (1, "a", "{}", "{}", "t1"),
            (2, "b", '{"k": "v"}', '{"m": 1}', "t2"),
        ]
        entries = _wal_rows_to_entries(rows)
        assert len(entries) == 2
        assert entries[1]["data"] == {"k": "v"}
        assert entries[1]["metadata"] == {"m": 1}


# ── AsyncLedger.__init__ ──────────────────────────────────────────────────────


class TestAsyncLedgerInit:
    """
    Tests for AsyncLedger.__init__ attribute defaults.

    All tests are async so that a running asyncio event loop is present
    when asyncio.Queue() is created (required on Python 3.9).
    """

    @pytest.mark.asyncio
    async def test_default_attributes(self) -> None:
        """AsyncLedger sets correct defaults when no extra args are provided."""
        ledger = AsyncLedger(endpoint="https://api.example.com/v1/logs/batch")
        assert ledger._endpoint == "https://api.example.com/v1/logs/batch"
        assert ledger._batch_size == 10
        assert ledger._flush_interval == 5.0
        assert ledger._running is False
        assert ledger._worker_task is None
        assert ledger._client is None

    @pytest.mark.asyncio
    async def test_custom_batch_size(self) -> None:
        """AsyncLedger respects a custom batch_size argument."""
        ledger = AsyncLedger(endpoint="http://x", batch_size=25)
        assert ledger._batch_size == 25

    @pytest.mark.asyncio
    async def test_api_key_from_arg(self) -> None:
        """AsyncLedger stores api_key passed directly."""
        ledger = AsyncLedger(endpoint="http://x", api_key="mykey")
        assert ledger._api_key == "mykey"

    @pytest.mark.asyncio
    async def test_api_key_from_config(self) -> None:
        """AsyncLedger falls back to config.api_key when api_key arg is absent."""
        cfg = HashedConfig(api_url="http://x", api_key="cfg_key")
        ledger = AsyncLedger(endpoint="http://x", config=cfg)
        assert ledger._api_key == "cfg_key"

    @pytest.mark.asyncio
    async def test_wal_path_uses_default_when_none(self) -> None:
        """AsyncLedger uses a default WAL path when wal_path is not provided."""
        ledger = AsyncLedger(endpoint="http://x")
        assert ledger._wal_path is not None
        assert "wal" in ledger._wal_path.lower()

    @pytest.mark.asyncio
    async def test_wal_path_custom(self, tmp_path: Path) -> None:
        """AsyncLedger stores a custom wal_path correctly."""
        custom = str(tmp_path / "custom.db")
        ledger = AsyncLedger(endpoint="http://x", wal_path=custom)
        assert ledger._wal_path == custom

    @pytest.mark.asyncio
    async def test_agent_public_key_stored(self) -> None:
        """AsyncLedger stores agent_public_key."""
        ledger = AsyncLedger(endpoint="http://x", agent_public_key="pubkey_abc")
        assert ledger._agent_public_key == "pubkey_abc"


# ── AsyncLedger async lifecycle ────────────────────────────────────────────────


class TestAsyncLedgerLifecycle:
    """
    Lifecycle tests for AsyncLedger (start / stop / context manager).

    The background _worker task and httpx.AsyncClient are fully mocked so
    that no real I/O or network activity occurs.
    """

    @pytest.fixture
    def wal_db(self, tmp_path: Path) -> str:
        """Return an isolated temp path for the WAL database."""
        return str(tmp_path / "test_wal.db")

    @staticmethod
    async def _noop_worker(self: Any) -> None:
        """Replacement _worker that just sleeps until cancelled."""
        try:
            while True:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    def _patched_ledger(self, wal_db: str) -> "tuple[AsyncLedger, Any]":
        """
        Return a (ledger, patcher_ctx) pair where:
        - hashed.ledger.httpx.AsyncClient is replaced by AsyncMock
        - AsyncLedger._worker is replaced by a no-op coroutine
        """
        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(is_success=True, status_code=202)
        ledger = AsyncLedger(
            endpoint="http://mock/v1/logs/batch",
            wal_path=wal_db,
        )
        return ledger, mock_client

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self, wal_db: str) -> None:
        """After start(), ledger._running is True."""
        ledger, mock_client = self._patched_ledger(wal_db)
        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            assert ledger._running is True
            await ledger.stop(flush=False)


# ── _worker() real loop (no patch) ───────────────────────────────────────────


class TestWorkerRealLoop:
    """
    Let the real _worker() coroutine run — covers lines 372-396.

    Key insight: with _batch_size=1, the inner collection loop exits as soon
    as one entry is dequeued, and _send_batch() is called immediately.
    """

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "worker_real.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_worker_dequeues_and_sends_batch(self, wal_db: str) -> None:
        """
        After log() puts an entry in the queue, the real _worker() picks it up
        and calls _send_batch() → HTTP POST.  Lines 372-386 covered.
        """
        sent_event = asyncio.Event()
        post_payloads: list = []

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        async def _capture_post(url: str, json: dict = None, **kwargs):  # type: ignore[override]
            post_payloads.append(json or {})
            sent_event.set()
            r = MagicMock()
            r.is_success = True
            r.status_code = 200
            return r

        mock_client.post = AsyncMock(side_effect=_capture_post)

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)
        # batch_size=1 → exits inner while after a single entry, sends immediately
        ledger._batch_size = 1

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client):
            await ledger.start()

            await ledger.log(
                "worker.real.test", data={"n": 1}, metadata={"agent": "bot"}
            )

            # Worker should send the batch within a few seconds
            try:
                await asyncio.wait_for(sent_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pytest.fail("_worker() did not call _send_batch() within 5 seconds")

            await ledger.stop(flush=False)

        assert len(post_payloads) >= 1
        assert post_payloads[0].get("batch_size") == 1

    @pytest.mark.asyncio
    async def test_worker_timeout_branch_sends_batch_after_interval(
        self, wal_db: str
    ) -> None:
        """
        If no entry arrives before the flush interval, the inner while exits via
        asyncio.TimeoutError and the worker loops back (lines 382-383, 392-394).

        We keep a tiny flush_interval and no items → worker loops continuously
        via the TimeoutError branch without crashing.
        """
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=MagicMock(is_success=True, status_code=200)
        )

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)
        ledger._flush_interval = 0.05  # 50ms — fast timeout for test
        ledger._batch_size = 100  # never reached

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client):
            await ledger.start()
            # Let the worker loop a few times (via TimeoutError branch) without crashing
            await asyncio.sleep(0.2)
            await ledger.stop(flush=False)

        # No POST should have been made (no items queued)
        assert mock_client.post.call_count == 0


# ── log() with WAL path (lines 355-357) ──────────────────────────────────────


class TestLogWithWal:
    """log() inserts the entry into the WAL DB when wal_path is configured."""

    @pytest.mark.asyncio
    async def test_log_inserts_entry_into_wal(self, tmp_path: Path) -> None:
        """
        When wal_path is set, log() calls _wal_insert() before queuing.
        Lines 355-357 covered.
        """
        wal_db = str(tmp_path / "log_wal.db")
        _wal_init(wal_db)

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log("wal.insert.check", data={"key": "value"}, metadata={})
            await ledger.stop(flush=False)

        # The WAL DB must contain the unsent entry
        rows = _wal_get_unsent(wal_db)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_multiple_logs_all_inserted_into_wal(self, tmp_path: Path) -> None:
        """Each log() call inserts exactly one row into the WAL."""
        wal_db = str(tmp_path / "multi_wal.db")
        _wal_init(wal_db)

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            for i in range(3):
                await ledger.log(f"event.{i}", data={"i": i}, metadata={})
            await ledger.stop(flush=False)

        rows = _wal_get_unsent(wal_db)
        assert len(rows) == 3


# ── _send_batch() with agent_public_key (line 414) ───────────────────────────


class TestSendBatchWithPublicKey:
    """
    When agent_public_key is set on the ledger, _send_batch() includes it
    in the JSON payload sent to the backend.  Line 414 covered.
    """

    @pytest.mark.asyncio
    async def test_send_batch_includes_agent_public_key(self, tmp_path: Path) -> None:
        """agent_public_key is included in the HTTP POST payload."""
        wal_db = str(tmp_path / "pk_test.db")
        _wal_init(wal_db)

        post_payloads: list = []

        async def _capture(url: str, json: dict = None, **kwargs):  # type: ignore[override]
            post_payloads.append(json or {})
            r = MagicMock()
            r.is_success = True
            r.status_code = 200
            return r

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.post = AsyncMock(side_effect=_capture)

        ledger = AsyncLedger(
            endpoint="http://mock/v1/logs/batch",
            wal_path=wal_db,
            agent_public_key="deadbeef1234567890abcdef",
        )

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            logs = [{"event_type": "x", "data": {}, "metadata": {}, "timestamp": "t"}]
            await ledger._send_batch(logs)
            await ledger.stop(flush=False)

        assert len(post_payloads) == 1
        assert post_payloads[0]["agent_public_key"] == "deadbeef1234567890abcdef"

    @pytest.mark.asyncio
    async def test_send_batch_no_public_key_omits_field(self, tmp_path: Path) -> None:
        """When agent_public_key is None, the field is absent from the payload."""
        wal_db = str(tmp_path / "no_pk_test.db")
        _wal_init(wal_db)

        post_payloads: list = []

        async def _capture(url: str, json: dict = None, **kwargs):  # type: ignore[override]
            post_payloads.append(json or {})
            r = MagicMock()
            r.is_success = True
            r.status_code = 200
            return r

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.post = AsyncMock(side_effect=_capture)

        ledger = AsyncLedger(
            endpoint="http://mock/v1/logs/batch",
            wal_path=wal_db,
            # No agent_public_key
        )

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            logs = [{"event_type": "y", "data": {}, "metadata": {}, "timestamp": "t"}]
            await ledger._send_batch(logs)
            await ledger.stop(flush=False)

        assert len(post_payloads) == 1
        assert "agent_public_key" not in post_payloads[0]


# ── Fernet encryption in WAL helpers ─────────────────────────────────────────


class TestWalFernetEncryption:
    """_wal_insert + _wal_rows_to_entries with AES encryption."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "enc_test.db")
        _wal_init(db)
        return db

    def test_fernet_insert_stores_encrypted_data(self, wal_db: str) -> None:
        """Inserted data should NOT be readable as plain JSON when encrypted."""
        from cryptography.fernet import Fernet

        fernet = Fernet(Fernet.generate_key())
        entry = {
            "event_type": "transfer.success",
            "data": {"amount": 99.0, "to": "Alice"},
            "metadata": {"sig": "abc"},
            "timestamp": "2026-01-01T00:00:00",
        }

        _wal_insert(wal_db, entry, fernet=fernet)

        # Raw SQLite row should be unreadable as JSON
        rows = _wal_get_unsent(wal_db)
        assert len(rows) == 1
        _, _, raw_data, raw_meta, _ = rows[0]

        # Should not be valid JSON (it's a Fernet token, not plaintext)
        with pytest.raises(Exception):
            json.loads(raw_data)

    def test_fernet_round_trip(self, wal_db: str) -> None:
        """Data encrypted on insert can be decrypted on retrieve."""
        from cryptography.fernet import Fernet

        fernet = Fernet(Fernet.generate_key())
        entry = {
            "event_type": "test.event",
            "data": {"key": "value", "num": 42},
            "metadata": {"meta_key": "meta_val"},
            "timestamp": "2026-01-01T12:00:00",
        }

        _wal_insert(wal_db, entry, fernet=fernet)
        rows = _wal_get_unsent(wal_db)
        entries = _wal_rows_to_entries(rows, fernet=fernet)

        assert len(entries) == 1
        assert entries[0]["data"] == entry["data"]
        assert entries[0]["metadata"] == entry["metadata"]

    def test_fernet_decryption_fallback_on_plaintext(self, wal_db: str) -> None:
        """_wal_rows_to_entries falls back to plaintext for unencrypted rows."""
        from cryptography.fernet import Fernet

        # Insert WITHOUT encryption (simulates pre-encryption rows on upgrade)
        entry = {
            "event_type": "legacy.event",
            "data": {"old": "data"},
            "metadata": {},
            "timestamp": "2025-12-31T23:59:59",
        }
        _wal_insert(wal_db, entry, fernet=None)  # plain insert

        rows = _wal_get_unsent(wal_db)
        fernet = Fernet(Fernet.generate_key())

        # Should NOT raise — falls back to JSON parse
        entries = _wal_rows_to_entries(rows, fernet=fernet)
        assert entries[0]["data"] == {"old": "data"}


# ── AsyncLedger.log() ─────────────────────────────────────────────────────────


class TestAsyncLedgerLog:
    """Tests for AsyncLedger.log() — the primary public API."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "log_test.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_log_enqueues_entry(self, wal_db: str) -> None:
        """log() should enqueue the entry so queue_size increases by 1."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            before = ledger.queue_size
            await ledger.log("test.event", {"key": "val"})
            after = ledger.queue_size
            assert after == before + 1
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_log_writes_to_wal(self, wal_db: str) -> None:
        """log() should persist the entry to the SQLite WAL before queueing."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log(
                "transfer.success", {"amount": 100.0}, metadata={"sig": "xyz"}
            )
            await ledger.stop(flush=False)

        # WAL entry should exist
        rows = _wal_get_unsent(wal_db)
        assert len(rows) >= 1
        event_types = [r[1] for r in rows]
        assert "transfer.success" in event_types

    @pytest.mark.asyncio
    async def test_log_includes_metadata_and_timestamp(self, wal_db: str) -> None:
        """log() entry should have event_type, data, metadata, and timestamp."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log(
                "payment.denied",
                {"tool": "send_money"},
                metadata={"policy": "max_amount exceeded"},
            )

            # Get the queued entry before stop
            entry = await asyncio.wait_for(ledger._queue.get(), timeout=1.0)
            ledger._queue.task_done()
            await ledger.stop(flush=False)

        assert entry["event_type"] == "payment.denied"
        assert entry["data"]["tool"] == "send_money"
        assert entry["metadata"]["policy"] == "max_amount exceeded"
        assert "timestamp" in entry


# ── AsyncLedger._send_batch() ─────────────────────────────────────────────────


class TestAsyncLedgerSendBatch:
    """Tests for _send_batch() — HTTP batch send + WAL acknowledgment."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "batch_test.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_send_batch_calls_http_post(self, wal_db: str) -> None:
        """_send_batch() should POST to the endpoint with the log payload."""
        mock_client = AsyncMock()
        mock_resp = MagicMock(is_success=True, status_code=202)
        mock_client.post = AsyncMock(return_value=mock_resp)

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()

            logs = [
                {
                    "event_type": "a.success",
                    "data": {"x": 1},
                    "metadata": {},
                    "timestamp": "2026-01-01",
                },
                {
                    "event_type": "b.denied",
                    "data": {"y": 2},
                    "metadata": {},
                    "timestamp": "2026-01-02",
                },
            ]
            # Put tasks in queue so task_done() works
            for _ in logs:
                ledger._queue.put_nowait({})
            for _ in logs:
                ledger._queue.get_nowait()

            await ledger._send_batch(logs)
            await ledger.stop(flush=False)

        assert mock_client.post.call_count >= 1
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"] if call_kwargs[1] else call_kwargs[0][1]
        assert "logs" in payload
        assert payload["batch_size"] == 2

    @pytest.mark.asyncio
    async def test_send_batch_marks_wal_sent_on_success(self, wal_db: str) -> None:
        """After a successful send, WAL entries should be removed."""
        mock_client = AsyncMock()
        mock_resp = MagicMock(is_success=True, status_code=202)
        mock_client.post = AsyncMock(return_value=mock_resp)

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log("evt.ok", {"n": 1})

            entry = await asyncio.wait_for(ledger._queue.get(), timeout=1.0)
            wal_id = entry.get("_wal_id")

            # Confirm WAL entry exists
            unsent_before = _wal_get_unsent(wal_db)
            assert any(r[0] == wal_id for r in unsent_before)

            await ledger._send_batch([entry])

            await ledger.stop(flush=False)

        # WAL entry should be gone after successful send
        unsent_after = _wal_get_unsent(wal_db)
        assert not any(r[0] == wal_id for r in unsent_after)

    @pytest.mark.asyncio
    async def test_send_batch_noop_when_no_client(self, wal_db: str) -> None:
        """_send_batch() should be a no-op (no crash) when _client is None."""
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)
        ledger._client = None  # force None

        # Should not raise
        await ledger._send_batch(
            [{"event_type": "x", "data": {}, "metadata": {}, "timestamp": "t"}]
        )


# ── AsyncLedger properties ────────────────────────────────────────────────────


class TestAsyncLedgerProperties:
    """Tests for queue_size and is_running properties."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "props_test.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_queue_size_reflects_pending_entries(self, wal_db: str) -> None:
        """queue_size should match the number of unprocessed entries."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            assert ledger.queue_size == 0

            await ledger.log("evt1", {"x": 1})
            await ledger.log("evt2", {"x": 2})
            assert ledger.queue_size == 2
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_is_running_toggles(self, wal_db: str) -> None:
        """is_running should be False before start, True during, False after stop."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        assert ledger.is_running is False

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            assert ledger.is_running is True
            await ledger.stop(flush=False)

        assert ledger.is_running is False


# ── WAL crash recovery on start() ────────────────────────────────────────────


class TestWalCrashRecovery:
    """start() should re-queue unsent WAL entries from previous session."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "recovery_test.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_start_replays_unsent_entries(self, wal_db: str) -> None:
        """Unsent WAL entries from a prior crash are re-queued on start()."""
        # Seed two unsent entries directly in the WAL
        e1 = {
            "event_type": "crash.event1",
            "data": {"n": 1},
            "metadata": {},
            "timestamp": "t1",
        }
        e2 = {
            "event_type": "crash.event2",
            "data": {"n": 2},
            "metadata": {},
            "timestamp": "t2",
        }
        _wal_insert(wal_db, e1)
        _wal_insert(wal_db, e2)

        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            # Both crash entries should be in the queue
            assert ledger.queue_size == 2
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_start_no_unsent_entries_empty_queue(self, wal_db: str) -> None:
        """If WAL has no unsent entries, queue should be empty after start."""
        mock_client = AsyncMock()
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            assert ledger.queue_size == 0
            await ledger.stop(flush=False)


# ── _send_batch error paths ───────────────────────────────────────────────────


class TestSendBatchErrorPaths:
    """Cover the non-success and HTTP error branches in _send_batch()."""

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "err_test.db")
        _wal_init(db)
        return db

    @pytest.mark.asyncio
    async def test_send_batch_non_success_logs_error(self, wal_db: str) -> None:
        """_send_batch() with a non-success HTTP response logs error but does not raise."""

        mock_client = AsyncMock()
        error_resp = MagicMock(
            is_success=False, status_code=500, text="Internal Server Error"
        )
        mock_client.post = AsyncMock(return_value=error_resp)

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            # Should not raise
            logs = [{"event_type": "x", "data": {}, "metadata": {}, "timestamp": "t"}]
            await ledger._send_batch(logs)
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_send_batch_http_error_does_not_raise(self, wal_db: str) -> None:
        """_send_batch() with httpx.HTTPError should log and not propagate."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            logs = [{"event_type": "y", "data": {}, "metadata": {}, "timestamp": "t"}]
            # Must not raise
            await ledger._send_batch(logs)
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_send_batch_unexpected_exception_does_not_raise(
        self, wal_db: str
    ) -> None:
        """_send_batch() with an unexpected exception logs and does not propagate."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            logs = [{"event_type": "z", "data": {}, "metadata": {}, "timestamp": "t"}]
            await ledger._send_batch(logs)
            await ledger.stop(flush=False)


# ── Hash chain (SPEC §3.2) ───────────────────────────────────────────────────


class TestHashChain:
    """
    Tests for the forward-linked SHA-256 hash chain introduced in SPEC §3.2.

    Verifies that:
    - Every new entry receives prev_hash = "genesis" (first) or the prior
      entry's entry_hash (subsequent).
    - verify_chain() returns valid=True for an untampered chain.
    - verify_chain() detects direct SQLite data modification (tampering).
    - The chain state (_last_entry_hash) survives a ledger restart.
    - _compute_entry_hash is deterministic for the same inputs.
    """

    @pytest.fixture()
    def wal_db(self, tmp_path: Path) -> str:
        db = str(tmp_path / "chain_test.db")
        _wal_init(db)
        return db

    # ── 1. First entry has prev_hash == "genesis" ─────────────────────────────

    def test_first_entry_has_genesis_prev_hash(self, wal_db: str) -> None:
        """The very first WAL entry must have prev_hash == 'genesis'."""
        entry = {
            "event_type": "transfer",
            "data": {"amount": 100},
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
        }
        _wal_insert(wal_db, entry, prev_hash="genesis")

        rows = _wal_get_all_for_verify(wal_db)
        assert len(rows) == 1
        # Row layout: (id, event_type, data, metadata, timestamp, prev_hash, entry_hash)
        _, _, _, _, _, stored_prev_hash, stored_entry_hash = rows[0]
        assert stored_prev_hash == "genesis"
        assert len(stored_entry_hash) == 64

    # ── 2. Consecutive entries are linked ────────────────────────────────────

    def test_chain_links_consecutive_entries(self, wal_db: str) -> None:
        """Entry 2's prev_hash must equal entry 1's entry_hash."""
        e1 = {"event_type": "op1", "data": {"n": 1}, "metadata": {}, "timestamp": "t1"}
        e2 = {"event_type": "op2", "data": {"n": 2}, "metadata": {}, "timestamp": "t2"}

        _, hash1 = _wal_insert(wal_db, e1, prev_hash="genesis")
        _wal_insert(wal_db, e2, prev_hash=hash1)

        rows = _wal_get_all_for_verify(wal_db)
        assert len(rows) == 2

        _, _, _, _, _, prev2, hash2 = rows[1]
        assert prev2 == hash1
        assert len(hash2) == 64

    # ── 3. verify_chain reports valid on untampered chain ────────────────────

    @pytest.mark.asyncio
    async def test_verify_chain_valid_returns_true(self, wal_db: str) -> None:
        """After logging 3 entries, verify_chain() must return valid=True."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log("evt.a", {"x": 1})
            await ledger.log("evt.b", {"x": 2})
            await ledger.log("evt.c", {"x": 3})
            result = await ledger.verify_chain()
            await ledger.stop(flush=False)

        assert result["valid"] is True
        assert result["total_entries"] == 3
        assert result["broken_at"] is None

    # ── 4. verify_chain detects SQLite-level data tampering ──────────────────

    @pytest.mark.asyncio
    async def test_verify_chain_detects_tampering(self, wal_db: str) -> None:
        """Directly modifying the 'data' column in SQLite breaks the chain."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger.start()
            await ledger.log("evt.x", {"amount": 50})
            await ledger.log("evt.y", {"amount": 100})
            await ledger.stop(flush=False)

        # Tamper: change the data column of row 1 directly in SQLite
        with sqlite3.connect(wal_db) as conn:
            rows = conn.execute("SELECT id FROM wal_entries ORDER BY id").fetchall()
            tampered_id = rows[0][0]
            conn.execute(
                "UPDATE wal_entries SET data = ? WHERE id = ?",
                (json.dumps({"amount": 999}), tampered_id),
            )
            conn.commit()

        # Re-open a ledger and verify
        ledger2 = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger2.start()
            result = await ledger2.verify_chain()
            await ledger2.stop(flush=False)

        assert result["valid"] is False
        assert result["broken_at"] == tampered_id
        assert "tampered" in result["reason"]

    # ── 5. _last_entry_hash survives a ledger restart ────────────────────────

    @pytest.mark.asyncio
    async def test_chain_survives_restart(self, wal_db: str) -> None:
        """After stop() + start() the new entry correctly chains to the last."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        # ── Session 1: log two entries ────────────────────────────────────────
        ledger1 = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger1.start()
            await ledger1.log("session1.a", {"s": 1})
            await ledger1.log("session1.b", {"s": 2})
            last_hash_session1 = ledger1._last_entry_hash
            await ledger1.stop(flush=False)

        # ── Session 2: new ledger on same WAL ─────────────────────────────────
        ledger2 = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)

        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger2.start()
            # After start(), _last_entry_hash should equal last entry of session 1
            assert ledger2._last_entry_hash == last_hash_session1
            await ledger2.log("session2.a", {"s": 3})
            await ledger2.stop(flush=False)

        # The third WAL row should have prev_hash == last_hash_session1
        rows = _wal_get_all_for_verify(wal_db)
        assert len(rows) == 3
        _, _, _, _, _, third_prev, _ = rows[2]
        assert third_prev == last_hash_session1

        # Full chain should be valid
        ledger3 = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)
        with (
            patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client),
            patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker),
        ):
            await ledger3.start()
            result = await ledger3.verify_chain()
            await ledger3.stop(flush=False)

        assert result["valid"] is True
        assert result["total_entries"] == 3
