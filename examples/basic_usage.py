"""
Basic usage examples for the Hashed SDK.

This script demonstrates the core functionality of the SDK.
"""

from hashed import HashedClient, HashRequest, HashAlgorithm


def main() -> None:
    """Demonstrate basic SDK usage."""
    print("=== Hashed SDK - Basic Usage Examples ===\n")

    # Initialize the client
    client = HashedClient()
    print("✓ Client initialized\n")

    # Example 1: Simple string hashing
    print("1. Simple String Hashing")
    print("-" * 40)
    hash_value = client.hash_string("Hello, World!")
    print(f"Data: 'Hello, World!'")
    print(f"Hash (SHA-256): {hash_value}\n")

    # Example 2: Using different algorithms
    print("2. Different Hashing Algorithms")
    print("-" * 40)
    data = "Test data"
    
    for algorithm in [HashAlgorithm.SHA256, HashAlgorithm.SHA512, HashAlgorithm.BLAKE2B]:
        hash_value = client.hash_string(data, algorithm=algorithm.value)
        print(f"{algorithm.value.upper()}: {hash_value[:32]}...")
    print()

    # Example 3: Using HashRequest for more control
    print("3. Using HashRequest Objects")
    print("-" * 40)
    request = HashRequest(
        data="Important data",
        algorithm=HashAlgorithm.SHA256,
        salt="my_secret_salt"
    )
    response = client.hash(request)
    print(f"Data: '{request.data}'")
    print(f"Algorithm: {response.algorithm}")
    print(f"Hash: {response.hash_value}")
    print(f"Timestamp: {response.timestamp}")
    print(f"Metadata: {response.metadata}\n")

    # Example 4: Hashing with salt
    print("4. Hashing with Salt")
    print("-" * 40)
    data = "password123"
    hash_without_salt = client.hash_string(data)
    hash_with_salt = client.hash_string(data, salt="random_salt")
    
    print(f"Data: '{data}'")
    print(f"Without salt: {hash_without_salt[:32]}...")
    print(f"With salt:    {hash_with_salt[:32]}...")
    print(f"Are they different? {hash_without_salt != hash_with_salt}\n")

    # Example 5: Key derivation
    print("5. Key Derivation (PBKDF2)")
    print("-" * 40)
    import os
    password = "my_secure_password"
    salt = os.urandom(16)
    
    key = client.derive_key(password, salt, length=32)
    print(f"Password: '{password}'")
    print(f"Salt: {salt.hex()}")
    print(f"Derived key (32 bytes): {key.hex()}\n")

    # Example 6: Context manager usage
    print("6. Using Context Manager")
    print("-" * 40)
    with HashedClient() as managed_client:
        result = managed_client.hash_string("Context manager test")
        print(f"Hash computed: {result[:32]}...")
    print("✓ Resources automatically cleaned up\n")

    print("=== Examples completed successfully! ===")


if __name__ == "__main__":
    main()
