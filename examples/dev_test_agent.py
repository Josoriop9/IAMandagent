"""
Dev Test Agent - Hashed AI Agent (Plain Python)
Auto-generated. Policies sourced from .hashed_policies.json
"""

import asyncio
import os
from dotenv import load_dotenv
from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for Dev Test Agent."""
    # 1. Setup
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("./secrets/dev_test_agent_key.pem", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="Dev Test Agent",
        agent_type="general"
    )

    # 2. Initialize (registers agent, syncs policies)
    await core.initialize()
    print(f"🤖 Dev Test Agent (general) initialized\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # ================================================================

    @core.guard("example_operation")
    async def example_operation(data: str):
        """example_operation - allowed [global]"""
        return {"status": "success", "tool": "example_operation", "data": data}


    # ================================================================
    # Execute Operations
    # ================================================================
    print("Running operations...")

    try:
        result = await example_operation("test")
        print(f"  ✓ example_operation: {result}")
    except Exception as e:
        print(f"  ✗ example_operation: {e}")

    await core.shutdown()
    print(f"\n✓ Dev Test Agent finished")


if __name__ == "__main__":
    asyncio.run(main())
