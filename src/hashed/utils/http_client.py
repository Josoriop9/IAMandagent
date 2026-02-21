"""
HTTP client utilities for API interactions.

This module provides an abstraction over httpx for making HTTP requests
with retry logic, error handling, and async support.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

from hashed.config import HashedConfig
from hashed.exceptions import HashedAPIError

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    HTTP client wrapper with retry logic and error handling.

    This class follows the Single Responsibility Principle by focusing
    solely on HTTP communication concerns.
    """

    def __init__(self, config: HashedConfig) -> None:
        """
        Initialize the HTTP client.

        Args:
            config: SDK configuration
        """
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

    def _get_headers(self) -> dict[str, str]:
        """
        Get default headers for requests.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "hashed-sdk/0.1.0",
        }
        
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        
        return headers

    def _get_async_client(self) -> httpx.AsyncClient:
        """
        Get or create the async HTTP client.

        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._config.api_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers=self._get_headers(),
            )
        return self._client

    def _get_sync_client(self) -> httpx.Client:
        """
        Get or create the sync HTTP client.

        Returns:
            httpx.Client instance
        """
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self._config.api_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers=self._get_headers(),
            )
        return self._sync_client

    async def request_async(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make an async HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            HashedAPIError: If the request fails after retries
        """
        client = self._get_async_client()
        last_error = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=endpoint,
                    json=data,
                    params=params,
                )
                
                if response.is_success:
                    return response.json()
                
                # Handle non-success status codes
                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", response.text)
                except Exception:
                    pass
                
                raise HashedAPIError(
                    f"API request failed: {error_detail}",
                    status_code=response.status_code,
                    details={"endpoint": endpoint, "method": method},
                )
                
            except httpx.HTTPError as e:
                last_error = e
                if attempt < self._config.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self._config.max_retries + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                continue

        # All retries exhausted
        raise HashedAPIError(
            f"Request failed after {self._config.max_retries + 1} attempts: {last_error}",
            details={"endpoint": endpoint, "method": method},
        ) from last_error

    def request_sync(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make a synchronous HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            HashedAPIError: If the request fails after retries
        """
        client = self._get_sync_client()
        last_error = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = client.request(
                    method=method,
                    url=endpoint,
                    json=data,
                    params=params,
                )
                
                if response.is_success:
                    return response.json()
                
                # Handle non-success status codes
                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", response.text)
                except Exception:
                    pass
                
                raise HashedAPIError(
                    f"API request failed: {error_detail}",
                    status_code=response.status_code,
                    details={"endpoint": endpoint, "method": method},
                )
                
            except httpx.HTTPError as e:
                last_error = e
                if attempt < self._config.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self._config.max_retries + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    import time
                    time.sleep(wait_time)
                continue

        # All retries exhausted
        raise HashedAPIError(
            f"Request failed after {self._config.max_retries + 1} attempts: {last_error}",
            details={"endpoint": endpoint, "method": method},
        ) from last_error

    async def close_async(self) -> None:
        """Close the async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def close_sync(self) -> None:
        """Close the sync HTTP client."""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
