"""
Hashing operations using the Strategy pattern.

This module implements the Strategy pattern to provide flexible
hashing algorithms while maintaining a consistent interface.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hashed.exceptions import HashedCryptoError
from hashed.models import HashAlgorithm, HashRequest, HashResponse


class HashStrategy(Protocol):
    """
    Protocol defining the interface for hash strategies.

    This follows the Interface Segregation Principle by defining
    a minimal, focused interface.
    """

    def compute_hash(self, data: bytes) -> str:
        """
        Compute hash for the given data.

        Args:
            data: Bytes to hash

        Returns:
            Hexadecimal string representation of the hash
        """
        ...


class SHA256Strategy:
    """Strategy for SHA-256 hashing."""

    def compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash."""
        return hashlib.sha256(data).hexdigest()


class SHA512Strategy:
    """Strategy for SHA-512 hashing."""

    def compute_hash(self, data: bytes) -> str:
        """Compute SHA-512 hash."""
        return hashlib.sha512(data).hexdigest()


class Blake2bStrategy:
    """Strategy for BLAKE2b hashing."""

    def compute_hash(self, data: bytes) -> str:
        """Compute BLAKE2b hash."""
        return hashlib.blake2b(data).hexdigest()


class Blake2sStrategy:
    """Strategy for BLAKE2s hashing."""

    def compute_hash(self, data: bytes) -> str:
        """Compute BLAKE2s hash."""
        return hashlib.blake2s(data).hexdigest()


class Hasher:
    """
    Main hasher class implementing the Strategy pattern.

    This class follows the Open/Closed Principle by being open for
    extension (new strategies) but closed for modification.
    """

    def __init__(self) -> None:
        """Initialize the hasher with available strategies."""
        self._strategies: dict[str, HashStrategy] = {
            HashAlgorithm.SHA256.value: SHA256Strategy(),
            HashAlgorithm.SHA512.value: SHA512Strategy(),
            HashAlgorithm.BLAKE2B.value: Blake2bStrategy(),
            HashAlgorithm.BLAKE2S.value: Blake2sStrategy(),
        }

    def register_strategy(self, algorithm: str, strategy: HashStrategy) -> None:
        """
        Register a new hash strategy.

        Args:
            algorithm: Algorithm identifier
            strategy: Hash strategy implementation

        This method demonstrates the Open/Closed Principle by allowing
        extension without modifying existing code.
        """
        self._strategies[algorithm] = strategy

    def hash(self, request: HashRequest) -> HashResponse:
        """
        Compute hash based on the request.

        Args:
            request: Hash request containing data and parameters

        Returns:
            HashResponse: Response containing the computed hash

        Raises:
            HashedCryptoError: If hashing fails
        """
        try:
            # Get the appropriate strategy
            strategy = self._strategies.get(request.algorithm)
            if not strategy:
                raise HashedCryptoError(
                    f"Unsupported algorithm: {request.algorithm}",
                    details={"algorithm": request.algorithm},
                )

            # Encode the data
            data_bytes = request.data.encode(request.encoding)

            # Apply salt if provided
            if request.salt:
                salt_bytes = request.salt.encode(request.encoding)
                data_bytes = salt_bytes + data_bytes

            # Compute the hash
            hash_value = strategy.compute_hash(data_bytes)

            # Create and return response
            return HashResponse(
                hash_value=hash_value,
                algorithm=request.algorithm,
                metadata={
                    "encoding": request.encoding,
                    "salted": request.salt is not None,
                    "data_length": len(request.data),
                },
            )

        except Exception as e:
            if isinstance(e, HashedCryptoError):
                raise
            raise HashedCryptoError(
                f"Failed to compute hash: {str(e)}",
                details={"algorithm": request.algorithm},
            ) from e

    def derive_key(
        self,
        password: str,
        salt: bytes,
        length: int = 32,
        iterations: int = 100000,
    ) -> bytes:
        """
        Derive a cryptographic key from a password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation
            length: Desired key length in bytes
            iterations: Number of iterations

        Returns:
            Derived key as bytes

        Raises:
            HashedCryptoError: If key derivation fails
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=length,
                salt=salt,
                iterations=iterations,
            )
            return kdf.derive(password.encode())
        except Exception as e:
            raise HashedCryptoError(
                f"Failed to derive key: {str(e)}"
            ) from e
