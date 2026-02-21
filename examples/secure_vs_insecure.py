"""
Security Comparison: INSECURE vs SECURE Agent

This example demonstrates the CRITICAL security difference between
allowing agents to modify policies vs keeping policy management separate.

⚠️ WARNING: The insecure examples are for educational purposes ONLY.
NEVER implement these patterns in production!
"""

import asyncio
from hashed import HashedCore
from hashed.config import HashedConfig


# ============================================================================
# ❌ INSECURE EXAMPLE - DO NOT USE IN PRODUCTION
# ============================================================================

async def insecure_agent_example():
    """
    This shows what NEVER to do.
    
    The agent has a tool that can modify policies,
    meaning it (or a malicious LLM) can bypass all governance.
    """
    print("=" * 70)
    print("❌ INSECURE AGENT EXAMPLE (Educational Only)")
    print("=" * 70)
    print()
    
    core = HashedCore()
    await core.initialize()
    
    # Set initial policy: transfer limited to $1000
    core.policy_engine.add_policy("transfer_money", max_amount=1000.0, allowed=True)
    
    # ❌ DANGER: Policy management exposed as @guard
    @core.guard("manage_policy")
    async def update_policy(tool_name: str, max_amount: float):
        """Agent can call this to modify its own policies!"""
        print(f"  ⚠️  Agent modifying its own policy...")
        core.policy_engine.add_policy(tool_name, max_amount=max_amount, allowed=True)
        return {"status": "policy updated"}
    
    @core.guard("transfer_money")
    async def transfer_money(amount: float, to: str):
        """Transfer money with policy check."""
        print(f"  💰 Transferring ${amount:,.0f} to {to}")
        return {"status": "success", "amount": amount}
    
    # Scenario: Agent wants to transfer $10,000
    print("1. Agent tries to transfer $10,000 (over $1,000 limit)")
    print("-" * 70)
    try:
        await transfer_money(10000.0, "attacker")
        print("  ✗ Should have been blocked!\n")
    except Exception as e:
        print(f"  ✓ Blocked: {e}\n")
    
    # 2. Agent uses policy management tool to bypass restriction
    print("2. Agent modifies policy to allow $10,000,000")
    print("-" * 70)
    await update_policy("transfer_money", 10000000.0)
    print("  ✓ Policy modified by agent\n")
    
    # 3. Now agent can transfer unlimited amounts
    print("3. Agent transfers $10,000 (now allowed)")
    print("-" * 70)
    result = await transfer_money(10000.0, "attacker")
    print(f"  ✓ Transfer succeeded: {result}\n")
    
    print("🚨 SECURITY BREACH!")
    print("   Agent bypassed all governance by modifying its own policies\n")
    
    await core.shutdown()


# ============================================================================
# ✅ SECURE EXAMPLE - USE THIS PATTERN
# ============================================================================

async def secure_agent_example():
    """
    This shows the secure pattern.
    
    Policy management is completely separate from agent operations.
    The agent can only CONSUME policies, never MODIFY them.
    """
    print("=" * 70)
    print("✅ SECURE AGENT EXAMPLE (Production Ready)")
    print("=" * 70)
    print()
    
    core = HashedCore()
    await core.initialize()
    
    # ✅ SECURE: Only admin can set policies (not via @guard)
    def admin_set_policy(tool_name: str, max_amount: float):
        """
        Only admin scripts can call this.
        NOT decorated with @guard.
        NOT available to the agent/LLM as a tool.
        """
        print(f"  🔒 Admin setting policy for {tool_name}")
        core.policy_engine.add_policy(tool_name, max_amount=max_amount, allowed=True)
    
    # Admin sets policy (outside of agent's reach)
    admin_set_policy("transfer_money", 1000.0)
    
    # ✅ SECURE: Agent only has operational tools
    @core.guard("transfer_money")
    async def transfer_money(amount: float, to: str):
        """Transfer money with policy check."""
        print(f"  💰 Transferring ${amount:,.0f} to {to}")
        return {"status": "success", "amount": amount}
    
    @core.guard("view_balance")
    async def view_balance(account: str):
        """View account balance."""
        print(f"  👁️  Viewing balance for {account}")
        return {"balance": 5000.0}
    
    # Agent available tools (what LLM can see/call)
    available_tools = [
        "transfer_money",  # Guarded operation
        "view_balance",    # Guarded operation
        # NOTE: No "manage_policy" or "update_policy"
    ]
    
    print(f"Available tools for agent: {available_tools}\n")
    
    # Scenario: Agent tries to transfer $10,000
    print("1. Agent tries to transfer $10,000 (over $1,000 limit)")
    print("-" * 70)
    try:
        await transfer_money(10000.0, "attacker")
        print("  ✗ Should have been blocked!\n")
    except Exception as e:
        print(f"  ✓ Blocked by policy: {str(e)[:80]}\n")
    
    # 2. Agent tries to modify policy (but can't - function doesn't exist for it)
    print("2. Agent searches for policy management tool")
    print("-" * 70)
    if "manage_policy" in available_tools or "update_policy" in available_tools:
        print("  ✗ SECURITY HOLE: Agent found policy management tool\n")
    else:
        print("  ✓ No policy management tool available to agent\n")
    
    # 3. Agent can only perform allowed operations
    print("3. Agent transfers $500 (within limit)")
    print("-" * 70)
    result = await transfer_money(500.0, "legitimate_recipient")
    print(f"  ✓ Transfer succeeded: {result}\n")
    
    # 4. Admin can change policy (agent cannot)
    print("4. Admin increases limit to $5,000")
    print("-" * 70)
    admin_set_policy("transfer_money", 5000.0)
    print("  ✓ Policy updated by admin\n")
    
    # 5. Now agent can transfer up to $5,000
    print("5. Agent transfers $3,000 (within new limit)")
    print("-" * 70)
    result = await transfer_money(3000.0, "vendor")
    print(f"  ✓ Transfer succeeded: {result}\n")
    
    print("✅ SECURE!")
    print("   Agent cannot modify policies")
    print("   Only admin can change governance rules\n")
    
    await core.shutdown()


# ============================================================================
# COMPARISON SUMMARY
# ============================================================================

def print_comparison():
    """Print side-by-side comparison."""
    print("\n" + "=" * 70)
    print("COMPARISON: Insecure vs Secure")
    print("=" * 70)
    print()
    
    comparison = """
┌─────────────────────────────────┬─────────────────────────────────┐
│   ❌ INSECURE PATTERN           │   ✅ SECURE PATTERN             │
├─────────────────────────────────┼─────────────────────────────────┤
│                                 │                                 │
│ @core.guard("manage_policy")    │ # NOT decorated with @guard     │
│ async def update_policy(...):   │ def admin_set_policy(...):      │
│     core.policy_engine...       │     # Only admin scripts call   │
│                                 │                                 │
│ ✗ Agent can modify policies     │ ✓ Agent cannot modify policies  │
│ ✗ LLM can call update_policy    │ ✓ LLM cannot see admin funcs    │
│ ✗ Agent bypasses governance     │ ✓ Governance enforced           │
│ ✗ Security hole                 │ ✓ Secure by design              │
│                                 │                                 │
└─────────────────────────────────┴─────────────────────────────────┘

KEY DIFFERENCES:

1. Function Decoration:
   ❌ @core.guard("manage_policy")  ← Agent can call
   ✅ No @guard on admin functions  ← Agent cannot call

2. Tool Availability:
   ❌ tools = ["transfer", "manage_policy"]  ← Dangerous
   ✅ tools = ["transfer", "view_balance"]    ← Safe

3. Policy Control:
   ❌ Agent controls its own policies  ← Can bypass
   ✅ Admin controls all policies      ← Enforced

4. Attack Surface:
   ❌ Large (agent can modify governance)
   ✅ Small (agent only executes operations)
"""
    
    print(comparison)
    
    print("\n" + "=" * 70)
    print("SECURITY RULES")
    print("=" * 70)
    print("""
1. NEVER decorate policy management with @guard
2. NEVER expose policy modification as a tool to LLM
3. ALWAYS separate admin functions from agent functions
4. ALWAYS use different API keys for admin vs agents
5. ALWAYS audit policy changes
6. ALWAYS validate API key type in backend
7. ALWAYS use RLS in database
8. ALWAYS monitor for policy modification attempts
""")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    print("\n🔒 HASHED SECURITY DEMONSTRATION\n")
    print("This demonstrates why agents should NEVER be able to")
    print("modify their own policies.\n")
    
    # Show insecure example
    await insecure_agent_example()
    
    print("\n" + "━" * 70 + "\n")
    
    # Show secure example
    await secure_agent_example()
    
    # Print comparison
    print_comparison()
    
    print("\n📚 For more information, see: SECURITY.md\n")


if __name__ == "__main__":
    asyncio.run(main())
