"""
Guard decorator usage examples.

This script demonstrates the @guard decorator that integrates
identity verification, policy validation, and audit logging.
"""

import asyncio
from hashed import HashedCore, PermissionError, create_core


# Example async function protected by guard
async def example_with_guard():
    """Demonstrate the @guard decorator with policy enforcement."""
    print("=== Hashed SDK - Guard Decorator Examples ===\n")

    # Create core with policies
    core = create_core(
        ledger_endpoint="https://api.example.com/audit/logs",
        policies={
            "transfer": {"max_amount": 1000.0, "allowed": True},
            "delete": {"allowed": False},
            "read": {"allowed": True},
        },
    )

    # Initialize (starts ledger if endpoint is configured)
    await core.initialize()
    
    print("✓ Core initialized")
    print(f"✓ Identity: {core.identity.public_key_hex[:16]}...")
    print(f"✓ Policies loaded: {len(core.policy_engine.list_policies())}\n")

    # Example 1: Successful operation within limits
    print("1. Successful Transfer (Within Limits)")
    print("-" * 50)

    @core.guard("transfer")
    async def transfer_money(amount: float, to_account: str) -> dict:
        """Simulate a money transfer."""
        # Actual transfer logic would go here
        return {
            "status": "success",
            "amount": amount,
            "to": to_account,
            "transaction_id": "tx_12345",
        }

    try:
        result = await transfer_money(amount=500.0, to_account="alice")
        print(f"✓ Transfer successful: ${result['amount']} to {result['to']}")
        print(f"  Transaction ID: {result['transaction_id']}\n")
    except PermissionError as e:
        print(f"✗ Transfer failed: {e}\n")

    # Example 2: Operation exceeding limits
    print("2. Failed Transfer (Exceeds Limit)")
    print("-" * 50)

    try:
        result = await transfer_money(amount=1500.0, to_account="bob")
        print(f"✓ Transfer successful: ${result['amount']} to {result['to']}\n")
    except PermissionError as e:
        print(f"✗ Transfer blocked: {e}")
        print(f"  Details: {e.details}\n")

    # Example 3: Blocked operation
    print("3. Blocked Operation")
    print("-" * 50)

    @core.guard("delete")
    async def delete_account(account_id: str) -> dict:
        """Simulate account deletion."""
        return {"status": "deleted", "account_id": account_id}

    try:
        result = await delete_account(account_id="acc_123")
        print(f"✓ Account deleted: {result['account_id']}\n")
    except PermissionError as e:
        print(f"✗ Delete blocked: {e}")
        print(f"  Policy denies all delete operations\n")

    # Example 4: Operation without amount limits
    print("4. Read Operation (No Limits)")
    print("-" * 50)

    @core.guard("read", amount_param=None)
    async def read_data(resource_id: str) -> dict:
        """Simulate data read."""
        return {
            "resource_id": resource_id,
            "data": "sample data content",
            "status": "success",
        }

    try:
        result = await read_data(resource_id="res_456")
        print(f"✓ Read successful: {result['resource_id']}")
        print(f"  Data preview: {result['data'][:30]}...\n")
    except PermissionError as e:
        print(f"✗ Read failed: {e}\n")

    # Example 5: Multiple operations with signatures
    print("5. Batch Operations with Identity Signatures")
    print("-" * 50)

    @core.guard("transfer")
    async def batch_transfer(amount: float, recipients: list) -> dict:
        """Simulate batch transfer."""
        total = amount * len(recipients)
        return {
            "status": "success",
            "total_amount": total,
            "recipient_count": len(recipients),
        }

    operations = [
        {"amount": 100.0, "recipients": ["alice", "bob"]},
        {"amount": 200.0, "recipients": ["charlie"]},
        {"amount": 300.0, "recipients": ["david", "eve", "frank"]},
    ]

    for i, op in enumerate(operations, 1):
        try:
            result = await batch_transfer(**op)
            print(f"  Operation {i}: ✓ ${result['total_amount']} to {result['recipient_count']} recipients")
        except PermissionError as e:
            print(f"  Operation {i}: ✗ Blocked - {e.message}")

    print()

    # Example 6: Checking permissions before execution
    print("6. Pre-checking Permissions")
    print("-" * 50)

    test_operations = [
        ("transfer", 800.0),
        ("transfer", 1200.0),
        ("delete", None),
        ("read", None),
    ]

    for tool_name, amount in test_operations:
        permitted = core.policy_engine.check_permission(tool_name, amount)
        status = "✓ Allowed" if permitted else "✗ Denied"
        amount_str = f" (${amount})" if amount else ""
        print(f"  {tool_name}{amount_str}: {status}")

    print()

    # Show policy details
    print("7. Policy Configuration")
    print("-" * 50)
    policies = core.policy_engine.export_policies()
    for name, policy in policies.items():
        max_amt = f"max=${policy['max_amount']}" if policy['max_amount'] else "unlimited"
        allowed = "✓" if policy['allowed'] else "✗"
        print(f"  {allowed} {name}: {max_amt}")

    print()

    # Cleanup
    await core.shutdown()
    print("✓ Core shutdown complete")
    print("\n=== Examples completed successfully! ===")


async def example_with_context_manager():
    """Demonstrate using HashedCore with async context manager."""
    print("\n=== Using Context Manager ===\n")

    async with HashedCore(ledger_endpoint="https://api.example.com/logs") as core:
        # Add policies
        core.policy_engine.add_policy("api_call", max_amount=100, allowed=True)

        @core.guard("api_call")
        async def make_api_call(amount: float, endpoint: str) -> dict:
            return {"status": "success", "endpoint": endpoint}

        try:
            result = await make_api_call(amount=50, endpoint="/api/data")
            print(f"✓ API call successful: {result['endpoint']}")
        except PermissionError as e:
            print(f"✗ API call failed: {e}")

    print("✓ Context manager automatically cleaned up resources\n")


def main():
    """Run all examples."""
    asyncio.run(example_with_guard())
    asyncio.run(example_with_context_manager())


if __name__ == "__main__":
    main()
