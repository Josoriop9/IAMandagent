"""
Example: Agent with Persistent Identity

This example demonstrates how to use persistent identity for agents,
allowing them to maintain the same identity across restarts.
"""

import asyncio
import os
from pathlib import Path

from hashed import HashedConfig, HashedCore, load_or_create_identity


async def main():
    """Main example function."""
    
    # ============================================================
    # STEP 1: Load or Create Persistent Identity
    # ============================================================
    
    print("=" * 60)
    print("PERSISTENT IDENTITY EXAMPLE")
    print("=" * 60)
    
    # Define where to store the identity file
    identity_file = "./secrets/agent_key.pem"
    
    # Get password from environment variable (RECOMMENDED)
    # In production, use a secrets manager (AWS Secrets, HashiCorp Vault, etc.)
    password = os.getenv("HASHED_IDENTITY_PASSWORD", "demo_password_123")
    
    print(f"\n1. Loading or creating identity from: {identity_file}")
    print(f"   (Password from env var: HASHED_IDENTITY_PASSWORD)")
    
    # This will:
    # - If file exists: load the existing identity
    # - If file doesn't exist: generate new identity and save it
    identity = load_or_create_identity(
        filepath=identity_file,
        password=password,
    )
    
    print(f"   ✓ Identity loaded/created")
    print(f"   Public Key: {identity.public_key_hex[:16]}...{identity.public_key_hex[-8:]}")
    
    # Check if this is first run or subsequent run
    identity_path = Path(identity_file)
    if identity_path.exists():
        import os
        import time
        created_time = os.path.getctime(identity_file)
        age_seconds = time.time() - created_time
        if age_seconds < 5:
            print(f"   → This is a NEW identity (just created)")
        else:
            print(f"   → This identity was LOADED from disk (created {int(age_seconds)}s ago)")
    
    # ============================================================
    # STEP 2: Create HashedCore with Persistent Identity
    # ============================================================
    
    print(f"\n2. Creating HashedCore with persistent identity")
    
    # Configuration (from environment variables)
    config = HashedConfig(
        backend_url=os.getenv("HASHED_BACKEND_URL", "http://localhost:8000"),
        api_key=os.getenv("HASHED_API_KEY"),
        enable_auto_sync=True,
        sync_interval=60,  # Sync policies every 60 seconds
    )
    
    # Create core with the persistent identity
    core = HashedCore(
        config=config,
        identity=identity,  # ← Use persistent identity
        agent_name="Persistent Demo Agent",
        agent_type="demo",
    )
    
    print(f"   ✓ Core created")
    
    # ============================================================
    # STEP 3: Initialize (registers agent if needed)
    # ============================================================
    
    print(f"\n3. Initializing core (auto-registers agent)")
    
    try:
        await core.initialize()
        print(f"   ✓ Core initialized")
        print(f"   Agent registered with backend: {config.backend_url}")
    except Exception as e:
        print(f"   ⚠ Initialization warning: {e}")
        print(f"   (This is OK if backend is not running)")
    
    # ============================================================
    # STEP 4: Define and Use Guarded Operations
    # ============================================================
    
    print(f"\n4. Setting up guarded operations")
    
    # Add local policy
    core.policy_engine.add_policy(
        tool_name="send_email",
        max_amount=100.0,  # Max 100 emails
        allowed=True,
    )
    print(f"   ✓ Policy added: send_email (max 100)")
    
    # Define guarded function
    @core.guard("send_email", amount_param="count")
    async def send_email(to: str, subject: str, count: int = 1):
        """Send email with governance."""
        print(f"      → Sending {count} email(s) to {to}")
        print(f"         Subject: {subject}")
        return {"status": "sent", "count": count, "to": to}
    
    # ============================================================
    # STEP 5: Execute Operations
    # ============================================================
    
    print(f"\n5. Executing guarded operations")
    
    # This will:
    # - Sign the operation with the identity
    # - Validate against policies (local + backend)
    # - Execute if allowed
    # - Log to backend
    
    try:
        result = await send_email(
            to="user@example.com",
            subject="Test Email",
            count=5
        )
        print(f"   ✓ Operation succeeded: {result}")
    except Exception as e:
        print(f"   ✗ Operation failed: {e}")
    
    # Try operation that violates policy
    print(f"\n6. Testing policy violation")
    try:
        result = await send_email(
            to="spam@example.com",
            subject="Bulk Email",
            count=150  # Exceeds max_amount=100
        )
        print(f"   ✗ Should have been blocked!")
    except Exception as e:
        print(f"   ✓ Correctly blocked: {e}")
    
    # ============================================================
    # STEP 6: Verify Identity Persistence
    # ============================================================
    
    print(f"\n7. Identity persistence verification")
    print(f"   Public key (this stays the same across restarts):")
    print(f"   {identity.public_key_hex}")
    print(f"\n   💡 Run this script again - you'll see the SAME public key!")
    print(f"   💡 The agent will maintain its identity and audit trail.")
    
    # ============================================================
    # STEP 7: Cleanup
    # ============================================================
    
    print(f"\n8. Shutting down")
    await core.shutdown()
    print(f"   ✓ Core shutdown complete")
    
    print(f"\n{'=' * 60}")
    print(f"EXAMPLE COMPLETE")
    print(f"{'=' * 60}")
    print(f"\n📁 Identity saved to: {identity_file}")
    print(f"🔐 Protected with password from: HASHED_IDENTITY_PASSWORD")
    print(f"🔑 Public Key: {identity.public_key_hex[:16]}...{identity.public_key_hex[-8:]}")
    print(f"\n✅ The agent will maintain this identity on next run!\n")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
