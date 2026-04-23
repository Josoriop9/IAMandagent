"""
Cryptography module for the Hashed SDK.

Provides SHA-256/SHA-512/BLAKE2 hash computation (``Hasher``) used internally
for the WAL hash chain (SPEC §3.2) and the canonical operation fingerprint.
Not the primary public API — most users should use HashedCore and
@core.guard() instead.
"""

from hashed.crypto.hasher import Hasher, HashStrategy

__all__ = ["Hasher", "HashStrategy"]
