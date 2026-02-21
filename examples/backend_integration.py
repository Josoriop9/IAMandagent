"""
Hashed SDK - Backend Integration Example

This example demonstrates how to use the SDK with the backend control plane:
1. Auto-registration of agents
2. Policy synchronization from backend
3. Audit logging to backend
4. Background policy updates
"""

import asyncio
import logging

from hashed import HashedCore, PermissionError
from hashed.config import HashedConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main example demonstrating backend integration."""
    
    print("\n" + "="*70)
    print("Hashed SDK - Backend Integration Example")
    print("="*70 + "\n")
    
    # ========================================================================
    # 1. CONFIGURATION
    # ========================================================================
    print("1. Configuring SDK with Backend")
    print("-" * 70)
    
    # Create configuration with backend URL and API key
    config = HashedConfig(
        backend_url="http://localhost:8000",  # Your backend server
        api_key="test_api_key_12345678901234567890123456789012",
        enable_auto_sync=True,
        sync_interval=300,  # Sync every 5 minutes
        timeout=30.0,
        verify_ssl=False,  # Set to True in production
        debug=True
    )
    
    print(f"✓ Backend URL: {config.backend_url}")
    print(f"✓ Auto-sync enabled: {config.enable_auto_sync}")
    print(f"✓ Sync interval: {config.sync_interval}s")
    
    # ========================================================================
    # 2. INITIALIZE CORE (with auto-registration & policy sync)
    # ========================================================================
    print("\n2. Initializing Core (Auto-registration & Policy Sync)")
    print("-" * 70)
    
    core = HashedCore(
        config=config,
        agent_name="Customer Service Bot",
        agent_type="customer_service",
    )
    
    try:
        # Initialize will:
        # - Register the agent with the backend
        # - Download policies from backend
        # - Start the ledger
        # - Start background policy sync
        await core.initialize()
        
        print(f"✓ Core initialized")
        print(f"✓ Agent identity: {core.identity.public_key_hex[:16]}...")
        print(f"✓ Policies loaded: {len(core.policy_engine.list_policies())}")
        
        # Show loaded policies
        policies = core.policy_engine.list_policies()
        if policies:
            print("\n  Loaded Policies:")
            for tool_name, policy in policies.items():
                allowed_str = "✓ Allowed" if policy.allowed else "✗ Denied"
                amount_str = f", max=${policy.max_amount}" if policy.max_amount else ""
                print(f"    - {tool_name}: {allowed_str}{amount_str}")
        
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        print("\nNote: Make sure the backend server is running!")
        print("Start server with: cd server && python server.py")
        return
    
    # ========================================================================
    # 3. DEFINE AGENT TOOLS WITH @guard DECORATOR
    # ========================================================================
    print("\n3. Defining Agent Tools")
    print("-" * 70)
    
    @core.guard("customer_chat")
    async def chat_with_customer(message: str, customer_id: str):
        """Handle customer chat messages."""
        # Simulate processing
        await asyncio.sleep(0.1)
        return {
            "status": "success",
            "response": f"Processed message from {customer_id}",
            "sentiment": "positive"
        }
    
    @core.guard("make_refund")
    async def process_refund(amount: float, customer_id: str, reason: str):
        """Process customer refund."""
        # Simulate refund processing
        await asyncio.sleep(0.1)
        return {
            "status": "success",
            "refund_id": f"ref_{customer_id}_{int(amount)}",
            "amount": amount
        }
    
    @core.guard("db_write")
    async def update_customer_data(customer_id: str, data: dict):
        """Update customer data in database."""
        # This should be blocked by policy
        await asyncio.sleep(0.1)
        return {"status": "success", "updated": data}
    
    print("✓ Tools defined:")
    print("  - customer_chat (chat with customers)")
    print("  - make_refund (process refunds)")
    print("  - db_write (update database)")
    
    # ========================================================================
    # 4. EXECUTE OPERATIONS (Policy Enforcement + Audit Logging)
    # ========================================================================
    print("\n4. Executing Operations")
    print("-" * 70)
    
    # Operation 1: Customer chat (should be allowed)
    print("\n  a) Customer Chat:")
    try:
        result = await chat_with_customer(
            message="Hello, I need help with my order",
            customer_id="cust_123"
        )
        print(f"    ✓ Chat successful: {result['response']}")
    except PermissionError as e:
        print(f"    ✗ Chat blocked: {e}")
    
    # Operation 2: Small refund (should be allowed if < max_amount)
    print("\n  b) Small Refund ($50):")
    try:
        result = await process_refund(
            amount=50.0,
            customer_id="cust_123",
            reason="Product defect"
        )
        print(f"    ✓ Refund successful: {result['refund_id']}")
    except PermissionError as e:
        print(f"    ✗ Refund blocked: {e}")
    
    # Operation 3: Large refund (might be blocked if > max_amount)
    print("\n  c) Large Refund ($150):")
    try:
        result = await process_refund(
            amount=150.0,
            customer_id="cust_456",
            reason="Wrong item shipped"
        )
        print(f"    ✓ Refund successful: {result['refund_id']}")
    except PermissionError as e:
        print(f"    ✗ Refund blocked: {str(e)}")
    
    # Operation 4: Database write (should be blocked)
    print("\n  d) Database Write:")
    try:
        result = await update_customer_data(
            customer_id="cust_123",
            data={"email": "newemail@example.com"}
        )
        print(f"    ✓ Database update successful")
    except PermissionError as e:
        print(f"    ✗ Database write blocked: Policy denies db_write operations")
    
    # ========================================================================
    # 5. MANUAL POLICY SYNC
    # ========================================================================
    print("\n5. Manual Policy Sync")
    print("-" * 70)
    
    try:
        await core.sync_policies_from_backend()
        print(f"✓ Policies re-synced from backend")
        print(f"✓ Current policies: {len(core.policy_engine.list_policies())}")
    except Exception as e:
        print(f"✗ Sync failed: {e}")
    
    # ========================================================================
    # 6. WAIT FOR LOGS TO BE SENT
    # ========================================================================
    print("\n6. Flushing Audit Logs to Backend")
    print("-" * 70)
    
    if core.ledger:
        await asyncio.sleep(1)  # Wait a moment for logs to queue
        await core.ledger.flush()
        print("✓ All audit logs sent to backend")
        print(f"  Check backend logs at: {config.backend_url}/v1/logs")
    
    # ========================================================================
    # 7. CLEANUP
    # ========================================================================
    print("\n7. Shutting Down")
    print("-" * 70)
    
    await core.shutdown()
    print("✓ Core shutdown complete")
    print("  - Background sync stopped")
    print("  - Ledger stopped and flushed")
    print("  - HTTP client closed")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print("""
✓ Agent auto-registered with backend
✓ Policies downloaded from backend
✓ Operations executed with policy enforcement
✓ Audit logs sent to backend in real-time
✓ Background sync running (until shutdown)

Next Steps:
1. Check backend logs: curl http://localhost:8000/v1/logs \\
     -H "X-API-KEY: test_api_key_12345678901234567890123456789012"

2. View agent info: curl http://localhost:8000/v1/agents \\
     -H "X-API-KEY: test_api_key_12345678901234567890123456789012"

3. Manage policies via backend API
4. Build dashboard to visualize agent activity
""")


async def example_context_manager():
    """Example using async context manager."""
    print("\n" + "="*70)
    print("Alternative: Using Async Context Manager")
    print("="*70 + "\n")
    
    config = HashedConfig(
        backend_url="http://localhost:8000",
        api_key="test_api_key_12345678901234567890123456789012",
    )
    
    # Using context manager (auto initialize/shutdown)
    async with HashedCore(config=config, agent_name="Quick Agent") as core:
        print("✓ Core initialized (via context manager)")
        
        @core.guard("test_operation")
        async def test_operation():
            return {"status": "success"}
        
        result = await test_operation()
        print(f"✓ Operation executed: {result}")
        
    print("✓ Core automatically shutdown\n")


if __name__ == "__main__":
    # Run main example
    asyncio.run(main())
    
    # Uncomment to see context manager example
    # asyncio.run(example_context_manager())
