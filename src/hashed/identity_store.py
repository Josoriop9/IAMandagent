"""
Identity persistence module for secure key management.

This module provides functions to securely store and load agent identities
across sessions, enabling persistent agent identity.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from hashed.exceptions import HashedCryptoError
from hashed.identity import IdentityManager

logger = logging.getLogger(__name__)


def load_or_create_identity(
    filepath: str,
    password: Optional[str] = None,
    create_if_missing: bool = True,
) -> IdentityManager:
    """
    Load an existing identity or create a new one if it doesn't exist.

    This is the main entry point for persistent identity management. It will:
    1. Check if the identity file exists
    2. If yes: load and decrypt it
    3. If no: generate a new identity and save it (if create_if_missing=True)

    Args:
        filepath: Path to the identity file (e.g., "./secrets/agent_key.pem")
        password: Password to encrypt/decrypt the private key. If None, uses no encryption.
        create_if_missing: If True, creates a new identity if file doesn't exist

    Returns:
        IdentityManager instance with persistent identity

    Raises:
        HashedCryptoError: If loading/creating fails
        FileNotFoundError: If file doesn't exist and create_if_missing=False

    Example:
        >>> # First run: generates and saves
        >>> identity = load_or_create_identity("./secrets/agent.pem", "my_password")
        >>> 
        >>> # Subsequent runs: loads the same identity
        >>> identity = load_or_create_identity("./secrets/agent.pem", "my_password")
        >>> 
        >>> # Use with HashedCore
        >>> core = HashedCore(identity=identity, agent_name="MyBot")
    """
    path = Path(filepath)

    # Check if identity file exists
    if path.exists():
        logger.info(f"Loading existing identity from {filepath}")
        return load_identity(filepath, password)

    # File doesn't exist
    if not create_if_missing:
        raise FileNotFoundError(f"Identity file not found: {filepath}")

    logger.info(f"Creating new identity and saving to {filepath}")
    identity = IdentityManager()
    save_identity(identity, filepath, password)
    return identity


def save_identity(
    identity: IdentityManager,
    filepath: str,
    password: Optional[str] = None,
    overwrite: bool = False,
) -> None:
    """
    Save an identity to a file with encryption.

    Args:
        identity: IdentityManager instance to save
        filepath: Path where to save the identity
        password: Password to encrypt the private key. If None, no encryption.
        overwrite: If True, overwrites existing file

    Raises:
        HashedCryptoError: If saving fails
        FileExistsError: If file exists and overwrite=False

    Example:
        >>> identity = IdentityManager()
        >>> save_identity(identity, "./secrets/agent.pem", "my_password")
    """
    path = Path(filepath)

    # Check if file already exists
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Identity file already exists: {filepath}. "
            "Use overwrite=True to replace it."
        )

    try:
        # Create parent directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Export private key (encrypted if password provided)
        password_bytes = password.encode("utf-8") if password else None
        private_key_pem = identity.export_private_key(password=password_bytes)

        # Write to file
        path.write_bytes(private_key_pem)

        # Set secure file permissions (owner read/write only)
        os.chmod(filepath, 0o600)

        logger.info(f"Identity saved to {filepath} (permissions: 0600)")
        logger.debug(f"Public key: {identity.public_key_hex}")

    except Exception as e:
        raise HashedCryptoError(
            f"Failed to save identity to {filepath}: {str(e)}"
        ) from e


def load_identity(
    filepath: str,
    password: Optional[str] = None,
) -> IdentityManager:
    """
    Load an identity from a file.

    Args:
        filepath: Path to the identity file
        password: Password to decrypt the private key (if encrypted)

    Returns:
        IdentityManager instance loaded from file

    Raises:
        HashedCryptoError: If loading fails
        FileNotFoundError: If file doesn't exist

    Example:
        >>> identity = load_identity("./secrets/agent.pem", "my_password")
        >>> print(identity.public_key_hex)
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"Identity file not found: {filepath}")

    try:
        # Read private key from file
        private_key_pem = path.read_bytes()

        # Load and decrypt
        password_bytes = password.encode("utf-8") if password else None
        identity = IdentityManager.from_private_key_bytes(
            private_key_pem, password=password_bytes
        )

        logger.info(f"Identity loaded from {filepath}")
        logger.debug(f"Public key: {identity.public_key_hex}")

        return identity

    except Exception as e:
        raise HashedCryptoError(
            f"Failed to load identity from {filepath}: {str(e)}"
        ) from e


def verify_identity_file(filepath: str, password: Optional[str] = None) -> bool:
    """
    Verify that an identity file is valid and can be loaded.

    This is useful for health checks or validation during startup.

    Args:
        filepath: Path to the identity file
        password: Password to decrypt (if encrypted)

    Returns:
        True if file is valid and can be loaded, False otherwise

    Example:
        >>> if verify_identity_file("./secrets/agent.pem", "password"):
        ...     print("Identity file is valid")
        ... else:
        ...     print("Identity file is corrupted or password is wrong")
    """
    try:
        load_identity(filepath, password)
        return True
    except Exception as e:
        logger.warning(f"Identity verification failed: {e}")
        return False


def generate_secure_password(length: int = 32) -> str:
    """
    Generate a cryptographically secure random password.

    This can be used to generate passwords for identity encryption.

    Args:
        length: Length of the password (default: 32)

    Returns:
        Secure random password

    Example:
        >>> password = generate_secure_password()
        >>> identity = IdentityManager()
        >>> save_identity(identity, "./secrets/agent.pem", password)
    """
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password
