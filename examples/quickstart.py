"""
Hashed SDK — 30-second Quickstart
==================================

Run these 3 commands, then execute this script:

  pip install hashed-sdk
  hashed signup           # create account (once)
  hashed init             # scaffold agent + .env (once per project)

Then:
  cd examples
  python quickstart.py

What this script demonstrates:
  1. Load identity (auto-generated Ed25519 key pair)
  2. Initialize agent (registers with backend + syncs policies)
  3. Run 3 guarded operations with automatic:
       - Policy enforcement (allow / deny / requires-approval)
       - Cryptographic signature of every operation
       - Immutable audit log entry in the ledger
  4. Show how to view the audit trail
"""

import asyncio
import os

from dotenv import load_dotenv

# Loads HASHED_API_KEY + HASHED_BACKEND_URL from .env (created by 'hashed init')
load_dotenv()

from hashed import HashedConfig, HashedCore, load_or_create_identity  # noqa: E402


async def main() -> None:
    # ── 1. Configuration ──────────────────────────────────────────────────────
    # HashedConfig reads in order:
    #   1. ~/.hashed/credentials.json (set by 'hashed login')
    #   2. Environment variables: HASHED_API_KEY, HASHED_BACKEND_URL
    #   3. .env file in current directory
    config = HashedConfig()

    # ── 2. Identity ───────────────────────────────────────────────────────────
    # Ed25519 key pair — auto-generated on first run, reused on subsequent runs.
    # The private key is encrypted at rest using the password below.
    password = os.getenv("HASHED_IDENTITY_PASSWORD", "change-me-in-production")
    identity = load_or_create_identity("quickstart_agent.pem", password)
    print(f"✓ Identity loaded  pubkey={identity.public_key_hex[:24]}…")

    # ── 3. Initialize ─────────────────────────────────────────────────────────
    # Registers the agent with the backend (idempotent) and syncs policies.
    # All subsequent @core.guard() calls enforce those policies.
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="Quickstart Agent",
        agent_type="demo",
    )
    await core.initialize()
    print("✓ Agent registered and policies synced\n")

    # ── 4. Define guarded operations ─────────────────────────────────────────
    # @core.guard() wraps any async function with:
    #   - Policy check   → allowed / denied / requires-approval
    #   - Ed25519 sign   → cryptographic proof of execution
    #   - Ledger entry   → immutable audit log flushed to backend
    #
    # Define tools INSIDE main() so @core.guard() has a live, initialized core.

    @core.guard("send_notification")
    async def send_notification(recipient: str, message: str) -> dict:
        """Send a notification — governed by Hashed policy."""
        # Replace with your real implementation (e.g., SendGrid, Twilio…)
        return {"status": "sent", "to": recipient, "chars": len(message)}

    @core.guard("read_customer_data")
    async def read_customer_data(customer_id: str) -> dict:
        """Read PII — governed by Hashed policy (data access control)."""
        return {"customer_id": customer_id, "name": "Jane Doe", "tier": "premium"}

    @core.guard("transfer_funds")
    async def transfer_funds(amount: float, currency: str = "USD") -> dict:
        """Transfer funds — Hashed checks amount against your policy limits."""
        return {"status": "transferred", "amount": amount, "currency": currency}

    # ── 5. Execute ────────────────────────────────────────────────────────────
    print("▶  Running guarded operations …\n")

    # Operation A: notification (typically allowed by default policy)
    try:
        result = await send_notification("alice@example.com", "Hello from Hashed!")
        print(f"  ✓  send_notification  → {result}")
    except Exception as exc:
        print(f"  ✗  send_notification  DENIED: {exc}")

    # Operation B: read PII (allowed unless you have a 'read_customer_data: denied' policy)
    try:
        result = await read_customer_data("cust-001")
        print(f"  ✓  read_customer_data → {result}")
    except Exception as exc:
        print(f"  ✗  read_customer_data DENIED: {exc}")

    # Operation C: financial transfer (denied if you have 'transfer_funds: {allowed: false}')
    try:
        result = await transfer_funds(250.00)
        print(f"  ✓  transfer_funds     → {result}")
    except Exception as exc:
        print(f"  ✗  transfer_funds     DENIED: {exc}")

    # ── 6. Audit trail ────────────────────────────────────────────────────────
    print(
        "\n📋  Every operation above is cryptographically signed and immutably logged.\n"
        "    View your audit trail:\n"
        "\n"
        "      hashed logs list\n"
        "\n"
        "    Or on the dashboard: https://app.hashed.dev\n"
    )

    await core.shutdown()
    print("✓  Quickstart complete!")


if __name__ == "__main__":
    asyncio.run(main())
