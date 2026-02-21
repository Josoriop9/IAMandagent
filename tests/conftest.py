"""
Pytest configuration and fixtures.

This module provides reusable test fixtures following the
DRY (Don't Repeat Yourself) principle.
"""

import pytest

from hashed.client import HashedClient
from hashed.config import HashedConfig
from hashed.crypto.hasher import Hasher


@pytest.fixture
def test_config() -> HashedConfig:
    """
    Provide a test configuration.

    Returns:
        HashedConfig: Configuration for testing
    """
    return HashedConfig(
        api_url="https://test.api.example.com",
        timeout=10.0,
        max_retries=1,
        verify_ssl=False,
        debug=True,
    )


@pytest.fixture
def client(test_config: HashedConfig) -> HashedClient:
    """
    Provide a test client instance.

    Args:
        test_config: Test configuration fixture

    Returns:
        HashedClient: Client for testing
    """
    return HashedClient(config=test_config)


@pytest.fixture
def hasher() -> Hasher:
    """
    Provide a hasher instance.

    Returns:
        Hasher: Hasher for testing
    """
    return Hasher()


@pytest.fixture
def sample_data() -> dict:
    """
    Provide sample test data.

    Returns:
        Dictionary of sample data for testing
    """
    return {
        "simple_string": "Hello, World!",
        "unicode_string": "Hello, 世界! 🌍",
        "empty_string": "",
        "long_string": "a" * 10000,
    }
