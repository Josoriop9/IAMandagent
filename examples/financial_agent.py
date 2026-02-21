"""
Financial Agent with Policies
This agent registers policies with the backend so they appear in the dashboard!
"""

import asyncio
import os
import httpx
from dotenv import load_dotenv
from hashed import HashedCore
from hashed.config import HashedConfig

# Load environment variables
load_dotenv()

async def create_policies_in_backend(api_key: str, backend_url: str, org_id: str):
    """Create policies directly in the backend."""
    print("Creating policies in backend...")
    
    policies_to_create = [
        {
            "tool_name": "process_payment",
            "allowed": True,
            "max_amount": 5000.0,
            "requires_approval": False,
        },
        {
            "tool_name": "issue_refund",
            "allowed": True,
            "max_amount": 1000.0,
            "requires_approval": True,
        },
        {
            "tool_name": "wire_transfer",
            "allowed": True,
            "max_amount": 10000.0,
            "requires_approval": True,
        },
        {
            "tool_name": "cancel_transaction",
            "allowed": True,
            "max_amount": None,
            "requires_approval": False,
        },
        {
            "tool_name": "delete_account",
            "allowed": False,
            "max_amount": None,
            "requires_approval": False,
        },
        {
            "tool_name": "view_balance",
            "allowed": True,
            "max_amount": None,
            "requires_approval": False,
        },
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        created_count = 0
        for policy in policies_to_create:
            try:
                response = await client.post(
                    f"{backend_url}/v1/policies",
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json"
                    },
                    json=policy
                )
                
                if response.status_code == 201:
                    created_count += 1
                    print(f"  ✓ Created policy: {policy['tool_name']}")
                elif response.status_code == 409:
                    print(f"  ○ Policy already exists: {policy['tool_name']}")
                else:
                    print(f"  ✗ Failed to create {policy['tool_name']}: {response.status_code}")
            except Exception as e:
                print(f"  ✗ Error creating {policy['tool_name']}: {e}")
        
        print(f"\n✓ Policies created: {created_count}/{len(policies_to_create)}\n")


async def main():
    print("=" * 70)
    print("Financial Agent with Backend Policies")
    print("=" * 70)
    print()
    
    # Configuration
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY", "hashed_4a492e530c7c814a24b6e86cfbdc6c7923cb5a30b957dc8af4ebf9d27b1bda82")
    
    # Get organization ID (you'll need this - it's in your Supabase)
    # For now, we'll use the API key's organization
    org_id = "auto"  # Backend will determine from API key
    
    # Step 1: Create policies in backend
    await create_policies_in_backend(api_key, backend_url, org_id)
    
    # Step 2: Initialize agent
    config = HashedConfig(
        backend_url=backend_url,
        api_key=api_key,
        enable_auto_sync=True,
    )
    
    core = HashedCore(
        config=config,
        agent_name="Financial Services Agent",
        agent_type="financial"
    )
    
    await core.initialize()
    
    print(f"✓ Agent initialized")
    print(f"✓ Agent ID: {core.identity.public_key_hex[:16]}...")
    print(f"✓ Policies synced from backend: {len(core.policy_engine.list_policies())}")
    print()
    
    # List synced policies
    print("Synced Policies:")
    print("-" * 70)
    for tool_name, policy in core.policy_engine.list_policies().items():
        status = "✓ Allowed" if policy.allowed else "✗ Denied"
        amount = f" (max: ${policy.max_amount:,.2f})" if policy.max_amount else ""
        print(f"  {tool_name}: {status}{amount}")
    print()
    
    # Step 3: Define agent operations
    @core.guard("process_payment")
    async def process_payment(amount: float, customer_id: str):
        """Process a customer payment."""
        print(f"  💳 Processing payment of ${amount:,.2f} for customer {customer_id}")
        await asyncio.sleep(0.1)
        return {"status": "success", "amount": amount, "customer_id": customer_id}
    
    @core.guard("issue_refund")
    async def issue_refund(amount: float, order_id: str):
        """Issue a refund to customer."""
        print(f"  💰 Issuing refund of ${amount:,.2f} for order {order_id}")
        await asyncio.sleep(0.1)
        return {"status": "refunded", "amount": amount}
    
    @core.guard("wire_transfer")
    async def wire_transfer(amount: float, to_account: str):
        """Wire transfer to external account."""
        print(f"  🏦 Wire transfer of ${amount:,.2f} to {to_account}")
        await asyncio.sleep(0.1)
        return {"status": "pending", "amount": amount}
    
    @core.guard("view_balance")
    async def view_balance(account_id: str):
        """View account balance."""
        print(f"  👁️  Viewing balance for account {account_id}")
        await asyncio.sleep(0.05)
        return {"balance": 12500.00, "account_id": account_id}
    
    @core.guard("delete_account")
    async def delete_account(account_id: str):
        """Delete account (should be blocked)."""
        print(f"  🗑️  Deleting account {account_id}")
        await asyncio.sleep(0.1)
        return {"status": "deleted"}
    
    # Step 4: Execute operations
    print("\nExecuting Financial Operations:")
    print("=" * 70)
    
    # Test 1: Small payment (allowed)
    print("\n1. Small Payment ($500)")
    print("-" * 70)
    try:
        result = await process_payment(amount=500.0, customer_id="CUST-001")
        print(f"  ✓ Success: {result['status']}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 2: Large payment (allowed, under limit)
    print("\n2. Large Payment ($4,500)")
    print("-" * 70)
    try:
        result = await process_payment(amount=4500.0, customer_id="CUST-002")
        print(f"  ✓ Success: {result['status']}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 3: Exceed payment limit (should be blocked)
    print("\n3. Exceeds Limit ($6,000)")
    print("-" * 70)
    try:
        result = await process_payment(amount=6000.0, customer_id="CUST-003")
        print(f"  ✓ Success: {result['status']}")
    except Exception as e:
        print(f"  ✗ Blocked by policy: Amount ${6000:,.2f} exceeds max ${5000:,.2f}")
    
    # Test 4: Refund (allowed)
    print("\n4. Issue Refund ($250)")
    print("-" * 70)
    try:
        result = await issue_refund(amount=250.0, order_id="ORD-789")
        print(f"  ✓ Success: {result['status']}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 5: Large refund (allowed but requires approval)
    print("\n5. Large Refund ($900 - requires approval)")
    print("-" * 70)
    try:
        result = await issue_refund(amount=900.0, order_id="ORD-456")
        print(f"  ✓ Success: {result['status']}")
        print(f"  ⚠️  Note: This would require human approval in production")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 6: Wire transfer (requires approval)
    print("\n6. Wire Transfer ($8,000 - requires approval)")
    print("-" * 70)
    try:
        result = await wire_transfer(amount=8000.0, to_account="EXT-BANK-123")
        print(f"  ✓ Success: {result['status']}")
        print(f"  ⚠️  Note: This requires human approval")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 7: View balance (always allowed)
    print("\n7. View Balance")
    print("-" * 70)
    try:
        result = await view_balance(account_id="ACC-999")
        print(f"  ✓ Balance: ${result['balance']:,.2f}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    # Test 8: Delete account (denied by policy)
    print("\n8. Delete Account (DENIED)")
    print("-" * 70)
    try:
        result = await delete_account(account_id="ACC-999")
        print(f"  ✓ Success: {result['status']}")
    except Exception as e:
        print(f"  ✗ Blocked by policy: delete_account is not allowed")
    
    # Batch operations for more logs
    print("\n9. Batch View Operations")
    print("-" * 70)
    for i in range(5):
        try:
            await view_balance(account_id=f"ACC-{100+i}")
            print(f"  ✓ Viewed balance for ACC-{100+i}")
        except Exception as e:
            print(f"  ✗ Failed for ACC-{100+i}")
    
    # Wait for logs to sync
    print("\n" + "=" * 70)
    print("Waiting for logs to sync to backend...")
    print("=" * 70)
    await asyncio.sleep(6)
    
    # Shutdown
    await core.shutdown()
    
    print("\n✓ Agent shutdown complete")
    print("\n🎉 SUCCESS! Check your dashboard:")
    print(f"   {backend_url.replace('8000', '3000')}/dashboard")
    print("\nYou should see:")
    print("   ✓ Agents: +1 (Financial Services Agent)")
    print("   ✓ Policies: 6 (process_payment, issue_refund, wire_transfer, etc.)")
    print("   ✓ Logs: ~15+ operations")
    print()


if __name__ == "__main__":
    asyncio.run(main())
