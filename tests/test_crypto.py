"""
Tests for cryptography operations.
"""

import pytest

from hashed.crypto.hasher import Hasher
from hashed.exceptions import HashedCryptoError
from hashed.models import HashRequest


class TestHasher:
    """Test suite for Hasher class."""

    def test_sha256_hash(self, hasher: Hasher) -> None:
        """Test SHA-256 hashing."""
        request = HashRequest(data="test", algorithm="sha256")
        response = hasher.hash(request)
        
        expected = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        assert response.hash_value == expected
        assert response.algorithm == "sha256"

    def test_sha512_hash(self, hasher: Hasher) -> None:
        """Test SHA-512 hashing."""
        request = HashRequest(data="test", algorithm="sha512")
        response = hasher.hash(request)
        
        assert len(response.hash_value) == 128
        assert response.algorithm == "sha512"

    def test_blake2b_hash(self, hasher: Hasher) -> None:
        """Test BLAKE2b hashing."""
        request = HashRequest(data="test", algorithm="blake2b")
        response = hasher.hash(request)
        
        assert response.hash_value
        assert response.algorithm == "blake2b"

    def test_blake2s_hash(self, hasher: Hasher) -> None:
        """Test BLAKE2s hashing."""
        request = HashRequest(data="test", algorithm="blake2s")
        response = hasher.hash(request)
        
        assert response.hash_value
        assert response.algorithm == "blake2s"

    def test_hash_with_salt(self, hasher: Hasher) -> None:
        """Test hashing with salt."""
        request1 = HashRequest(data="test", salt="salt1")
        request2 = HashRequest(data="test", salt="salt2")
        
        response1 = hasher.hash(request1)
        response2 = hasher.hash(request2)
        
        assert response1.hash_value != response2.hash_value
        assert response1.metadata["salted"] is True
        assert response2.metadata["salted"] is True

    def test_hash_metadata(self, hasher: Hasher) -> None:
        """Test that hash response includes correct metadata."""
        request = HashRequest(data="test data", algorithm="sha256", salt="salt")
        response = hasher.hash(request)
        
        assert response.metadata["encoding"] == "utf-8"
        assert response.metadata["salted"] is True
        assert response.metadata["data_length"] == 9

    def test_unicode_data(self, hasher: Hasher) -> None:
        """Test hashing Unicode data."""
        request = HashRequest(data="Hello, 世界! 🌍", algorithm="sha256")
        response = hasher.hash(request)
        
        assert response.hash_value
        assert len(response.hash_value) == 64

    def test_derive_key(self, hasher: Hasher) -> None:
        """Test key derivation with PBKDF2."""
        password = "secure_password"
        salt = b"random_salt_1234"
        
        key = hasher.derive_key(password, salt, length=32)
        
        assert len(key) == 32
        assert isinstance(key, bytes)

    def test_derive_key_consistency(self, hasher: Hasher) -> None:
        """Test that key derivation is consistent."""
        password = "password"
        salt = b"salt"
        
        key1 = hasher.derive_key(password, salt, length=32)
        key2 = hasher.derive_key(password, salt, length=32)
        
        assert key1 == key2
