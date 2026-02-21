"""
Hashed SDK - A professional Python SDK for hashed operations.

This package provides a clean, type-safe interface for cryptographic
hashing operations and API interactions.
"""

from hashed.client import HashedClient
from hashed.config import HashedConfig
from hashed.core import HashedCore, create_core
from hashed.exceptions import (
    HashedError,
    HashedAPIError,
    HashedConfigError,
    HashedCryptoError,
    HashedValidationError,
)
from hashed.guard import PermissionError, Policy, PolicyEngine
from hashed.identity import IdentityManager
from hashed.ledger import AsyncLedger
from hashed.models import HashRequest, HashResponse, HashAlgorithm

__version__ = "0.1.0"
__all__ = [
    # Core
    "HashedClient",
    "HashedCore",
    "create_core",
    # Configuration
    "HashedConfig",
    # Exceptions
    "HashedError",
    "HashedAPIError",
    "HashedConfigError",
    "HashedCryptoError",
    "HashedValidationError",
    "PermissionError",
    # Models
    "HashRequest",
    "HashResponse",
    "HashAlgorithm",
    # Security & Policy
    "IdentityManager",
    "PolicyEngine",
    "Policy",
    # Ledger
    "AsyncLedger",
]
