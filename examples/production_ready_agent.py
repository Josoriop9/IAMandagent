"""
Production-Ready Customer Support Agent

This example demonstrates a SECURE, production-ready AI agent following
all security best practices.
"""

import asyncio
import os
import httpx
from dotenv import load_dotenv
from hashed import HashedCore
from hashed.config import HashedConfig

load_dotenv()


# ============================================================================
# ADMIN FUNCTIONS (Policy Setup) - NOT EXPOSED TO AGENT
# ============================================================================

async def admin_setup_policies(api_key: str, backend_url: str):
    """
    Admin function to set up policies in the backend.
    
    ✅ SECURE: This is NOT decorated with @guard
    ✅ SECURE: Agent cannot call this
    ✅ SECURE: Only runs during setup
    """
    print("🔒 Admin: Setting up policies...")
    
    policies = [
        {
            "tool_name": "process_refund",
            "allowed": True,
            "max_amount": 500.0,
            "requires_approval": False,
        },
        {
            "tool_name": "send_email",
            "allowed": True,
            "max_amount": None,
            "requires_approval": False,
        },
        {
            "tool_name": "lookup_order",
            "allowed": True,
            "max_amount": None,
            "requires_approval": False,
        },
        {
            "tool_name": "escalate_to_human",
            "allowed": True,
            "max_amount": None,
            "requires_approval": False,
        },
        {
            "tool_name": "delete_customer_data",
            "allowed": False,  # DENIED
            "max_amount": None,
            "requires_approval": False,
        },
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for policy in policies:
            try:
                response = await client.post(
                    f"{backend_url}/v1/policies",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json=policy
                )
                if response.status_code in [201, 409]:
                    print(f"  ✓ Policy: {policy['tool_name']}")
            except Exception as e:
                print(f"  ✗ Failed: {policy['tool_name']} - {e}")
    
    print()


# ============================================================================
# AGENT FUNCTIONS (Operations) - EXPOSED TO AGENT VIA @guard
# ============================================================================

async def main():
    print("=" * 70)
    print("🤖 Production-Ready Customer Support Agent")
    print("=" * 70)
    print()
    
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY", "hashed_4a492e530c7c814a24b6e86cfbdc6c7923cb5a30b957dc8af4ebf9d27b1bda82")
    
    # Step 1: Admin sets up policies (one-time setup)
    await admin_setup_policies(api_key, backend_url)
    
    # Step 2: Initialize agent
    config = HashedConfig(
        backend_url=backend_url,
        api_key=api_key,
        enable_auto_sync=True,
        sync_interval=300,
    )
    
    core = HashedCore(
        config=config,
        agent_name="Customer Support Bot",
        agent_type="customer_service"
    )
    
    await core.initialize()
    
    print(f"✓ Agent initialized: {core.identity.public_key_hex[:16]}...")
    print(f"✓ Policies synced: {len(core.policy_engine.list_policies())}\n")
    
    # Step 3: Define agent operations (these ARE available to agent)
    
    @core.guard("process_refund")
    async def process_refund(amount: float, order_id: str, reason: str):
        """Process a customer refund."""
        print(f"  💵 Processing refund: ${amount} for order {order_id}")
        print(f"     Reason: {reason}")
        await asyncio.sleep(0.1)
        return {
            "status": "refunded",
            "amount": amount,
            "order_id": order_id,
            "refund_id": f"REF-{order_id[:8]}"
        }
    
    @core.guard("send_email")
    async def send_email(to: str, subject: str, body: str):
        """Send email to customer."""
        print(f"  📧 Sending email to: {to}")
        print(f"     Subject: {subject}")
        await asyncio.sleep(0.1)
        return {"status": "sent", "message_id": f"MSG-{to[:8]}"}
    
    @core.guard("lookup_order")
    async def lookup_order(order_id: str):
        """Look up order details."""
        print(f"  🔍 Looking up order: {order_id}")
        await asyncio.sleep(0.1)
        return {
            "order_id": order_id,
            "status": "delivered",
            "total": 129.99,
            "items": ["Widget A", "Widget B"]
        }
    
    @core.guard("escalate_to_human")
    async def escalate_to_human(issue: str, priority: str = "normal"):
        """Escalate issue to human support."""
        print(f"  🚨 Escalating to human: {issue}")
        print(f"     Priority: {priority}")
        await asyncio.sleep(0.1)
        return {
            "status": "escalated",
            "ticket_id": f"TKT-{hash(issue) % 10000}",
            "priority": priority
        }
    
    @core.guard("delete_customer_data")
    async def delete_customer_data(customer_id: str):
        """Delete customer data (DENIED by policy)."""
        print(f"  🗑️  Attempting to delete customer: {customer_id}")
        await asyncio.sleep(0.1)
        return {"status": "deleted"}
    
    # Step 4: List available agent tools
    print("Available Agent Tools:")
    print("-" * 70)
    agent_tools = [
        "process_refund",
        "send_email", 
        "lookup_order",
        "escalate_to_human",
        # NOTE: delete_customer_data is NOT listed (even though defined)
        # because policy denies it
    ]
    for tool in agent_tools:
        policy = core.policy_engine.get_policy(tool)
        if policy:
            status = "✓" if policy.allowed else "✗"
            limit = f" (max: ${policy.max_amount})" if policy.max_amount else ""
            print(f"  {status} {tool}{limit}")
    print()
    
    # Step 5: Simulate customer support scenarios
    print("Simulating Customer Support Scenarios:")
    print("=" * 70)
    
    # Scenario 1: Customer wants refund
    print("\n📞 Scenario 1: Customer Requests Refund ($45)")
    print("-" * 70)
    try:
        order = await lookup_order("ORD-12345")
        print(f"  ✓ Order found: ${order['total']}, status: {order['status']}")
        
        refund = await process_refund(
            amount=45.00,
            order_id="ORD-12345",
            reason="Product damaged on arrival"
        )
        print(f"  ✓ Refund processed: {refund['refund_id']}")
        
        email = await send_email(
            to="customer@example.com",
            subject="Refund Processed",
            body=f"Your refund of ${refund['amount']} has been processed."
        )
        print(f"  ✓ Confirmation sent: {email['message_id']}\n")
    except Exception as e:
        print(f"  ✗ Failed: {e}\n")
    
    # Scenario 2: Large refund (within limit)
    print("📞 Scenario 2: Large Refund Request ($350)")
    print("-" * 70)
    try:
        refund = await process_refund(
            amount=350.00,
            order_id="ORD-67890",
            reason="Wrong item shipped"
        )
        print(f"  ✓ Refund approved: {refund['refund_id']}\n")
    except Exception as e:
        print(f"  ✗ Blocked: {e}\n")
    
    # Scenario 3: Refund exceeds limit
    print("📞 Scenario 3: Refund Exceeds Limit ($750)")
    print("-" * 70)
    try:
        refund = await process_refund(
            amount=750.00,
            order_id="ORD-99999",
            reason="Defective product"
        )
        print(f"  ✓ Should have been blocked!\n")
    except Exception as e:
        print(f"  ✗ Blocked by policy: Amount exceeds $500 limit")
        
        # Escalate to human instead
        escalation = await escalate_to_human(
            issue="Refund request for $750 (exceeds agent limit)",
            priority="high"
        )
        print(f"  ✓ Escalated: {escalation['ticket_id']}\n")
    
    # Scenario 4: Attempt to delete data (denied)
    print("📞 Scenario 4: Customer Requests Data Deletion")
    print("-" * 70)
    try:
        result = await delete_customer_data("CUST-456")
        print(f"  ✗ SECURITY BREACH: Deletion succeeded!\n")
    except Exception as e:
        print(f"  ✓ Blocked by policy: delete_customer_data not allowed")
        
        # Escalate to human for manual processing
        escalation = await escalate_to_human(
            issue="Customer requests data deletion (GDPR)",
            priority="high"
        )
        print(f"  ✓ Escalated to compliance team: {escalation['ticket_id']}\n")
    
    # Scenario 5: Multiple customer interactions
    print("📞 Scenario 5: Batch Customer Support")
    print("-" * 70)
    for i in range(3):
        try:
            await lookup_order(f"ORD-00{i}")
            await send_email(
                to=f"customer{i}@example.com",
                subject="Order Status Update",
                body="Your order has been delivered"
            )
            print(f"  ✓ Customer {i+1} processed")
        except Exception as e:
            print(f"  ✗ Customer {i+1} failed")
    
    print()
    
    # Summary
    print("=" * 70)
    print("Agent Summary")
    print("=" * 70)
    print(f"""
✅ Security Best Practices Followed:
   - Policy management NOT exposed to agent
   - Policies managed via backend (centralized)
   - Agent only has operational tools
   - Dangerous operations (delete) blocked
   - Large refunds escalated to humans
   - Complete audit trail in logs

✅ Agent Capabilities:
   - Process refunds up to $500
   - Send customer emails
   - Look up order information  
   - Escalate complex issues

✅ Agent Limitations:
   - Cannot modify its own policies
   - Cannot delete customer data
   - Cannot process refunds > $500
   - Cannot bypass governance

📊 Check Dashboard:
   - Agents: 1 (Customer Support Bot)
   - Policies: 5
   - Logs: ~15+ operations
   
🔗 Dashboard: {backend_url.replace('8000', '3000')}/dashboard
""")
    
    # Wait for logs to sync
    print("Syncing logs to backend...")
    await asyncio.sleep(6)
    
    await core.shutdown()
    print("✓ Agent shutdown complete\n")


if __name__ == "__main__":
    asyncio.run(main())
