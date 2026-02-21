"""
Data models for the Hashed SDK.

This module defines Pydantic models for request and response validation,
ensuring type safety and data integrity throughout the SDK.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class HashAlgorithm(str, Enum):
    """Supported hashing algorithms."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


class HashRequest(BaseModel):
    """
    Request model for hashing operations.

    This model validates input data before processing, following
    the Interface Segregation Principle by providing a focused interface.
    """

    data: str = Field(
        ...,
        min_length=1,
        description="Data to be hashed",
    )
    algorithm: HashAlgorithm = Field(
        default=HashAlgorithm.SHA256,
        description="Hashing algorithm to use",
    )
    encoding: str = Field(
        default="utf-8",
        description="Character encoding for the input data",
    )
    salt: Optional[str] = Field(
        default=None,
        description="Optional salt for the hash",
    )

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, v: str) -> str:
        """Validate that the encoding is supported."""
        try:
            "test".encode(v)
        except LookupError:
            raise ValueError(f"Unsupported encoding: {v}")
        return v

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_schema_extra = {
            "example": {
                "data": "Hello, World!",
                "algorithm": "sha256",
                "encoding": "utf-8",
            }
        }


class HashResponse(BaseModel):
    """
    Response model for hashing operations.

    Contains the result of a hashing operation along with metadata.
    """

    hash_value: str = Field(
        ...,
        description="The computed hash value",
    )
    algorithm: str = Field(
        ...,
        description="Algorithm used for hashing",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of when the hash was computed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the operation",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "hash_value": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
                "algorithm": "sha256",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            }
        }


class APIResponse(BaseModel):
    """
    Generic API response model.

    Provides a consistent structure for API responses.
    """

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Response data",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the operation failed",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the response",
    )
