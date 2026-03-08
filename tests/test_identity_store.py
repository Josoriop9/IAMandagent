"""
Tests for identity persistence module.
"""

import os
import tempfile
from pathlib import Path

import pytest

from hashed import (
    HashedCryptoError,
    IdentityManager,
    export_identity_for_env,
    generate_secure_password,
    load_identity,
    load_identity_from_env,
    load_or_create_identity,
    save_identity,
    verify_identity_file,
)


class TestIdentityStore:
    """Test suite for identity persistence."""

    def test_save_and_load_identity_without_password(self):
        """Test saving and loading identity without encryption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")

            # Create and save identity
            original_identity = IdentityManager()
            original_pubkey = original_identity.public_key_hex

            save_identity(original_identity, filepath, password=None)

            # Verify file exists
            assert Path(filepath).exists()

            # Load identity
            loaded_identity = load_identity(filepath, password=None)

            # Verify it's the same identity
            assert loaded_identity.public_key_hex == original_pubkey

    def test_save_and_load_identity_with_password(self):
        """Test saving and loading identity with encryption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "test_password_123"

            # Create and save identity
            original_identity = IdentityManager()
            original_pubkey = original_identity.public_key_hex

            save_identity(original_identity, filepath, password=password)

            # Verify file exists
            assert Path(filepath).exists()

            # Load identity with correct password
            loaded_identity = load_identity(filepath, password=password)

            # Verify it's the same identity
            assert loaded_identity.public_key_hex == original_pubkey

    def test_load_identity_with_wrong_password(self):
        """Test that loading with wrong password fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "correct_password"
            wrong_password = "wrong_password"

            # Create and save identity
            identity = IdentityManager()
            save_identity(identity, filepath, password=password)

            # Try to load with wrong password
            with pytest.raises(HashedCryptoError):
                load_identity(filepath, password=wrong_password)

    def test_load_or_create_identity_creates_new(self):
        """Test that load_or_create_identity creates new identity if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "test_password"

            # File doesn't exist yet
            assert not Path(filepath).exists()

            # Load or create (should create)
            identity = load_or_create_identity(filepath, password=password)

            # Verify file was created
            assert Path(filepath).exists()

            # Verify we got an identity
            assert identity.public_key_hex is not None

    def test_load_or_create_identity_loads_existing(self):
        """Test that load_or_create_identity loads existing identity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "test_password"

            # Create identity first time
            first_identity = load_or_create_identity(filepath, password=password)
            first_pubkey = first_identity.public_key_hex

            # Load identity second time (should load, not create)
            second_identity = load_or_create_identity(filepath, password=password)
            second_pubkey = second_identity.public_key_hex

            # Verify it's the same identity
            assert first_pubkey == second_pubkey

    def test_save_identity_overwrite_protection(self):
        """Test that save_identity doesn't overwrite by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")

            # Create and save first identity
            identity1 = IdentityManager()
            save_identity(identity1, filepath)

            # Try to save another identity without overwrite
            identity2 = IdentityManager()
            with pytest.raises(FileExistsError):
                save_identity(identity2, filepath, overwrite=False)

    def test_save_identity_with_overwrite(self):
        """Test that save_identity can overwrite with flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")

            # Create and save first identity
            identity1 = IdentityManager()
            pubkey1 = identity1.public_key_hex
            save_identity(identity1, filepath)

            # Save another identity with overwrite=True
            identity2 = IdentityManager()
            pubkey2 = identity2.public_key_hex
            save_identity(identity2, filepath, overwrite=True)

            # Load and verify it's the second identity
            loaded = load_identity(filepath)
            assert loaded.public_key_hex == pubkey2
            assert loaded.public_key_hex != pubkey1

    def test_verify_identity_file_valid(self):
        """Test verify_identity_file with valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "test_password"

            # Create identity
            identity = IdentityManager()
            save_identity(identity, filepath, password=password)

            # Verify it
            assert verify_identity_file(filepath, password=password) is True

    def test_verify_identity_file_invalid_password(self):
        """Test verify_identity_file with wrong password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "correct_password"
            wrong_password = "wrong_password"

            # Create identity
            identity = IdentityManager()
            save_identity(identity, filepath, password=password)

            # Verify with wrong password
            assert verify_identity_file(filepath, password=wrong_password) is False

    def test_verify_identity_file_missing(self):
        """Test verify_identity_file with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "nonexistent.pem")

            # Verify missing file
            assert verify_identity_file(filepath) is False

    def test_generate_secure_password(self):
        """Test secure password generation."""
        # Generate password
        password = generate_secure_password()

        # Verify length (default 32)
        assert len(password) == 32

        # Verify it contains various character types
        assert any(c.isalpha() for c in password)
        assert any(c.isdigit() for c in password)

        # Generate with custom length
        password_short = generate_secure_password(length=16)
        assert len(password_short) == 16

        # Verify passwords are different (randomness)
        password2 = generate_secure_password()
        assert password != password2

    def test_file_permissions(self):
        """Test that saved identity files have secure permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")

            # Create and save identity
            identity = IdentityManager()
            save_identity(identity, filepath)

            # Check file permissions (should be 0600 = owner read/write only)
            stat_info = os.stat(filepath)
            permissions = stat_info.st_mode & 0o777
            assert permissions == 0o600

    def test_load_or_create_with_create_if_missing_false(self):
        """Test load_or_create_identity with create_if_missing=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")

            # Try to load non-existent file with create_if_missing=False
            with pytest.raises(FileNotFoundError):
                load_or_create_identity(
                    filepath, password="test", create_if_missing=False
                )

    def test_signature_persistence(self):
        """Test that signatures remain valid after save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_key.pem")
            password = "test_password"
            message = "test message for signing"

            # Create identity and sign a message
            original_identity = IdentityManager()
            signature = original_identity.sign_message(message)

            # Save identity
            save_identity(original_identity, filepath, password=password)

            # Load identity
            loaded_identity = load_identity(filepath, password=password)

            # Verify the signature with loaded identity
            assert loaded_identity.verify_signature(message, signature)

    def test_directory_creation(self):
        """Test that save_identity creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create path with nested directories that don't exist
            filepath = os.path.join(tmpdir, "deep", "nested", "path", "test_key.pem")

            # Save identity (should create all parent directories)
            identity = IdentityManager()
            save_identity(identity, filepath)

            # Verify file exists
            assert Path(filepath).exists()

            # Verify parent directories were created
            assert Path(filepath).parent.exists()


# ============================================================================
# Tests for cloud/env-var identity loading (load_identity_from_env,
# export_identity_for_env) — added 2026-03-08 for cloud deployment support.
# ============================================================================

class TestLoadIdentityFromEnv:
    """Tests for load_identity_from_env() — HASHED_AGENT_PRIVATE_KEY support."""

    def test_returns_none_when_env_var_not_set(self, monkeypatch):
        """Should return None if HASHED_AGENT_PRIVATE_KEY is not set."""
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY", raising=False)
        result = load_identity_from_env()
        assert result is None

    def test_loads_valid_unencrypted_key_from_env(self, monkeypatch):
        """Round-trip: save a key, base64-encode it, set env var, load back."""
        import base64

        # 1. Create a fresh identity
        original = IdentityManager()
        pem_bytes = original.export_private_key(password=None)

        # 2. Encode as base64 (simulating what the CLI does)
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        # 3. Set env var
        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", raising=False)

        # 4. Load from env
        loaded = load_identity_from_env()

        assert loaded is not None
        # Same public key → same underlying private key
        assert loaded.public_key_hex == original.public_key_hex

    def test_loads_encrypted_key_with_password_from_env(self, monkeypatch):
        """Should decrypt the key using HASHED_AGENT_PRIVATE_KEY_PASSWORD."""
        import base64

        original = IdentityManager()
        password = "super-secret-123"
        pem_bytes = original.export_private_key(password=password.encode())
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", password)

        loaded = load_identity_from_env()

        assert loaded is not None
        assert loaded.public_key_hex == original.public_key_hex

    def test_raises_on_invalid_base64(self, monkeypatch):
        """Should raise ValueError with helpful message for bad base64."""
        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", "this-is-not-valid-base64!!!")
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", raising=False)

        with pytest.raises(ValueError, match="not valid base64"):
            load_identity_from_env()

    def test_raises_on_wrong_password(self, monkeypatch):
        """Should raise ValueError when password is wrong."""
        import base64

        original = IdentityManager()
        pem_bytes = original.export_private_key(password=b"correct-password")
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", "wrong-password")

        with pytest.raises(ValueError, match="Failed to load identity"):
            load_identity_from_env()

    def test_loaded_identity_can_sign_and_verify(self, monkeypatch):
        """Identity loaded from env var should be fully functional."""
        import base64

        original = IdentityManager()
        pem_bytes = original.export_private_key(password=None)
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", raising=False)

        loaded = load_identity_from_env()
        assert loaded is not None

        message = "test-message-for-signing"
        signature = loaded.sign_message(message)

        # Verify with the loaded key
        assert loaded.verify_signature(message, signature)
        # Also verifiable with the original (same underlying key)
        assert original.verify_signature(message, signature)


class TestExportIdentityForEnv:
    """Tests for export_identity_for_env() — CLI helper for cloud setup."""

    def test_returns_valid_base64_string(self, tmp_path):
        """Should return a non-empty base64 string."""
        import base64

        # Write a test PEM file
        identity = IdentityManager()
        pem_file = tmp_path / "agent.pem"
        pem_file.write_bytes(identity.export_private_key(password=None))

        result = export_identity_for_env(str(pem_file))

        assert isinstance(result, str)
        assert len(result) > 0
        # Must be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_round_trip_with_load_identity_from_env(self, tmp_path, monkeypatch):
        """export_for_env → set env var → load_from_env → same public key."""
        # Create and save identity
        original = IdentityManager()
        pem_file = tmp_path / "agent.pem"
        pem_file.write_bytes(original.export_private_key(password=None))

        # Export to base64
        b64 = export_identity_for_env(str(pem_file))

        # Set env var and load back
        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", raising=False)

        loaded = load_identity_from_env()

        assert loaded is not None
        assert loaded.public_key_hex == original.public_key_hex

    def test_raises_for_missing_file(self):
        """Should raise FileNotFoundError for non-existent path."""
        with pytest.raises(FileNotFoundError):
            export_identity_for_env("/tmp/nonexistent_agent_xyz.pem")

    def test_output_has_no_newlines(self, tmp_path):
        """base64 output must be single-line (safe for env var assignment)."""
        identity = IdentityManager()
        pem_file = tmp_path / "agent.pem"
        pem_file.write_bytes(identity.export_private_key(password=None))

        result = export_identity_for_env(str(pem_file))

        assert "\n" not in result
        assert "\r" not in result


class TestHashedCoreEnvIdentity:
    """Tests that HashedCore auto-loads identity from HASHED_AGENT_PRIVATE_KEY."""

    def test_core_uses_env_identity_when_set(self, monkeypatch):
        """HashedCore should use env var identity when no explicit identity given."""
        import base64
        from hashed.core import HashedCore

        original = IdentityManager()
        pem_bytes = original.export_private_key(password=None)
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)
        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY_PASSWORD", raising=False)

        core = HashedCore(agent_name="test-env-agent")

        # Should have the same public key as the one we encoded
        assert core.identity.public_key_hex == original.public_key_hex

    def test_core_explicit_identity_overrides_env(self, monkeypatch):
        """Explicit identity= parameter should override HASHED_AGENT_PRIVATE_KEY."""
        import base64
        from hashed.core import HashedCore

        env_identity = IdentityManager()
        pem_bytes = env_identity.export_private_key(password=None)
        b64 = base64.b64encode(pem_bytes).decode("ascii")

        monkeypatch.setenv("HASHED_AGENT_PRIVATE_KEY", b64)

        explicit_identity = IdentityManager()  # different key
        core = HashedCore(agent_name="test-explicit", identity=explicit_identity)

        # Explicit identity takes priority over env var
        assert core.identity.public_key_hex == explicit_identity.public_key_hex
        assert core.identity.public_key_hex != env_identity.public_key_hex

    def test_core_generates_ephemeral_identity_when_no_env(self, monkeypatch):
        """HashedCore should generate a new identity when env var is not set."""
        import base64
        from hashed.core import HashedCore

        monkeypatch.delenv("HASHED_AGENT_PRIVATE_KEY", raising=False)

        core = HashedCore(agent_name="test-ephemeral")

        # Should have a valid identity (just not from env var)
        assert len(core.identity.public_key_hex) == 64  # Ed25519 = 32 bytes = 64 hex chars
