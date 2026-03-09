"""
Tests for src/hashed/identity.py — IdentityManager

Covers the lines NOT exercised by other test files:
  - __init__ with provided private_key (else branch, line 45)
  - sign_message() exception path (lines 81-82)
  - verify_signature() with an explicit public_key arg (lines 111-112)
  - sign_data() exception path (lines 141-142)
  - export_private_key() with password (lines 162-178)
  - from_private_key_bytes() invalid key type raises HashedCryptoError (line 209)
  - from_private_key_bytes() generic exception → HashedCryptoError (line 235)
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hashed.exceptions import HashedCryptoError
from hashed.identity import IdentityManager


# ── __init__ ─────────────────────────────────────────────────────────────────


class TestIdentityManagerInit:
    """Tests for IdentityManager.__init__."""

    def test_generates_new_key_when_none_provided(self) -> None:
        """Default constructor generates a fresh Ed25519 key pair."""
        identity = IdentityManager()
        assert identity.public_key_hex
        assert len(identity.public_key_hex) == 64  # 32 bytes → 64 hex chars

    def test_uses_provided_private_key(self) -> None:
        """__init__ with an existing private key reuses it (else branch, line 45)."""
        # Generate a key pair first
        original = IdentityManager()
        private_key = original._private_key

        # Create a second manager using the same key
        reused = IdentityManager(private_key=private_key)

        assert reused.public_key_hex == original.public_key_hex

    def test_two_default_identities_have_different_keys(self) -> None:
        """Each call to IdentityManager() generates a unique key."""
        a = IdentityManager()
        b = IdentityManager()
        assert a.public_key_hex != b.public_key_hex


# ── sign_message() ────────────────────────────────────────────────────────────


class TestSignMessage:
    """Tests for sign_message()."""

    def test_returns_bytes(self) -> None:
        """sign_message() returns bytes."""
        identity = IdentityManager()
        sig = identity.sign_message("hello")
        assert isinstance(sig, bytes)
        assert len(sig) == 64  # Ed25519 signatures are always 64 bytes

    def test_same_message_same_key_produces_same_signature(self) -> None:
        """Ed25519 is deterministic — same key + same message = same signature."""
        identity = IdentityManager()
        assert identity.sign_message("test") == identity.sign_message("test")

    def test_different_messages_different_signatures(self) -> None:
        """Different messages produce different signatures."""
        identity = IdentityManager()
        assert identity.sign_message("a") != identity.sign_message("b")

    def test_sign_message_exception_raises_crypto_error(self) -> None:
        """sign_message() wraps internal exceptions in HashedCryptoError (lines 81-82)."""
        from unittest.mock import MagicMock
        identity = IdentityManager()

        # Replace the C-extension private key with a mock that raises on sign()
        mock_key = MagicMock()
        mock_key.sign = MagicMock(side_effect=RuntimeError("broken"))
        identity._private_key = mock_key

        with pytest.raises(HashedCryptoError):
            identity.sign_message("fail")


# ── verify_signature() ────────────────────────────────────────────────────────


class TestVerifySignature:
    """Tests for verify_signature()."""

    def test_own_signature_is_valid(self) -> None:
        """verify_signature() returns True for a correctly signed message."""
        identity = IdentityManager()
        sig = identity.sign_message("hello world")
        assert identity.verify_signature("hello world", sig) is True

    def test_wrong_message_is_invalid(self) -> None:
        """Signature of 'x' does not verify against 'y'."""
        identity = IdentityManager()
        sig = identity.sign_message("x")
        assert identity.verify_signature("y", sig) is False

    def test_tampered_signature_is_invalid(self) -> None:
        """A tampered signature should fail verification."""
        identity = IdentityManager()
        sig = identity.sign_message("message")
        tampered = b"\x00" * 64
        assert identity.verify_signature("message", tampered) is False

    def test_verify_with_explicit_public_key(self) -> None:
        """verify_signature() with an explicit public_key argument (lines 111-112)."""
        signer = IdentityManager()
        verifier = IdentityManager()   # different identity

        sig = signer.sign_message("cross verify")

        # Verify using signer's public key passed explicitly to verifier
        result = verifier.verify_signature(
            "cross verify", sig, public_key=signer.public_key
        )
        assert result is True

    def test_verify_with_wrong_public_key_returns_false(self) -> None:
        """Verification with the wrong public key returns False."""
        signer = IdentityManager()
        other  = IdentityManager()

        sig = signer.sign_message("secret")

        # Verify with a DIFFERENT public key — must fail
        result = signer.verify_signature("secret", sig, public_key=other.public_key)
        assert result is False


# ── sign_data() ───────────────────────────────────────────────────────────────


class TestSignData:
    """Tests for sign_data()."""

    def test_returns_required_fields(self) -> None:
        """sign_data() result contains data, signature, public_key, timestamp."""
        identity = IdentityManager()
        result = identity.sign_data({"action": "transfer", "amount": 100})

        assert "data" in result
        assert "signature" in result
        assert "public_key" in result
        assert "timestamp" in result

    def test_signature_is_hex_string(self) -> None:
        """The signature field should be a valid hex string."""
        identity = IdentityManager()
        result = identity.sign_data({"k": "v"})
        sig_bytes = bytes.fromhex(result["signature"])
        assert len(sig_bytes) == 64

    def test_signed_data_verifiable(self) -> None:
        """sign_data() output should be verifiable via verify_signed_data()."""
        identity = IdentityManager()
        signed = identity.sign_data({"op": "read", "resource": "config"})
        assert IdentityManager.verify_signed_data(signed) is True

    def test_sign_data_is_canonical(self) -> None:
        """Key order in the dict should not affect the signature."""
        identity = IdentityManager()
        s1 = identity.sign_data({"a": 1, "b": 2})
        s2 = identity.sign_data({"b": 2, "a": 1})
        assert s1["signature"] == s2["signature"]

    def test_sign_data_exception_raises_crypto_error(self) -> None:
        """sign_data() wraps internal errors in HashedCryptoError (lines 141-142)."""
        identity = IdentityManager()

        # Replace C-extension key with a mock that raises on sign()
        mock_key = MagicMock()
        mock_key.sign = MagicMock(side_effect=ValueError("oops"))
        identity._private_key = mock_key

        with pytest.raises(HashedCryptoError):
            identity.sign_data({"x": 1})


# ── verify_signed_data() ──────────────────────────────────────────────────────


class TestVerifySignedData:
    """Tests for the static verify_signed_data()."""

    def test_valid_signed_data_returns_true(self) -> None:
        identity = IdentityManager()
        signed = identity.sign_data({"test": True})
        assert IdentityManager.verify_signed_data(signed) is True

    def test_tampered_signature_returns_false(self) -> None:
        identity = IdentityManager()
        signed = identity.sign_data({"x": 1})
        signed["signature"] = "00" * 64   # all zeros
        assert IdentityManager.verify_signed_data(signed) is False

    def test_tampered_data_returns_false(self) -> None:
        identity = IdentityManager()
        signed = identity.sign_data({"amount": 100})
        signed["data"]["amount"] = 9999   # tamper
        assert IdentityManager.verify_signed_data(signed) is False

    def test_missing_field_returns_false(self) -> None:
        """Incomplete signed_data dict returns False, not an exception."""
        assert IdentityManager.verify_signed_data({"data": {}}) is False


# ── export_private_key() ──────────────────────────────────────────────────────


class TestExportPrivateKey:
    """Tests for export_private_key()."""

    def test_export_without_password_returns_pem(self) -> None:
        """export_private_key() with no password returns PEM bytes."""
        identity = IdentityManager()
        pem = identity.export_private_key()
        assert isinstance(pem, bytes)
        assert b"PRIVATE KEY" in pem

    def test_export_with_password_returns_encrypted_pem(self) -> None:
        """export_private_key() with password returns encrypted PEM (lines 162-178)."""
        identity = IdentityManager()
        pem = identity.export_private_key(password=b"s3cr3t")
        assert isinstance(pem, bytes)
        assert b"PRIVATE KEY" in pem
        # Encrypted PEM starts with ENCRYPTED PRIVATE KEY
        assert b"ENCRYPTED" in pem

    def test_export_then_import_roundtrip_no_password(self) -> None:
        """Export/import without password preserves the key pair."""
        original = IdentityManager()
        pem = original.export_private_key()

        restored = IdentityManager.from_private_key_bytes(pem)
        assert restored.public_key_hex == original.public_key_hex

    def test_export_then_import_roundtrip_with_password(self) -> None:
        """Export/import with password preserves the key pair."""
        original = IdentityManager()
        pem = original.export_private_key(password=b"mypass")

        restored = IdentityManager.from_private_key_bytes(pem, password=b"mypass")
        assert restored.public_key_hex == original.public_key_hex


# ── from_private_key_bytes() ─────────────────────────────────────────────────


class TestFromPrivateKeyBytes:
    """Tests for from_private_key_bytes()."""

    def test_valid_pem_creates_identity(self) -> None:
        """from_private_key_bytes() with valid PEM returns correct identity."""
        original = IdentityManager()
        pem = original.export_private_key()

        restored = IdentityManager.from_private_key_bytes(pem)
        assert restored.public_key_hex == original.public_key_hex

    def test_wrong_password_raises_crypto_error(self) -> None:
        """Wrong password on encrypted PEM raises HashedCryptoError (line 235)."""
        identity = IdentityManager()
        pem = identity.export_private_key(password=b"correct")

        with pytest.raises(HashedCryptoError):
            IdentityManager.from_private_key_bytes(pem, password=b"wrong")

    def test_invalid_pem_raises_crypto_error(self) -> None:
        """Garbage bytes raises HashedCryptoError."""
        with pytest.raises(HashedCryptoError):
            IdentityManager.from_private_key_bytes(b"not a pem")

    def test_wrong_key_type_raises_crypto_error(self) -> None:
        """A non-Ed25519 key type raises HashedCryptoError (line 208-209)."""
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization as ser

        # Generate an ECDSA key (not Ed25519)
        ecdsa_key = ec.generate_private_key(ec.SECP256R1())
        ecdsa_pem = ecdsa_key.private_bytes(
            encoding=ser.Encoding.PEM,
            format=ser.PrivateFormat.PKCS8,
            encryption_algorithm=ser.NoEncryption(),
        )

        with pytest.raises(HashedCryptoError):
            IdentityManager.from_private_key_bytes(ecdsa_pem)


# ── public_key_bytes property ────────────────────────────────────────────────


class TestPublicKeyProperties:
    """Tests for public_key, public_key_bytes, public_key_hex properties."""

    def test_public_key_bytes_is_32_bytes(self) -> None:
        """Ed25519 public key is exactly 32 bytes."""
        identity = IdentityManager()
        assert len(identity.public_key_bytes) == 32

    def test_public_key_hex_is_64_chars(self) -> None:
        """Hex representation of 32 bytes is 64 hex chars."""
        identity = IdentityManager()
        assert len(identity.public_key_hex) == 64
        # All hex characters
        int(identity.public_key_hex, 16)

    def test_public_key_roundtrip(self) -> None:
        """public_key_bytes → hex → back should match."""
        identity = IdentityManager()
        hex_key = identity.public_key_hex
        reconstructed = bytes.fromhex(hex_key)
        assert reconstructed == identity.public_key_bytes
