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
from hashed.identity_store import (
    generate_secure_password,
    load_identity,
    load_or_create_identity,
    save_identity,
    verify_identity_file,
)
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
    # Identity Persistence
    "load_or_create_identity",
    "load_identity",
    "save_identity",
    "verify_identity_file",
    "generate_secure_password",
    # Ledger
    "AsyncLedger",
]
