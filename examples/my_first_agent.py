"""
My First Agent with Hashed SDK
Using YOUR API key to populate the dashboard!
"""

import asyncio
import os
from dotenv import load_dotenv
from hashed import HashedCore
from hashed.config import HashedConfig

# Load environment variables
load_dotenv()

async def main():
    print("=== Creating Your First Agent ===\n")
    
    # Configure with YOUR API key to connect to backend
    config = HashedConfig(
        backend_url=os.getenv("BACKEND_URL", "http://localhost:8000"),
        api_key=os.getenv("API_KEY", "hashed_4a492e530c7c814a24b6e86cfbdc6c7923cb5a30b957dc8af4ebf9d27b1bda82")
    )
    
    # Create core with backend mode
    # Note: In backend mode, policies are synced from the backend
    # You need to create policies via the API first, or they'll be created when syncing
    core = HashedCore(
        config=config,
        agent_name=os.getenv("AGENT_NAME", "My First Agent"),
        agent_type="customer_service"
    )
    
    await core.initialize()
    
    print(f"✓ Agent registered with backend")
    print(f"✓ Agent ID: {core.identity.public_key_hex[:16]}...")
    print(f"✓ Policies synced: {len(core.policy_engine.list_policies())}\n")
    
    # Define agent tools
    @core.guard("send_email")
    async def send_email(to: str, subject: str, body: str):
        """Send email to customer"""
        print(f"  📧 Sending email to {to}")
        await asyncio.sleep(0.1)
        return {"status": "sent", "to": to}
    
    @core.guard("transfer_money")
    async def transfer_money(amount: float, to_account: str):
        """Transfer money to account"""
        print(f"  💰 Transferring ${amount} to {to_account}")
        await asyncio.sleep(0.1)
        return {"status": "success", "amount": amount}
    
    @core.guard("make_refund")
    async def make_refund(amount: float, order_id: str):
        """Process customer refund"""
        print(f"  💵 Processing refund of ${amount} for order {order_id}")
        await asyncio.sleep(0.1)
        return {"status": "refunded", "amount": amount}
    
    @core.guard("delete_data")
    async def delete_data(data_id: str):
        """Delete data (should be blocked)"""
        print(f"  🗑️  Deleting {data_id}")
        await asyncio.sleep(0.1)
        return {"status": "deleted"}
    
    # Execute some operations
    print("Executing Operations:\n")
    
    print("1. Send Email (Allowed)")
    print("-" * 50)
    try:
        result = await send_email(
            to="customer@example.com",
            subject="Welcome!",
            body="Thank you for signing up"
        )
        print(f"  ✓ {result}\n")
    except Exception as e:
        print(f"  ✗ {e}\n")
    
    print("2. Small Transfer (Allowed - under $500)")
    print("-" * 50)
    try:
        result = await transfer_money(amount=250.0, to_account="alice")
        print(f"  ✓ {result}\n")
    except Exception as e:
        print(f"  ✗ Blocked: {e}\n")
    
    print("3. Large Transfer (Blocked - over $500)")
    print("-" * 50)
    try:
        result = await transfer_money(amount=750.0, to_account="bob")
        print(f"  ✓ {result}\n")
    except Exception as e:
        print(f"  ✗ Blocked by policy!\n")
        print(f"     {e}\n")
    
    print("4. Process Refund (Allowed - under $100)")
    print("-" * 50)
    try:
        result = await make_refund(amount=50.0, order_id="ORD-123")
        print(f"  ✓ {result}\n")
    except Exception as e:
        print(f"  ✗ {e}\n")
    
    print("5. Delete Data (Blocked by policy)")
    print("-" * 50)
    try:
        result = await delete_data(data_id="user_456")
        print(f"  ✓ {result}\n")
    except Exception as e:
        print(f"  ✗ Blocked by policy!\n")
        print(f"     Policy denies delete operations\n")
    
    # More operations to generate logs
    print("6. Batch Operations")
    print("-" * 50)
    for i in range(5):
        try:
            await send_email(
                to=f"customer{i}@example.com",
                subject="Newsletter",
                body="Monthly update"
            )
            print(f"  ✓ Email {i+1} sent")
        except Exception as e:
            print(f"  ✗ Email {i+1} failed")
    
    print("\n" + "=" * 50)
    print("Waiting for logs to sync to backend...")
    print("=" * 50)
    
    # Wait for ledger to flush
    await asyncio.sleep(6)
    
    await core.shutdown()
    print("\n✓ Agent shutdown complete")
    print("\n🎉 SUCCESS! Now check your dashboard:")
    print("   http://localhost:3001/dashboard")
    print("\nYou should see:")
    print("   - Agents: 1")
    print("   - Policies: 9")
    print("   - Logs: ~10+ operations")

if __name__ == "__main__":
    asyncio.run(main())
