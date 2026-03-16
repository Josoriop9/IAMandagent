"""
Hashed SDK - A professional Python SDK for hashed operations.

This package provides a clean, type-safe interface for cryptographic
hashing operations and API interactions.
"""

from hashed.client import HashedClient
from hashed.config import HashedConfig
from hashed.core import HashedCore, create_core
from hashed.exceptions import (
    HashedAPIError,
    HashedConfigError,
    HashedCryptoError,
    HashedError,
    HashedValidationError,
)
from hashed.guard import PermissionError, Policy, PolicyEngine
from hashed.identity import IdentityManager
from hashed.identity_store import (
    export_identity_for_env,
    generate_secure_password,
    get_or_create_identity_password,
    load_identity,
    load_identity_from_env,
    load_or_create_identity,
    save_identity,
    verify_identity_file,
)
from hashed.ledger import AsyncLedger
from hashed.models import HashAlgorithm, HashRequest, HashResponse

__version__ = "0.3.3"
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
    "get_or_create_identity_password",
    "load_or_create_identity",
    "load_identity",
    "save_identity",
    "verify_identity_file",
    "generate_secure_password",
    "load_identity_from_env",
    "export_identity_for_env",
    # Ledger
    "AsyncLedger",
]
