"""
Custom exceptions for the Hashed SDK.

This module defines a hierarchy of exceptions that provide clear,
specific error handling throughout the SDK.
"""

from typing import Any, Optional


class HashedError(Exception):
    """Base exception for all Hashed SDK errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        """
        Initialize the base exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class HashedConfigError(HashedError):
    """Raised when there's a configuration error."""

    pass


class HashedAPIError(HashedError):
    """Raised when an API request fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code if applicable
            details: Optional dictionary with additional error context
        """
        super().__init__(message, details)
        self.status_code = status_code


class HashedCryptoError(HashedError):
    """Raised when a cryptographic operation fails."""

    pass


class HashedValidationError(HashedError):
    """Raised when data validation fails."""

    pass
