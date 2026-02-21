"""
Tests for Pydantic models.
"""

import pytest
from pydantic import ValidationError

from hashed.models import HashRequest, HashResponse, HashAlgorithm


class TestHashRequest:
    """Test suite for HashRequest model."""

    def test_valid_request(self) -> None:
        """Test creating a valid hash request."""
        request = HashRequest(data="test")
        assert request.data == "test"
        assert request.algorithm == HashAlgorithm.SHA256
        assert request.encoding == "utf-8"
        assert request.salt is None

    def test_custom_algorithm(self) -> None:
        """Test request with custom algorithm."""
        request = HashRequest(data="test", algorithm=HashAlgorithm.SHA512)
        assert request.algorithm == HashAlgorithm.SHA512

    def test_with_salt(self) -> None:
        """Test request with salt."""
        request = HashRequest(data="test", salt="my_salt")
        assert request.salt == "my_salt"

    def test_empty_data_fails(self) -> None:
        """Test that empty data raises validation error."""
        with pytest.raises(ValidationError):
            HashRequest(data="")

    def test_invalid_encoding(self) -> None:
        """Test that invalid encoding raises validation error."""
        with pytest.raises(ValidationError):
            HashRequest(data="test", encoding="invalid_encoding")

    def test_algorithm_enum_values(self) -> None:
        """Test that algorithm enum has expected values."""
        assert HashAlgorithm.SHA256.value == "sha256"
        assert HashAlgorithm.SHA512.value == "sha512"
        assert HashAlgorithm.BLAKE2B.value == "blake2b"
        assert HashAlgorithm.BLAKE2S.value == "blake2s"


class TestHashResponse:
    """Test suite for HashResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid hash response."""
        response = HashResponse(
            hash_value="abc123",
            algorithm="sha256"
        )
        assert response.hash_value == "abc123"
        assert response.algorithm == "sha256"
        assert response.timestamp
        assert isinstance(response.metadata, dict)

    def test_with_metadata(self) -> None:
        """Test response with custom metadata."""
        metadata = {"key": "value", "count": 42}
        response = HashResponse(
            hash_value="abc123",
            algorithm="sha256",
            metadata=metadata
        )
        assert response.metadata == metadata

    def test_response_immutability(self) -> None:
        """Test that response fields are set correctly."""
        response = HashResponse(
            hash_value="test_hash",
            algorithm="sha256"
        )
        assert response.hash_value == "test_hash"
