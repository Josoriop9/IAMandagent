"""
Main client interface for the Hashed SDK.

This module provides the HashedClient class, which serves as the
primary entry point for SDK users.
"""

import logging
from typing import Optional

from hashed.config import HashedConfig
from hashed.crypto.hasher import Hasher
from hashed.models import HashRequest, HashResponse
from hashed.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)


class HashedClient:
    """
    Main client for the Hashed SDK.

    This class implements the Facade pattern, providing a simplified
    interface to the SDK's complex subsystems. It follows the Single
    Responsibility Principle by delegating specific tasks to specialized
    components.

    Example:
        >>> from hashed import HashedClient, HashRequest
        >>> client = HashedClient.from_env()
        >>> request = HashRequest(data="Hello, World!")
        >>> response = client.hash(request)
        >>> print(response.hash_value)
    """

    def __init__(self, config: Optional[HashedConfig] = None) -> None:
        """
        Initialize the Hashed client.

        Args:
            config: Configuration for the client. If None, will use default config.
        """
        self._config = config or HashedConfig()
        self._http_client = HTTPClient(self._config)
        self._hasher = Hasher()
        
        if self._config.debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("HashedClient initialized in debug mode")

    @classmethod
    def from_env(cls) -> "HashedClient":
        """
        Create a client from environment variables.

        This is a factory method following the Factory pattern.

        Returns:
            HashedClient: Configured client instance

        Example:
            >>> client = HashedClient.from_env()
        """
        config = HashedConfig.from_env()
        return cls(config=config)

    @property
    def config(self) -> HashedConfig:
        """Get the current configuration."""
        return self._config

    def hash(self, request: HashRequest) -> HashResponse:
        """
        Compute a hash for the given request.

        This method delegates to the Hasher component, demonstrating
        the Delegation principle.

        Args:
            request: Hash request containing data and parameters

        Returns:
            HashResponse: Response containing the computed hash

        Example:
            >>> request = HashRequest(data="Hello", algorithm="sha256")
            >>> response = client.hash(request)
        """
        logger.debug(f"Computing hash with algorithm: {request.algorithm}")
        return self._hasher.hash(request)

    def hash_string(
        self,
        data: str,
        algorithm: str = "sha256",
        salt: Optional[str] = None,
    ) -> str:
        """
        Convenience method to hash a string and return the hash value directly.

        Args:
            data: String to hash
            algorithm: Hashing algorithm to use
            salt: Optional salt

        Returns:
            Hexadecimal hash string

        Example:
            >>> hash_value = client.hash_string("Hello, World!")
        """
        request = HashRequest(data=data, algorithm=algorithm, salt=salt)
        response = self.hash(request)
        return response.hash_value

    def derive_key(
        self,
        password: str,
        salt: bytes,
        length: int = 32,
        iterations: int = 100000,
    ) -> bytes:
        """
        Derive a cryptographic key from a password.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation
            length: Desired key length in bytes
            iterations: Number of iterations

        Returns:
            Derived key as bytes

        Example:
            >>> import os
            >>> salt = os.urandom(16)
            >>> key = client.derive_key("my_password", salt)
        """
        logger.debug(f"Deriving key with length: {length}")
        return self._hasher.derive_key(password, salt, length, iterations)

    async def request_async(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """
        Make an async API request.

        This demonstrates the async/await pattern for non-blocking operations.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data

        Returns:
            Response data

        Example:
            >>> import asyncio
            >>> async def main():
            ...     result = await client.request_async("POST", "/hash", {"data": "test"})
            >>> asyncio.run(main())
        """
        logger.debug(f"Making async {method} request to {endpoint}")
        return await self._http_client.request_async(method, endpoint, data=data)

    def request_sync(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """
        Make a synchronous API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data

        Returns:
            Response data

        Example:
            >>> result = client.request_sync("GET", "/status")
        """
        logger.debug(f"Making sync {method} request to {endpoint}")
        return self._http_client.request_sync(method, endpoint, data=data)

    async def close_async(self) -> None:
        """
        Close async resources.

        Should be called when done with async operations.

        Example:
            >>> await client.close_async()
        """
        await self._http_client.close_async()
        logger.debug("Async resources closed")

    def close_sync(self) -> None:
        """
        Close synchronous resources.

        Should be called when done with sync operations.

        Example:
            >>> client.close_sync()
        """
        self._http_client.close_sync()
        logger.debug("Sync resources closed")

    def __enter__(self) -> "HashedClient":
        """
        Context manager entry.

        Enables usage with 'with' statement for automatic resource management.

        Example:
            >>> with HashedClient() as client:
            ...     result = client.hash_string("test")
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        self.close_sync()

    async def __aenter__(self) -> "HashedClient":
        """
        Async context manager entry.

        Example:
            >>> async with HashedClient() as client:
            ...     result = await client.request_async("GET", "/status")
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup resources."""
        await self.close_async()
