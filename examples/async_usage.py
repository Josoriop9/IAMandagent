"""
Async usage examples for the Hashed SDK.

This script demonstrates asynchronous operations with the SDK.
"""

import asyncio
from hashed import HashedClient, HashRequest


async def hash_multiple_items(client: HashedClient, items: list[str]) -> list[str]:
    """
    Hash multiple items concurrently.

    Args:
        client: Hashed client instance
        items: List of strings to hash

    Returns:
        List of hash values
    """
    # Note: hash() is synchronous, but this demonstrates async patterns
    results = []
    for item in items:
        hash_value = client.hash_string(item)
        results.append(hash_value)
    return results


async def main() -> None:
    """Demonstrate async SDK usage."""
    print("=== Hashed SDK - Async Usage Examples ===\n")

    # Example 1: Using async context manager
    print("1. Async Context Manager")
    print("-" * 40)
    async with HashedClient() as client:
        hash_value = client.hash_string("Async test")
        print(f"Hash computed: {hash_value[:32]}...")
    print("✓ Async resources cleaned up\n")

    # Example 2: Processing multiple items
    print("2. Processing Multiple Items")
    print("-" * 40)
    client = HashedClient()
    
    items = [
        "Item 1",
        "Item 2",
        "Item 3",
        "Item 4",
        "Item 5",
    ]
    
    results = await hash_multiple_items(client, items)
    
    for item, hash_value in zip(items, results):
        print(f"'{item}' -> {hash_value[:32]}...")
    
    await client.close_async()
    print()

    # Example 3: Batch processing with timing
    print("3. Batch Processing with Timing")
    print("-" * 40)
    import time
    
    async with HashedClient() as client:
        start_time = time.time()
        
        # Generate test data
        test_data = [f"test_data_{i}" for i in range(100)]
        
        # Process all items
        hashes = []
        for data in test_data:
            hash_value = client.hash_string(data)
            hashes.append(hash_value)
        
        elapsed = time.time() - start_time
        print(f"Processed {len(test_data)} items in {elapsed:.3f} seconds")
        print(f"Average: {elapsed/len(test_data)*1000:.2f} ms per item\n")

    # Example 4: Concurrent operations with asyncio.gather
    print("4. Concurrent Operations")
    print("-" * 40)
    
    async def hash_task(client: HashedClient, data: str, task_id: int) -> tuple[int, str]:
        """Task that hashes data and returns result with task ID."""
        # Simulate some async work
        await asyncio.sleep(0.01)
        hash_value = client.hash_string(data)
        return task_id, hash_value
    
    async with HashedClient() as client:
        tasks = [
            hash_task(client, f"concurrent_data_{i}", i)
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        print("Concurrent tasks completed:")
        for task_id, hash_value in results[:3]:  # Show first 3
            print(f"  Task {task_id}: {hash_value[:32]}...")
        print(f"  ... and {len(results) - 3} more\n")

    print("=== Async examples completed successfully! ===")


if __name__ == "__main__":
    asyncio.run(main())
