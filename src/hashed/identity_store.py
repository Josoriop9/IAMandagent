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

        # Security: warn when the key is stored without password encryption.
        # The file has 0600 permissions (owner-only), but an unencrypted PEM
        # can be read by any process running as the same OS user or by root.
        # Pass a strong, unique password to protect against local privilege
        # escalation and disk forensics.
        if not password:
            logger.warning(
                "⚠️  Saving Ed25519 private key WITHOUT password encryption "
                "to %s. Pass a password to save_identity() for defence against "
                "local privilege escalation (OWASP ASVS 4.0 L2 — C-10).",
                filepath,
            )

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


# ── Default hashed directory ──────────────────────────────────────────────────
_HASHED_DIR = Path.home() / ".hashed"
_IDENTITY_PASSWORD_FILE = _HASHED_DIR / "identity_password"


def get_or_create_identity_password() -> str:
    """
    Return the identity password using this precedence:

    1. ``HASHED_IDENTITY_PASSWORD`` environment variable  (set by the user)
    2. ``~/.hashed/identity_password`` file              (auto-generated on first run)
    3. Auto-generate → save to ``~/.hashed/identity_password`` (chmod 0600)

    This means developers never need to manage this credential manually —
    Hashed handles it transparently while still keeping the Ed25519 private
    key encrypted on disk.

    Power users can override by setting ``HASHED_IDENTITY_PASSWORD`` in their
    ``.env`` file.

    Returns:
        The password string to use for identity encryption/decryption.

    Example::

        from hashed.identity_store import get_or_create_identity_password, load_or_create_identity

        pwd = get_or_create_identity_password()
        identity = load_or_create_identity("./secrets/agent.pem", password=pwd)
    """
    import secrets as _secrets

    # 1. Explicit env var takes highest priority
    env_password = os.getenv("HASHED_IDENTITY_PASSWORD")
    if env_password:
        logger.debug("Using HASHED_IDENTITY_PASSWORD from environment variable.")
        return env_password

    # 2. Previously auto-generated password saved to disk
    if _IDENTITY_PASSWORD_FILE.exists():
        try:
            password = _IDENTITY_PASSWORD_FILE.read_text(encoding="utf-8").strip()
            if password:
                logger.debug(
                    "Loaded identity password from %s", _IDENTITY_PASSWORD_FILE
                )
                return password
        except OSError as exc:
            logger.warning("Could not read %s: %s", _IDENTITY_PASSWORD_FILE, exc)

    # 3. Generate a new secure password and persist it
    password = _secrets.token_hex(32)  # 256-bit → 64 hex chars

    try:
        _HASHED_DIR.mkdir(parents=True, exist_ok=True)
        _IDENTITY_PASSWORD_FILE.write_text(password, encoding="utf-8")
        os.chmod(_IDENTITY_PASSWORD_FILE, 0o600)
        logger.info(
            "Auto-generated identity password saved to %s (permissions: 0600). "
            "To override, set HASHED_IDENTITY_PASSWORD in your .env file.",
            _IDENTITY_PASSWORD_FILE,
        )
    except OSError as exc:
        logger.warning(
            "Could not persist identity password to %s: %s. "
            "Set HASHED_IDENTITY_PASSWORD in your .env to avoid this.",
            _IDENTITY_PASSWORD_FILE,
            exc,
        )

    return password


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


def load_identity_from_env() -> Optional["IdentityManager"]:
    """
    Load an agent identity from environment variables.

    Designed for cloud/serverless deployments (Lambda, Cloud Run, Railway,
    Kubernetes) where writing a .pem file to disk is not practical.

    Environment variables
    ---------------------
    HASHED_AGENT_PRIVATE_KEY
        Base64-encoded PEM private key.  Generate it from an existing key:

            # Encode (run once on your dev machine)
            base64 -i ~/.hashed/agents/my-agent.pem | tr -d '\\n'

        Then set that output as the env var in your cloud provider
        (Railway Variables, AWS Secrets Manager, GitHub Secrets, etc.).

    HASHED_AGENT_PRIVATE_KEY_PASSWORD   (optional)
        Password used to decrypt the key if it was saved with encryption.
        Leave unset if the key was saved without a password.

    Returns
    -------
    IdentityManager if HASHED_AGENT_PRIVATE_KEY is set, otherwise None.

    Example
    -------
        # In your agent code (cloud-friendly):
        from hashed.identity_store import load_identity_from_env
        from hashed import HashedCore

        identity = load_identity_from_env()   # None if env var not set
        core = HashedCore(agent_name="prod-agent", identity=identity)
        # HashedCore also checks the env var automatically, so this is
        # equivalent to just: core = HashedCore(agent_name="prod-agent")
    """
    import base64
    import os

    raw_b64 = os.getenv("HASHED_AGENT_PRIVATE_KEY")
    if not raw_b64:
        return None

    try:
        # validate=True rejects any characters not in the base64 alphabet,
        # giving a clear error instead of silently decoding garbage bytes.
        pem_bytes = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise ValueError(
            "HASHED_AGENT_PRIVATE_KEY is not valid base64. "
            "Encode your .pem file with:  base64 -i agent.pem | tr -d '\\n'"
        ) from exc

    password_str = os.getenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD")
    password_bytes: Optional[bytes] = (
        password_str.encode("utf-8") if password_str else None
    )

    try:
        from hashed.identity import IdentityManager  # local import to avoid circular

        identity = IdentityManager.from_private_key_bytes(
            pem_bytes, password=password_bytes
        )
        logger.info(
            "Agent identity loaded from HASHED_AGENT_PRIVATE_KEY env var "
            "(public_key=%s)",
            identity.public_key_hex[:16] + "...",
        )
        return identity
    except Exception as exc:
        raise ValueError(
            f"Failed to load identity from HASHED_AGENT_PRIVATE_KEY: {exc}. "
            "Check that the key is a valid Ed25519 PEM and the password is correct."
        ) from exc


def export_identity_for_env(filepath: str, password: Optional[str] = None) -> str:
    """
    Read a .pem file and return the base64-encoded string ready to set as
    HASHED_AGENT_PRIVATE_KEY in your cloud provider.

    Args:
        filepath: Path to the .pem file (e.g., ~/.hashed/agents/my-agent.pem)
        password: Password used when the key was saved (if any)

    Returns:
        Base64-encoded string (no newlines) ready to paste into env var config.

    Example
    -------
        from hashed.identity_store import export_identity_for_env
        b64 = export_identity_for_env("~/.hashed/agents/my-agent.pem")
        print(f"Set this in Railway Variables:")
        print(f"HASHED_AGENT_PRIVATE_KEY={b64}")
    """
    import base64
    from pathlib import Path

    path = Path(filepath).expanduser()
    pem_bytes = path.read_bytes()
    b64 = base64.b64encode(pem_bytes).decode("ascii")
    logger.info(
        "Exported identity from %s as base64 (%d chars). "
        "Set as HASHED_AGENT_PRIVATE_KEY in your cloud provider.",
        filepath,
        len(b64),
    )
    return b64
