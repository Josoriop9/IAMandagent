"""
Tests for the HashedClient class.
"""

import pytest

from hashed.client import HashedClient
from hashed.config import HashedConfig
from hashed.models import HashRequest


class TestHashedClient:
    """Test suite for HashedClient."""

    def test_client_initialization(self, test_config: HashedConfig) -> None:
        """Test that client initializes correctly."""
        client = HashedClient(config=test_config)
        assert client.config == test_config

    def test_client_from_env(self) -> None:
        """Test client creation from environment."""
        client = HashedClient.from_env()
        assert isinstance(client, HashedClient)
        assert isinstance(client.config, HashedConfig)

    def test_hash_string_sha256(self, client: HashedClient) -> None:
        """Test hashing a string with SHA-256."""
        result = client.hash_string("Hello, World!")
        # Expected SHA-256 hash
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert result == expected

    def test_hash_with_request(self, client: HashedClient) -> None:
        """Test hashing with a HashRequest object."""
        request = HashRequest(data="test", algorithm="sha256")
        response = client.hash(request)

        assert response.hash_value
        assert response.algorithm == "sha256"
        assert response.metadata["data_length"] == 4

    def test_hash_with_salt(self, client: HashedClient) -> None:
        """Test hashing with salt."""
        hash1 = client.hash_string("test", salt="salt1")
        hash2 = client.hash_string("test", salt="salt2")
        hash3 = client.hash_string("test", salt="salt1")

        # Different salts should produce different hashes
        assert hash1 != hash2
        # Same salt should produce same hash
        assert hash1 == hash3

    def test_different_algorithms(self, client: HashedClient) -> None:
        """Test different hashing algorithms."""
        data = "test"
        sha256_hash = client.hash_string(data, algorithm="sha256")
        sha512_hash = client.hash_string(data, algorithm="sha512")
        blake2b_hash = client.hash_string(data, algorithm="blake2b")

        # All should produce different length hashes
        assert len(sha256_hash) == 64  # 256 bits = 64 hex chars
        assert len(sha512_hash) == 128  # 512 bits = 128 hex chars
        assert len(blake2b_hash) == 128  # BLAKE2b default

    def test_context_manager_sync(self, test_config: HashedConfig) -> None:
        """Test client as synchronous context manager."""
        with HashedClient(config=test_config) as client:
            result = client.hash_string("test")
            assert result

    @pytest.mark.asyncio
    async def test_context_manager_async(self, test_config: HashedConfig) -> None:
        """Test client as asynchronous context manager."""
        async with HashedClient(config=test_config) as client:
            result = client.hash_string("test")
            assert result

    def test_derive_key(self, client: HashedClient) -> None:
        """Test key derivation."""
        import os
        salt = os.urandom(16)
        key = client.derive_key("password", salt, length=32)

        assert len(key) == 32
        assert isinstance(key, bytes)

        # Same password and salt should produce same key
        key2 = client.derive_key("password", salt, length=32)
        assert key == key2

        # Different password should produce different key
        key3 = client.derive_key("different", salt, length=32)
        assert key != key3


# ── HTTP proxy methods + lifecycle ───────────────────────────────────────────


class TestHashedClientHTTPAndLifecycle:
    """Covers request_async, request_sync, close_async, close_sync."""

    @pytest.mark.asyncio
    async def test_request_async_delegates_to_http_client(
        self, test_config: HashedConfig
    ) -> None:
        """request_async() delegates to the internal HTTPClient."""
        from unittest.mock import AsyncMock, patch

        client = HashedClient(config=test_config)
        with patch.object(
            client._http_client,
            "request_async",
            new_callable=AsyncMock,
            return_value={"status": "ok"},
        ) as mock_req:
            result = await client.request_async("GET", "/ping")

        assert result == {"status": "ok"}
        mock_req.assert_awaited_once_with("GET", "/ping", data=None)

    def test_request_sync_delegates_to_http_client(
        self, test_config: HashedConfig
    ) -> None:
        """request_sync() delegates to the internal HTTPClient."""
        from unittest.mock import patch

        client = HashedClient(config=test_config)
        with patch.object(
            client._http_client,
            "request_sync",
            return_value={"pong": True},
        ) as mock_req:
            result = client.request_sync("GET", "/health")

        assert result == {"pong": True}
        mock_req.assert_called_once_with("GET", "/health", data=None)

    @pytest.mark.asyncio
    async def test_close_async_delegates_to_http_client(
        self, test_config: HashedConfig
    ) -> None:
        """close_async() calls HTTPClient.close_async()."""
        from unittest.mock import AsyncMock

        client = HashedClient(config=test_config)
        client._http_client.close_async = AsyncMock()

        await client.close_async()

        client._http_client.close_async.assert_awaited_once()

    def test_close_sync_delegates_to_http_client(
        self, test_config: HashedConfig
    ) -> None:
        """close_sync() calls HTTPClient.close_sync()."""
        from unittest.mock import MagicMock

        client = HashedClient(config=test_config)
        client._http_client.close_sync = MagicMock()

        client.close_sync()

        client._http_client.close_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_calls_close_async(
        self, test_config: HashedConfig
    ) -> None:
        """__aexit__ should call close_async()."""
        from unittest.mock import AsyncMock

        client = HashedClient(config=test_config)
        client._http_client.close_async = AsyncMock()

        async with client:
            pass

        client._http_client.close_async.assert_awaited_once()

    def test_sync_context_manager_calls_close_sync(
        self, test_config: HashedConfig
    ) -> None:
        """__exit__ should call close_sync()."""
        from unittest.mock import MagicMock

        client = HashedClient(config=test_config)
        client._http_client.close_sync = MagicMock()

        with client:
            pass

        client._http_client.close_sync.assert_called_once()
