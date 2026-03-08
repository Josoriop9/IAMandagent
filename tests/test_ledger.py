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
        """_wal_insert returns a positive integer row id."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        entry = {
            "event_type": "transfer",
            "data": {"amount": 50},
            "metadata": {"agent": "bot"},
            "timestamp": "2026-01-01T00:00:00",
        }
        row_id = _wal_insert(db, entry)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_insert_increments_ids(self, tmp_path: Path) -> None:
        """Each insert returns a strictly increasing row id."""
        db = str(tmp_path / "wal.db")
        _wal_init(db)
        entry = {
            "event_type": "log",
            "data": {},
            "timestamp": "2026-01-01T00:00:00",
        }
        ids = [_wal_insert(db, entry) for _ in range(3)]
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
        row_id = _wal_insert(db, {"event_type": "x", "data": {}, "timestamp": "t"})
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
        ids = [
            _wal_insert(db, {"event_type": "a", "data": {}, "timestamp": "t"})
            for _ in range(3)
        ]
        _wal_mark_sent(db, ids[:2])
        remaining = _wal_get_unsent(db)
        assert len(remaining) == 1
        assert remaining[0][0] == ids[2]

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
            (7, "transfer", json.dumps({"amount": 99}), json.dumps({"agent": "x"}), "2026-01-01"),
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
        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            assert ledger._running is True
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self, wal_db: str) -> None:
        """Calling start() twice does not raise; second call is a no-op."""
        ledger, mock_client = self._patched_ledger(wal_db)
        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            await ledger.start()  # should warn and return early
            assert ledger._running is True
            await ledger.stop(flush=False)

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, wal_db: str) -> None:
        """After stop(), ledger._running is False."""
        ledger, mock_client = self._patched_ledger(wal_db)
        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            await ledger.stop(flush=False)
        assert ledger._running is False

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self, wal_db: str) -> None:
        """Calling stop() on a ledger that was never started does not raise."""
        ledger = AsyncLedger(endpoint="http://mock/v1/logs/batch", wal_path=wal_db)
        await ledger.stop()  # must not raise

    @pytest.mark.asyncio
    async def test_context_manager_starts_and_stops(self, wal_db: str) -> None:
        """AsyncLedger can be used as an async context manager."""
        ledger, mock_client = self._patched_ledger(wal_db)
        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            async with AsyncLedger(
                endpoint="http://mock/v1/logs/batch", wal_path=wal_db
            ) as ledger:
                assert ledger._running is True
        assert ledger._running is False

    @pytest.mark.asyncio
    async def test_wal_created_on_start(self, wal_db: str) -> None:
        """start() creates the SQLite WAL file at wal_path."""
        ledger, mock_client = self._patched_ledger(wal_db)
        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            assert Path(wal_db).exists()
            await ledger.stop(flush=False)


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
        _wal_insert(wal_db, entry, fernet=None)   # plain insert

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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            await ledger.log("transfer.success", {"amount": 100.0}, metadata={"sig": "xyz"})
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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()

            logs = [
                {"event_type": "a.success", "data": {"x": 1}, "metadata": {}, "timestamp": "2026-01-01"},
                {"event_type": "b.denied",  "data": {"y": 2}, "metadata": {}, "timestamp": "2026-01-02"},
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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
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
        await ledger._send_batch([{"event_type": "x", "data": {}, "metadata": {}, "timestamp": "t"}])


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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
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

        with patch("hashed.ledger.httpx.AsyncClient", return_value=mock_client), \
             patch.object(AsyncLedger, "_worker", TestAsyncLedgerLifecycle._noop_worker):
            await ledger.start()
            assert ledger.is_running is True
            await ledger.stop(flush=False)

        assert ledger.is_running is False
