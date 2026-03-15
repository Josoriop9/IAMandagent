"""
Tests for the new features introduced in the Sprint 7 HashedCore refactor:
  - _CircuitBreaker (open/closed/auto-reset)
  - _execute_remote_guard (circuit-breaker integration)
  - _log_to_all_transports (backend → ledger fallback)
  - _validate_local_policy (SRP helper)
  - sync_wrapper async/sync interop (ThreadPoolExecutor path)
  - _background_sync exponential backoff
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hashed.core import HashedCore, _CircuitBreaker
from hashed.config import HashedConfig
from hashed.guard import PermissionError as HashedPermissionError


# ──────────────────────────────────────────────────────────────────────────────
# _CircuitBreaker unit tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = _CircuitBreaker()
        assert cb.is_open is False

    def test_opens_after_threshold_failures(self):
        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False  # not yet
        cb.record_failure()
        assert cb.is_open is True   # threshold reached

    def test_success_resets_failure_count(self):
        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False  # two failures after reset — not open

    def test_auto_resets_after_cooldown(self):
        cb = _CircuitBreaker(failure_threshold=1, cooldown_s=0.05)
        cb.record_failure()
        assert cb.is_open is True
        time.sleep(0.1)
        assert cb.is_open is False  # cooldown elapsed

    def test_stays_open_within_cooldown(self):
        cb = _CircuitBreaker(failure_threshold=1, cooldown_s=60.0)
        cb.record_failure()
        assert cb.is_open is True

    def test_second_open_not_overwrite_opened_at(self):
        """record_failure beyond threshold must not reset opened_at."""
        cb = _CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        first_opened = cb._opened_at
        cb.record_failure()
        assert cb._opened_at == first_opened  # unchanged

    def test_record_success_when_closed_is_noop(self):
        cb = _CircuitBreaker()
        cb.record_success()  # should not raise
        assert cb.is_open is False


# ──────────────────────────────────────────────────────────────────────────────
# _validate_local_policy
# ──────────────────────────────────────────────────────────────────────────────

class TestValidateLocalPolicy:
    def _make_core(self):
        config = HashedConfig()
        config._backend_url = None
        return HashedCore(config=config)

    def test_passes_when_policy_allowed(self):
        core = self._make_core()
        core.policy_engine.add_policy("test_tool", allowed=True)
        context = {"args": (), "kwargs": {}, "public_key": core.identity.public_key_hex}
        # Should not raise
        core._validate_local_policy("test_tool", None, context)

    def test_raises_when_policy_denied(self):
        core = self._make_core()
        core.policy_engine.add_policy("blocked_tool", allowed=False)
        context = {"args": (), "kwargs": {}, "public_key": core.identity.public_key_hex}
        with pytest.raises(HashedPermissionError):
            core._validate_local_policy("blocked_tool", None, context)

    def test_raises_when_amount_exceeds_max(self):
        core = self._make_core()
        core.policy_engine.add_policy("transfer", allowed=True, max_amount=100.0)
        context = {"args": (), "kwargs": {}, "public_key": core.identity.public_key_hex}
        with pytest.raises(HashedPermissionError):
            core._validate_local_policy("transfer", 500.0, context)


# ──────────────────────────────────────────────────────────────────────────────
# _execute_remote_guard
# ──────────────────────────────────────────────────────────────────────────────

class TestExecuteRemoteGuard:
    def _make_core_with_client(self):
        config = HashedConfig()
        config._backend_url = "http://test"
        core = HashedCore(config=config)
        core._http_client = AsyncMock()
        return core

    @pytest.mark.asyncio
    async def test_no_op_when_no_http_client(self):
        config = HashedConfig()
        config._backend_url = None
        core = HashedCore(config=config)
        # Should not raise, no client
        await core._execute_remote_guard("tool", None, {})

    @pytest.mark.asyncio
    async def test_skip_when_circuit_open_fail_open(self):
        """Circuit OPEN + fail_open → skips call, does NOT raise."""
        core = self._make_core_with_client()
        core._circuit_breaker._failures = 3
        core._circuit_breaker._opened_at = time.monotonic()
        # fail_closed defaults to False — no override needed
        assert core._config.fail_closed is False

        await core._execute_remote_guard("tool", None, {})
        core._http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_when_circuit_open_fail_closed(self):
        """Circuit OPEN + fail_closed → raises PermissionError."""
        core = self._make_core_with_client()
        core._circuit_breaker._failures = 3
        core._circuit_breaker._opened_at = time.monotonic()
        # HashedConfig is frozen — override via with_overrides()
        core._config = core._config.with_overrides(fail_closed=True)

        with pytest.raises(HashedPermissionError, match="circuit breaker OPEN"):
            await core._execute_remote_guard("tool", None, {})

    @pytest.mark.asyncio
    async def test_records_success_on_allowed_response(self):
        core = self._make_core_with_client()
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"allowed": True}
        core._http_client.post = AsyncMock(return_value=mock_response)

        await core._execute_remote_guard("tool", None, {})
        assert core._circuit_breaker._failures == 0

    @pytest.mark.asyncio
    async def test_raises_permission_error_when_backend_denies(self):
        core = self._make_core_with_client()
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"allowed": False, "message": "blocked"}
        core._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(HashedPermissionError, match="denied by backend policy"):
            await core._execute_remote_guard("tool", None, {})

    @pytest.mark.asyncio
    async def test_records_failure_on_http_error_fail_open(self):
        core = self._make_core_with_client()
        core._http_client.post = AsyncMock(side_effect=Exception("network error"))
        core._config._fail_closed = False

        await core._execute_remote_guard("tool", None, {})
        assert core._circuit_breaker._failures == 1

    @pytest.mark.asyncio
    async def test_raises_on_http_error_fail_closed(self):
        core = self._make_core_with_client()
        core._http_client.post = AsyncMock(side_effect=Exception("network error"))
        core._config = core._config.with_overrides(fail_closed=True)

        with pytest.raises(HashedPermissionError, match="backend unreachable"):
            await core._execute_remote_guard("tool", None, {})

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self):
        """Three consecutive network errors should open the circuit."""
        core = self._make_core_with_client()
        core._http_client.post = AsyncMock(side_effect=Exception("network error"))
        core._config._fail_closed = False

        for _ in range(3):
            await core._execute_remote_guard("tool", None, {})

        assert core._circuit_breaker.is_open is True


# ──────────────────────────────────────────────────────────────────────────────
# _log_to_all_transports
# ──────────────────────────────────────────────────────────────────────────────

class TestLogToAllTransports:
    def _make_core(self):
        config = HashedConfig()
        config._backend_url = "http://test"
        core = HashedCore(config=config)
        core._http_client = AsyncMock()
        return core

    @pytest.mark.asyncio
    async def test_logs_to_backend_when_available(self):
        core = self._make_core()
        mock_resp = MagicMock()
        mock_resp.is_success = True
        core._http_client.post = AsyncMock(return_value=mock_resp)

        await core._log_to_all_transports("tool", "success", None, "result", "sig123")
        core._http_client.post.assert_called_once()
        call_json = core._http_client.post.call_args[1]["json"]
        assert call_json["status"] == "success"
        assert call_json["operation"] == "tool"

    @pytest.mark.asyncio
    async def test_falls_back_to_ledger_when_backend_fails(self):
        core = self._make_core()
        core._http_client.post = AsyncMock(side_effect=Exception("backend down"))
        mock_ledger = AsyncMock()
        core._ledger = mock_ledger

        await core._log_to_all_transports("tool", "success", None, "result", "sig123")
        mock_ledger.log.assert_called_once()
        call_kwargs = mock_ledger.log.call_args[1]
        assert call_kwargs["event_type"] == "tool.success"

    @pytest.mark.asyncio
    async def test_no_error_when_both_transports_unavailable(self):
        config = HashedConfig()
        config._backend_url = None
        core = HashedCore(config=config)
        # Both http_client and ledger are None — should be silent
        await core._log_to_all_transports("tool", "success", None, "result", "sig")

    @pytest.mark.asyncio
    async def test_truncates_long_result(self):
        core = self._make_core()
        mock_resp = MagicMock()
        mock_resp.is_success = True
        core._http_client.post = AsyncMock(return_value=mock_resp)
        long_result = "x" * 500

        await core._log_to_all_transports("tool", "success", None, long_result, "sig")
        call_json = core._http_client.post.call_args[1]["json"]
        assert len(call_json["data"]["result"]) == 200


# ──────────────────────────────────────────────────────────────────────────────
# sync_wrapper async/sync interop
# ──────────────────────────────────────────────────────────────────────────────

class TestSyncWrapper:
    def _make_core(self):
        config = HashedConfig()
        config._backend_url = None
        core = HashedCore(config=config)
        core.policy_engine.add_policy("sync_tool", allowed=True)
        return core

    def test_sync_function_decorated_runs_successfully(self):
        core = self._make_core()

        @core.guard("sync_tool")
        def sync_fn(value: str):
            return f"processed:{value}"

        result = sync_fn(value="hello")
        assert result == "processed:hello"

    @pytest.mark.asyncio
    async def test_sync_wrapper_works_inside_running_loop(self):
        """Verify sync_wrapper uses ThreadPoolExecutor when a loop is running."""
        core = self._make_core()

        @core.guard("sync_tool")
        def sync_fn(value: str):
            return f"thread:{value}"

        # We're already inside an async test (running loop exists)
        # The sync_wrapper should handle this via ThreadPoolExecutor
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: sync_fn(value="world"))
        assert result == "thread:world"

    @pytest.mark.asyncio
    async def test_async_function_decorated_runs_successfully(self):
        core = self._make_core()

        @core.guard("sync_tool")
        async def async_fn(value: str):
            return f"async:{value}"

        result = await async_fn(value="test")
        assert result == "async:test"


# ──────────────────────────────────────────────────────────────────────────────
# Performance tracking
# ──────────────────────────────────────────────────────────────────────────────

class TestPerformanceTracking:
    @pytest.mark.asyncio
    async def test_overhead_logged_at_debug(self, caplog):
        import logging
        config = HashedConfig()
        config._backend_url = None
        core = HashedCore(config=config)
        core.policy_engine.add_policy("timed_tool", allowed=True)

        @core.guard("timed_tool")
        async def timed_fn():
            return "ok"

        with caplog.at_level(logging.DEBUG, logger="hashed.core"):
            await timed_fn()

        overhead_logs = [r for r in caplog.records if "governance overhead" in r.message]
        assert len(overhead_logs) == 1
        assert "timed_tool" in overhead_logs[0].message
        assert "ms" in overhead_logs[0].message


# ──────────────────────────────────────────────────────────────────────────────
# _background_sync exponential backoff
# ──────────────────────────────────────────────────────────────────────────────

class TestBackgroundSyncBackoff:
    @pytest.mark.asyncio
    async def test_backoff_increases_on_repeated_failures(self):
        """Verify backoff grows between retries (exponential)."""
        config = HashedConfig()
        core = HashedCore(config=config)
        core._initialized = True
        core._http_client = AsyncMock()

        call_count = 0
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 4:
                core._initialized = False  # stop after 4 iterations

        async def fake_sync():
            nonlocal call_count
            call_count += 1
            raise Exception("simulated sync failure")

        with patch("asyncio.sleep", side_effect=fake_sleep):
            core.sync_policies_from_backend = fake_sync
            try:
                await core._background_sync()
            except Exception:
                pass

        # Backoff should grow: 0, 10, 20, 40, ...
        assert len(sleep_calls) >= 2
        # Each subsequent sleep should be >= previous (backoff increasing)
        for i in range(1, len(sleep_calls)):
            assert sleep_calls[i] >= sleep_calls[i - 1]

    @pytest.mark.asyncio
    async def test_backoff_resets_on_success(self):
        """Backoff resets to base sync_interval after a successful sync."""
        config = HashedConfig()
        core = HashedCore(config=config)
        core._initialized = True
        core._http_client = AsyncMock()

        # sync_interval minimum is 60s per HashedConfig validator
        base_interval = core._config.sync_interval  # 300 by default
        call_count = 0
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 3:
                core._initialized = False

        async def fake_sync():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("first failure")
            # second call succeeds → backoff resets to 0

        with patch("asyncio.sleep", side_effect=fake_sleep):
            core.sync_policies_from_backend = fake_sync
            await core._background_sync()

        # sleep_calls: [base, base+backoff, base+0]
        # After failure: sleep > base_interval (backoff added)
        # After success: sleep == base_interval (backoff reset to 0)
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == float(base_interval)       # first sleep, backoff=0
        assert sleep_calls[1] > sleep_calls[0]              # after failure, backoff added
        assert sleep_calls[2] == float(base_interval)       # after success, backoff reset
