"""
Identity management module using Ed25519 cryptographic signatures.

This module provides identity management with digital signatures for
message authentication and verification.
"""

from datetime import datetime
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
            raise HashedCryptoError(
                f"Failed to sign message: {str(e)}"
            ) from e

    def verify_signature(
        self, message: str, signature: bytes, public_key: Optional[Ed25519PublicKey] = None
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

        Args:
            data: Dictionary to sign

        Returns:
            Dictionary with original data plus signature and metadata

        Example:
            >>> identity = IdentityManager()
            >>> signed = identity.sign_data({"action": "transfer", "amount": 100})
        """
        import json

        try:
            # Create canonical JSON representation
            data_json = json.dumps(data, sort_keys=True)
            signature = self.sign_message(data_json)

            return {
                "data": data,
                "signature": signature.hex(),
                "public_key": self.public_key_hex,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            raise HashedCryptoError(
                f"Failed to sign data: {str(e)}"
            ) from e

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
            raise HashedCryptoError(
                f"Failed to export private key: {str(e)}"
            ) from e

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
            raise HashedCryptoError(
                f"Failed to load private key: {str(e)}"
            ) from e
