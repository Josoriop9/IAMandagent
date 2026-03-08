"""
Tests for HTTPClient — covering request_async, request_sync,
retry logic, backoff, headers, and lifecycle methods.

All HTTP calls are intercepted via unittest.mock — no real network needed.
"""

import asyncio
import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from hashed.config import HashedConfig
from hashed.exceptions import HashedAPIError
from hashed.utils.http_client import HTTPClient, _backoff_delay


# ── Helpers ───────────────────────────────────────────────────────────────────

def _config(api_url: str = "http://test.local", api_key: str = "test_key") -> HashedConfig:
    """Return a HashedConfig with no real env vars."""
    import os
    for v in ("HASHED_BACKEND_URL", "HASHED_API_KEY"):
        os.environ.pop(v, None)
    return HashedConfig(api_url=api_url, api_key=api_key)


def _mock_response(
    status_code: int = 200,
    body: Optional[dict] = None,
    text: str = "",
    headers: Optional[dict] = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = body or {}
    resp.text = text
    resp.headers = headers or {}
    return resp


# ── _backoff_delay ────────────────────────────────────────────────────────────


class TestBackoffDelay:
    """Pure-function tests for _backoff_delay()."""

    def test_increases_with_attempt(self):
        d0 = _backoff_delay(0, jitter=False)
        d1 = _backoff_delay(1, jitter=False)
        d2 = _backoff_delay(2, jitter=False)
        assert d0 < d1 < d2

    def test_capped_at_max_wait(self):
        from hashed.utils.http_client import _MAX_RETRY_WAIT_SECONDS
        delay = _backoff_delay(100, jitter=False)
        assert delay <= _MAX_RETRY_WAIT_SECONDS

    def test_jitter_adds_noise(self):
        """Two calls with jitter=True should (almost always) differ."""
        delays = {_backoff_delay(0, jitter=True) for _ in range(20)}
        # With jitter there should be more than 1 distinct value across 20 samples
        assert len(delays) > 1

    def test_no_jitter_is_deterministic(self):
        d1 = _backoff_delay(3, jitter=False)
        d2 = _backoff_delay(3, jitter=False)
        assert d1 == d2


# ── HTTPClient initialisation ─────────────────────────────────────────────────


class TestHTTPClientInit:
    """Tests for __init__ and internal client factory methods."""

    def test_init_stores_config(self):
        cfg = _config()
        client = HTTPClient(cfg)
        assert client._config is cfg

    def test_async_client_not_created_at_init(self):
        """Async client should be lazily created."""
        client = HTTPClient(_config())
        assert client._client is None

    def test_sync_client_not_created_at_init(self):
        client = HTTPClient(_config())
        assert client._sync_client is None

    def test_get_headers_includes_auth_when_api_key_set(self):
        cfg = _config(api_key="hashed_abc123")
        client = HTTPClient(cfg)
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer hashed_abc123"

    def test_get_headers_no_auth_when_no_api_key(self):
        import os
        os.environ.pop("HASHED_API_KEY", None)
        cfg = HashedConfig(api_url="http://x", api_key=None)
        client = HTTPClient(cfg)
        headers = client._get_headers()
        assert "Authorization" not in headers

    def test_get_headers_content_type(self):
        client = HTTPClient(_config())
        headers = client._get_headers()
        assert headers["Content-Type"] == "application/json"

    def test_get_async_client_creates_and_caches(self):
        """_get_async_client() should create once and reuse."""
        client = HTTPClient(_config())
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            c1 = client._get_async_client()
            c2 = client._get_async_client()
        assert c1 is c2
        assert mock_cls.call_count == 1

    def test_get_sync_client_creates_and_caches(self):
        client = HTTPClient(_config())
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            c1 = client._get_sync_client()
            c2 = client._get_sync_client()
        assert c1 is c2
        assert mock_cls.call_count == 1


# ── request_async — success path ─────────────────────────────────────────────


class TestRequestAsync:
    """Tests for request_async() including retries."""

    def test_success_returns_json(self):
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)
            mock_resp = _mock_response(200, body={"ok": True})
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(return_value=mock_resp)

            with patch.object(client, "_get_async_client", return_value=async_inner):
                result = await client.request_async("GET", "/ping")

            assert result == {"ok": True}

        asyncio.run(run())

    def test_404_raises_immediately_no_retry(self):
        """4xx errors should not be retried."""
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)
            mock_resp = _mock_response(404, text="Not found")
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(return_value=mock_resp)

            with patch.object(client, "_get_async_client", return_value=async_inner):
                with pytest.raises(HashedAPIError) as exc_info:
                    await client.request_async("GET", "/missing")

            assert "404" in str(exc_info.value)
            assert async_inner.request.call_count == 1   # no retry

        asyncio.run(run())

    def test_503_retries_and_eventually_raises(self):
        """503 is retryable — exhausts retries then raises."""
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)
            mock_resp = _mock_response(503, text="unavailable")
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(return_value=mock_resp)

            # Patch sleep so the test doesn't actually wait
            with (
                patch.object(client, "_get_async_client", return_value=async_inner),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                with pytest.raises(HashedAPIError):
                    await client.request_async("POST", "/log")

            # max_retries default is 3, so 4 total attempts
            expected_attempts = cfg.max_retries + 1
            assert async_inner.request.call_count == expected_attempts

        asyncio.run(run())

    def test_503_retries_then_succeeds(self):
        """On transient error followed by success, returns json."""
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)

            fail = _mock_response(503, text="unavail")
            ok   = _mock_response(200, body={"result": "done"})
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(side_effect=[fail, ok])

            with (
                patch.object(client, "_get_async_client", return_value=async_inner),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                result = await client.request_async("GET", "/data")

            assert result == {"result": "done"}
            assert async_inner.request.call_count == 2

        asyncio.run(run())

    def test_network_error_retries(self):
        """ConnectError is retried, then raises HashedAPIError."""
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )

            with (
                patch.object(client, "_get_async_client", return_value=async_inner),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                with pytest.raises(HashedAPIError):
                    await client.request_async("GET", "/ping")

            assert async_inner.request.call_count == cfg.max_retries + 1

        asyncio.run(run())

    def test_429_respects_retry_after_header(self):
        """429 with Retry-After header should sleep for that duration (capped)."""
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)

            fail = _mock_response(429, headers={"Retry-After": "2"})
            ok   = _mock_response(200, body={"ok": 1})
            async_inner = AsyncMock()
            async_inner.request = AsyncMock(side_effect=[fail, ok])

            sleep_calls = []
            async def _fake_sleep(t):
                sleep_calls.append(t)

            with (
                patch.object(client, "_get_async_client", return_value=async_inner),
                patch("asyncio.sleep", side_effect=_fake_sleep),
            ):
                result = await client.request_async("POST", "/action")

            assert result == {"ok": 1}
            # Should have slept for ~2 seconds (the Retry-After value)
            assert len(sleep_calls) == 1
            assert sleep_calls[0] == pytest.approx(2.0)

        asyncio.run(run())


# ── request_sync — success path ──────────────────────────────────────────────


class TestRequestSync:
    """Tests for the synchronous request path."""

    def test_success_returns_json(self):
        cfg = _config()
        client = HTTPClient(cfg)
        mock_resp = _mock_response(200, body={"status": "ok"})
        sync_inner = MagicMock()
        sync_inner.request = MagicMock(return_value=mock_resp)

        with patch.object(client, "_get_sync_client", return_value=sync_inner):
            result = client.request_sync("GET", "/health")

        assert result == {"status": "ok"}

    def test_400_raises_immediately(self):
        cfg = _config()
        client = HTTPClient(cfg)
        mock_resp = _mock_response(400, text="Bad request")
        sync_inner = MagicMock()
        sync_inner.request = MagicMock(return_value=mock_resp)

        with patch.object(client, "_get_sync_client", return_value=sync_inner):
            with pytest.raises(HashedAPIError) as exc_info:
                client.request_sync("POST", "/bad")

        assert "400" in str(exc_info.value)
        assert sync_inner.request.call_count == 1

    def test_502_retries_then_raises(self):
        cfg = _config()
        client = HTTPClient(cfg)
        mock_resp = _mock_response(502, text="Bad gateway")
        sync_inner = MagicMock()
        sync_inner.request = MagicMock(return_value=mock_resp)

        with (
            patch.object(client, "_get_sync_client", return_value=sync_inner),
            patch("time.sleep"),
        ):
            with pytest.raises(HashedAPIError):
                client.request_sync("GET", "/api")

        assert sync_inner.request.call_count == cfg.max_retries + 1

    def test_network_error_retries_sync(self):
        cfg = _config()
        client = HTTPClient(cfg)
        sync_inner = MagicMock()
        sync_inner.request = MagicMock(
            side_effect=httpx.ConnectError("refused")
        )

        with (
            patch.object(client, "_get_sync_client", return_value=sync_inner),
            patch("time.sleep"),
        ):
            with pytest.raises(HashedAPIError):
                client.request_sync("GET", "/ping")

        assert sync_inner.request.call_count == cfg.max_retries + 1


# ── Lifecycle — close_async / close_sync ─────────────────────────────────────


class TestHTTPClientLifecycle:

    def test_close_async_closes_client(self):
        async def run():
            cfg = _config()
            client = HTTPClient(cfg)
            mock_inner = AsyncMock()
            client._client = mock_inner

            await client.close_async()

            mock_inner.aclose.assert_awaited_once()
            assert client._client is None

        asyncio.run(run())

    def test_close_async_noop_when_no_client(self):
        """close_async() when client is None should not raise."""
        async def run():
            client = HTTPClient(_config())
            await client.close_async()   # no exception
        asyncio.run(run())

    def test_close_sync_closes_client(self):
        cfg = _config()
        client = HTTPClient(cfg)
        mock_inner = MagicMock()
        client._sync_client = mock_inner

        client.close_sync()

        mock_inner.close.assert_called_once()
        assert client._sync_client is None

    def test_close_sync_noop_when_no_client(self):
        client = HTTPClient(_config())
        client.close_sync()  # no exception
