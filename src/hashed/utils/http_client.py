"""
HTTP client utilities for API interactions.

This module provides an abstraction over httpx for making HTTP requests
with retry logic, error handling, and async support.
"""

import asyncio
import logging
import random
import time
from typing import Any, Optional, Set

import httpx

from hashed.config import HashedConfig
from hashed.exceptions import HashedAPIError

logger = logging.getLogger(__name__)

# HTTP status codes that are worth retrying (transient errors)
_RETRYABLE_STATUS_CODES: Set[int] = {429, 502, 503, 504}

# Hard cap on retry wait so agents don't stall indefinitely
_MAX_RETRY_WAIT_SECONDS: float = 30.0


def _backoff_delay(attempt: int, jitter: bool = True) -> float:
    """
    Calculate exponential backoff delay with optional jitter.

    Formula: min(base * 2^attempt + jitter, max_wait)

    Args:
        attempt: Zero-based attempt number
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Seconds to wait before next attempt
    """
    base = 2 ** attempt          # 1, 2, 4, 8, 16 …
    noise = random.uniform(0, 1) if jitter else 0
    return min(base + noise, _MAX_RETRY_WAIT_SECONDS)


class HTTPClient:
    """
    HTTP client wrapper with exponential-backoff retry and error handling.

    Retry behaviour:
    - Retries on network-level errors (ConnectError, TimeoutException, etc.)
    - Retries on transient HTTP errors: 429 (rate limited), 502, 503, 504
    - Respects ``Retry-After`` header when present (429 responses)
    - Does NOT retry on 4xx client errors (400, 401, 403, 404 …) — those
      are deterministic failures that won't improve on retry.
    - Adds random jitter to each delay to prevent thundering-herd effects.

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
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._config.api_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers=self._get_headers(),
            )
        return self._client

    def _get_sync_client(self) -> httpx.Client:
        """Get or create the sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self._config.api_url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
                headers=self._get_headers(),
            )
        return self._sync_client

    # ── Async ────────────────────────────────────────────────────────────────

    async def request_async(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make an async HTTP request with exponential-backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body (serialised as JSON)
            params: URL query parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            HashedAPIError: If the request fails after all retries
        """
        client = self._get_async_client()
        last_error: Optional[Exception] = None
        max_attempts = self._config.max_retries + 1

        for attempt in range(max_attempts):
            try:
                response = await client.request(
                    method=method,
                    url=endpoint,
                    json=data,
                    params=params,
                )

                # ── Success ──────────────────────────────────────────────
                if response.is_success:
                    return response.json()

                # ── Transient server error — retry ───────────────────────
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = HashedAPIError(
                        f"Transient HTTP {response.status_code} from {endpoint}",
                        status_code=response.status_code,
                        details={"endpoint": endpoint, "method": method},
                    )
                    if attempt < max_attempts - 1:
                        # Respect Retry-After header (common on 429)
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait = min(float(retry_after), _MAX_RETRY_WAIT_SECONDS)
                        else:
                            wait = _backoff_delay(attempt)
                        logger.warning(
                            f"HTTP {response.status_code} on attempt "
                            f"{attempt + 1}/{max_attempts} for {method} {endpoint}. "
                            f"Retrying in {wait:.1f}s…"
                        )
                        await asyncio.sleep(wait)
                    continue

                # ── Deterministic client error — do not retry ────────────
                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_data.get("error", response.text))
                except Exception:
                    pass

                raise HashedAPIError(
                    f"API request failed [{response.status_code}]: {error_detail}",
                    status_code=response.status_code,
                    details={"endpoint": endpoint, "method": method},
                )

            except httpx.HTTPError as e:
                # Network-level errors (timeout, connection refused, etc.)
                last_error = e
                if attempt < max_attempts - 1:
                    wait = _backoff_delay(attempt)
                    logger.warning(
                        f"Network error on attempt {attempt + 1}/{max_attempts} "
                        f"for {method} {endpoint}: {e}. Retrying in {wait:.1f}s…"
                    )
                    await asyncio.sleep(wait)
                continue

        raise HashedAPIError(
            f"Request failed after {max_attempts} attempt(s): {last_error}",
            details={"endpoint": endpoint, "method": method},
        ) from last_error

    # ── Sync ─────────────────────────────────────────────────────────────────

    def request_sync(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make a synchronous HTTP request with exponential-backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body (serialised as JSON)
            params: URL query parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            HashedAPIError: If the request fails after all retries
        """
        client = self._get_sync_client()
        last_error: Optional[Exception] = None
        max_attempts = self._config.max_retries + 1

        for attempt in range(max_attempts):
            try:
                response = client.request(
                    method=method,
                    url=endpoint,
                    json=data,
                    params=params,
                )

                if response.is_success:
                    return response.json()

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = HashedAPIError(
                        f"Transient HTTP {response.status_code} from {endpoint}",
                        status_code=response.status_code,
                        details={"endpoint": endpoint, "method": method},
                    )
                    if attempt < max_attempts - 1:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait = min(float(retry_after), _MAX_RETRY_WAIT_SECONDS)
                        else:
                            wait = _backoff_delay(attempt)
                        logger.warning(
                            f"HTTP {response.status_code} on attempt "
                            f"{attempt + 1}/{max_attempts} for {method} {endpoint}. "
                            f"Retrying in {wait:.1f}s…"
                        )
                        time.sleep(wait)
                    continue

                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_data.get("error", response.text))
                except Exception:
                    pass

                raise HashedAPIError(
                    f"API request failed [{response.status_code}]: {error_detail}",
                    status_code=response.status_code,
                    details={"endpoint": endpoint, "method": method},
                )

            except httpx.HTTPError as e:
                last_error = e
                if attempt < max_attempts - 1:
                    wait = _backoff_delay(attempt)
                    logger.warning(
                        f"Network error on attempt {attempt + 1}/{max_attempts} "
                        f"for {method} {endpoint}: {e}. Retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
                continue

        raise HashedAPIError(
            f"Request failed after {max_attempts} attempt(s): {last_error}",
            details={"endpoint": endpoint, "method": method},
        ) from last_error

    # ── Lifecycle ─────────────────────────────────────────────────────────────

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
