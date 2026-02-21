# Hashed SDK Examples

This directory contains example scripts demonstrating how to use the Hashed SDK.

## Examples

### 1. Basic Usage (`basic_usage.py`)

Demonstrates the fundamental features of the SDK:
- Simple string hashing
- Different hashing algorithms (SHA-256, SHA-512, BLAKE2b, BLAKE2s)
- Using `HashRequest` objects for more control
- Hashing with salt
- Key derivation using PBKDF2
- Context manager usage

**Run:**
```bash
python examples/basic_usage.py
```

### 2. Async Usage (`async_usage.py`)

Shows how to use the SDK with asynchronous operations:
- Async context manager
- Processing multiple items concurrently
- Batch processing with timing
- Using `asyncio.gather()` for concurrent operations

**Run:**
```bash
python examples/async_usage.py
```

## Installation

Before running the examples, make sure you have installed the SDK:

```bash
# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Environment Configuration

The SDK can be configured using environment variables. Create a `.env` file:

```env
HASHED_API_KEY=your_api_key_here
HASHED_API_URL=https://api.hashed.example.com
HASHED_TIMEOUT=30.0
HASHED_MAX_RETRIES=3
HASHED_VERIFY_SSL=true
HASHED_DEBUG=false
```

## Quick Start

```python
from hashed import HashedClient

# Initialize the client
client = HashedClient()

# Hash a string
hash_value = client.hash_string("Hello, World!")
print(f"Hash: {hash_value}")
```

## Advanced Usage

### Using Different Algorithms

```python
from hashed import HashedClient, HashAlgorithm

client = HashedClient()

# SHA-512
hash_sha512 = client.hash_string("data", algorithm="sha512")

# BLAKE2b
hash_blake2b = client.hash_string("data", algorithm="blake2b")
```

### With Salt

```python
hash_with_salt = client.hash_string(
    "sensitive_data",
    salt="random_salt_value"
)
```

### Key Derivation

```python
import os

salt = os.urandom(16)
key = client.derive_key(
    password="user_password",
    salt=salt,
    length=32,
    iterations=100000
)
```

## More Information

For complete documentation, see the main [README.md](../README.md) file.
