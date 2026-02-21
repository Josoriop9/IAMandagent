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
