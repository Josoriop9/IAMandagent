"""
Identity management module using Ed25519 cryptographic signatures.

This module provides identity management with digital signatures for
message authentication and verification.
"""

import os
import warnings
from datetime import datetime, timezone
from time import time_ns
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from hashed.exceptions import HashedCryptoError


class IdentityManager:
    """
    Identity manager using Ed25519 signatures.

    This class handles cryptographic identity operations including
    key generation, message signing, and signature verification.
    """

    def __init__(self, private_key: Optional[Ed25519PrivateKey] = None) -> None:
        """
        Initialize the identity manager.

        Args:
            private_key: Optional existing private key. If None, generates a new one.
        """
        if private_key is None:
            self._private_key = Ed25519PrivateKey.generate()
        else:
            self._private_key = private_key

        self._public_key = self._private_key.public_key()

    @property
    def public_key(self) -> Ed25519PublicKey:
        """Get the public key."""
        return self._public_key

    @property
    def public_key_bytes(self) -> bytes:
        """Get the public key as bytes."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def public_key_hex(self) -> str:
        """Get the public key as hexadecimal string."""
        return self.public_key_bytes.hex()

    def sign_message(self, message: str) -> bytes:
        """
        Sign a message using the private key.

        Args:
            message: Message to sign

        Returns:
            Signature as bytes

        Raises:
            HashedCryptoError: If signing fails

        Example:
            >>> identity = IdentityManager()
            >>> signature = identity.sign_message("Hello, World!")
        """
        try:
            message_bytes = message.encode("utf-8")
            signature = self._private_key.sign(message_bytes)
            return signature
        except Exception as e:
            raise HashedCryptoError(f"Failed to sign message: {str(e)}") from e

    def verify_signature(
        self,
        message: str,
        signature: bytes,
        public_key: Optional[Ed25519PublicKey] = None,
    ) -> bool:
        """
        Verify a message signature.

        Args:
            message: Original message
            signature: Signature to verify
            public_key: Public key to verify against. If None, uses own public key.

        Returns:
            True if signature is valid, False otherwise

        Example:
            >>> identity = IdentityManager()
            >>> signature = identity.sign_message("test")
            >>> is_valid = identity.verify_signature("test", signature)
            >>> assert is_valid
        """
        try:
            key = public_key or self._public_key
            message_bytes = message.encode("utf-8")
            key.verify(signature, message_bytes)
            return True
        except Exception:
            return False

    def sign_data(self, data: dict) -> dict:
        """
        Sign structured data and return it with signature and metadata.

        .. deprecated::
            Use :meth:`sign_operation` instead, which produces a canonical
            payload conforming to SPEC §2.1 (includes nonce, timestamp_ns,
            version and agent_id for replay-attack protection).

        Args:
            data: Dictionary to sign

        Returns:
            Dictionary with original data plus signature and metadata

        Example:
            >>> identity = IdentityManager()
            >>> signed = identity.sign_data({"action": "transfer", "amount": 100})
        """
        import json

        warnings.warn(
            "sign_data() is deprecated and will be removed in a future release. "
            "Use sign_operation() instead, which produces a SPEC §2.1-compliant "
            "canonical payload with nonce and timestamp_ns for replay protection.",
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            # Create canonical JSON representation
            data_json = json.dumps(data, sort_keys=True)
            signature = self.sign_message(data_json)

            return {
                "data": data,
                "signature": signature.hex(),
                "public_key": self.public_key_hex,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            raise HashedCryptoError(f"Failed to sign data: {str(e)}") from e

    @staticmethod
    def verify_signed_data(signed_data: dict) -> bool:
        """
        Verify signed data structure.

        Args:
            signed_data: Dictionary with data, signature, and public_key fields

        Returns:
            True if signature is valid, False otherwise

        Example:
            >>> identity = IdentityManager()
            >>> signed = identity.sign_data({"test": "data"})
            >>> is_valid = IdentityManager.verify_signed_data(signed)
        """
        import json

        try:
            data = signed_data["data"]
            signature = bytes.fromhex(signed_data["signature"])
            public_key_bytes = bytes.fromhex(signed_data["public_key"])

            # Reconstruct public key
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Verify signature
            data_json = json.dumps(data, sort_keys=True)
            message_bytes = data_json.encode("utf-8")
            public_key.verify(signature, message_bytes)
            return True
        except Exception:
            return False

    def sign_operation(
        self,
        operation: str,
        amount: Optional[float] = None,
        context: Optional[dict] = None,
        status: str = "pending",
    ) -> dict:
        """
        Sign an agent operation producing a SPEC §2.1-compliant canonical payload.

        Constructs a deterministic canonical payload with a CSPRNG nonce and
        nanosecond timestamp to provide replay-attack protection as specified in
        SPEC §2.1–2.3.

        Args:
            operation: Tool/operation name as registered in the PolicyEngine.
            amount: Optional numeric amount for rate-limited operations.
            context: Sanitized execution context (no secrets, no PII).
                     Defaults to an empty dict.
            status: Operation lifecycle status. Default is ``"pending"`` for
                    pre-execution guard checks.

        Returns:
            A dict with four keys:
            - ``"payload"``   – the canonical payload dict (SPEC §2.1)
            - ``"canonical"`` – the JSON-serialised string that was signed
            - ``"signature"`` – Ed25519 signature as a 128-char hex string
            - ``"public_key"``– agent_id (64-char hex public key)

        Raises:
            HashedCryptoError: If signing fails.

        Example:
            >>> identity = IdentityManager()
            >>> signed = identity.sign_operation("send_email", amount=None)
            >>> IdentityManager.verify_signed_operation(signed)
            True
        """
        import json

        try:
            payload: dict = {
                "version": 1,
                "agent_id": self.public_key_hex,
                "operation": operation,
                "amount": amount,
                "timestamp_ns": time_ns(),
                "nonce": os.urandom(16).hex(),
                "status": status,
                "context": context if context is not None else {},
            }

            # §2.2 Canonicalization — sort_keys, no whitespace, ASCII-safe
            canonical: str = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            canonical_bytes: bytes = canonical.encode("utf-8")

            # §2.3 Signature production
            signature_bytes: bytes = self._private_key.sign(canonical_bytes)

            return {
                "payload": payload,
                "canonical": canonical,
                "signature": signature_bytes.hex(),
                "public_key": self.public_key_hex,
            }
        except Exception as e:
            raise HashedCryptoError(f"Failed to sign operation: {str(e)}") from e

    @staticmethod
    def verify_signed_operation(signed: dict) -> bool:
        """
        Verify a signed operation produced by :meth:`sign_operation`.

        Reconstructs the public key from the embedded ``public_key`` field,
        re-encodes the ``canonical`` string to UTF-8, and verifies the Ed25519
        signature.

        Args:
            signed: Dict as returned by :meth:`sign_operation` — must contain
                    ``"canonical"``, ``"signature"``, and ``"public_key"`` keys.

        Returns:
            ``True`` if the signature is cryptographically valid, ``False``
            for any tampered, malformed, or missing field.

        Example:
            >>> identity = IdentityManager()
            >>> signed = identity.sign_operation("read_file")
            >>> IdentityManager.verify_signed_operation(signed)
            True
        """
        try:
            canonical_bytes = signed["canonical"].encode("utf-8")
            signature = bytes.fromhex(signed["signature"])
            public_key_bytes = bytes.fromhex(signed["public_key"])

            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, canonical_bytes)
            return True
        except Exception:
            return False

    def export_private_key(self, password: Optional[bytes] = None) -> bytes:
        """
        Export the private key in PEM format.

        Args:
            password: Optional password to encrypt the private key

        Returns:
            Private key in PEM format

        Raises:
            HashedCryptoError: If export fails
        """
        try:
            if password:
                from cryptography.hazmat.primitives import serialization as ser

                encryption = ser.BestAvailableEncryption(password)
            else:
                from cryptography.hazmat.primitives import serialization as ser

                encryption = ser.NoEncryption()

            return self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption,
            )
        except Exception as e:
            raise HashedCryptoError(f"Failed to export private key: {str(e)}") from e

    @classmethod
    def from_private_key_bytes(
        cls, private_key_bytes: bytes, password: Optional[bytes] = None
    ) -> "IdentityManager":
        """
        Create an IdentityManager from private key bytes.

        Args:
            private_key_bytes: Private key in PEM format
            password: Optional password if key is encrypted

        Returns:
            IdentityManager instance

        Raises:
            HashedCryptoError: If key loading fails
        """
        try:
            private_key = serialization.load_pem_private_key(
                private_key_bytes, password=password
            )
            if not isinstance(private_key, Ed25519PrivateKey):
                raise HashedCryptoError("Invalid key type, expected Ed25519")
            return cls(private_key=private_key)
        except Exception as e:
            raise HashedCryptoError(f"Failed to load private key: {str(e)}") from e
