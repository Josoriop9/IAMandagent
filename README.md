# Hashed SDK

A professional Python SDK for cryptographic hashing operations with a clean, type-safe interface.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🔐 **Multiple Hash Algorithms**: SHA-256, SHA-512, BLAKE2b, BLAKE2s
- 🔑 **Key Derivation**: PBKDF2-based key derivation
- ⚡ **Async Support**: Full async/await support with httpx
- 🛡️ **Type Safety**: Complete type hints with Pydantic models
- 🎯 **SOLID Principles**: Clean, maintainable architecture
- 🧪 **Well Tested**: Comprehensive test suite
- 📚 **Great Documentation**: Examples and detailed docstrings
- 🔄 **Retry Logic**: Automatic retry with exponential backoff
- 🎨 **Context Managers**: Sync and async context managers

## Installation

```bash
# Using pip
pip install hashed-sdk

# For development
pip install -e ".[dev]"
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

## Usage Examples

### Basic Hashing

```python
from hashed import HashedClient, HashRequest, HashAlgorithm

client = HashedClient()

# Simple hashing
sha256_hash = client.hash_string("my data")

# Using different algorithms
sha512_hash = client.hash_string("my data", algorithm="sha512")
blake2b_hash = client.hash_string("my data", algorithm="blake2b")

# Using HashRequest for more control
request = HashRequest(
    data="sensitive data",
    algorithm=HashAlgorithm.SHA256,
    salt="random_salt"
)
response = client.hash(request)
print(f"Hash: {response.hash_value}")
print(f"Metadata: {response.metadata}")
```

### Hashing with Salt

```python
# Add salt for additional security
hash_with_salt = client.hash_string(
    data="password",
    salt="unique_salt_per_user"
)
```

### Key Derivation

```python
import os

# Generate a cryptographic key from a password
password = "user_password"
salt = os.urandom(16)

key = client.derive_key(
    password=password,
    salt=salt,
    length=32,
    iterations=100000
)
print(f"Derived key: {key.hex()}")
```

### Async Operations

```python
import asyncio

async def main():
    async with HashedClient() as client:
        # Use the client asynchronously
        hash_value = client.hash_string("async data")
        
        # Make async API requests
        result = await client.request_async("GET", "/status")

asyncio.run(main())
```

### Context Managers

```python
# Synchronous context manager
with HashedClient() as client:
    result = client.hash_string("data")

# Asynchronous context manager
async with HashedClient() as client:
    result = client.hash_string("data")
```

## Configuration

### Environment Variables

Create a `.env` file:

```env
HASHED_API_KEY=your_api_key_here
HASHED_API_URL=https://api.hashed.example.com
HASHED_TIMEOUT=30.0
HASHED_MAX_RETRIES=3
HASHED_VERIFY_SSL=true
HASHED_DEBUG=false
```

### Programmatic Configuration

```python
from hashed import HashedClient, HashedConfig

# Create custom configuration
config = HashedConfig(
    api_key="your_api_key",
    api_url="https://custom.api.com",
    timeout=60.0,
    max_retries=5,
    verify_ssl=True,
    debug=False
)

# Initialize client with config
client = HashedClient(config=config)

# Or load from environment
client = HashedClient.from_env()
```

## Architecture

This SDK follows SOLID principles and professional design patterns:

- **Single Responsibility Principle**: Each module has a clear, focused purpose
- **Open/Closed Principle**: Extensible through strategies and protocols
- **Liskov Substitution Principle**: Proper inheritance hierarchies
- **Interface Segregation Principle**: Focused, minimal interfaces
- **Dependency Inversion Principle**: Depends on abstractions, not concretions

### Design Patterns

- **Facade Pattern**: `HashedClient` provides a simplified interface
- **Strategy Pattern**: Pluggable hashing algorithms
- **Factory Pattern**: `from_env()` class method
- **Context Manager**: Resource management with `__enter__` / `__exit__`

## Project Structure

```
hashed-sdk/
├── src/hashed/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Main client (Facade)
│   ├── config.py            # Configuration management
│   ├── exceptions.py        # Custom exceptions
│   ├── models.py            # Pydantic models
│   ├── crypto/              # Cryptography module
│   │   ├── __init__.py
│   │   └── hasher.py        # Hash strategies
│   └── utils/               # Utilities
│       ├── __init__.py
│       └── http_client.py   # HTTP client wrapper
├── tests/                   # Test suite
├── examples/                # Usage examples
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/hashed-sdk.git
cd hashed-sdk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hashed --cov-report=term-missing

# Run specific test file
pytest tests/test_client.py
```

### Code Quality

```bash
# Format code with black
black src/ tests/

# Type checking with mypy
mypy src/

# Lint with ruff
ruff check src/ tests/
```

## Examples

Check out the [examples](examples/) directory for more detailed usage examples:

- [basic_usage.py](examples/basic_usage.py) - Basic functionality
- [async_usage.py](examples/async_usage.py) - Async operations
- [examples/README.md](examples/README.md) - Detailed examples documentation

## API Reference

### HashedClient

Main client class providing SDK functionality.

**Methods:**
- `hash(request: HashRequest) -> HashResponse` - Compute hash from request
- `hash_string(data: str, algorithm: str, salt: str) -> str` - Convenience method
- `derive_key(password: str, salt: bytes, length: int, iterations: int) -> bytes` - Key derivation
- `request_async(method: str, endpoint: str, data: dict) -> dict` - Async API request
- `request_sync(method: str, endpoint: str, data: dict) -> dict` - Sync API request

### HashRequest

Request model for hashing operations.

**Fields:**
- `data: str` - Data to be hashed (required)
- `algorithm: HashAlgorithm` - Hashing algorithm (default: SHA256)
- `encoding: str` - Character encoding (default: utf-8)
- `salt: Optional[str]` - Optional salt

### HashResponse

Response model for hashing operations.

**Fields:**
- `hash_value: str` - Computed hash value
- `algorithm: str` - Algorithm used
- `timestamp: datetime` - Timestamp of computation
- `metadata: dict` - Additional metadata

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Changelog

### Version 0.1.0 (Initial Release)

- ✨ Initial release
- 🔐 Support for SHA-256, SHA-512, BLAKE2b, BLAKE2s
- 🔑 PBKDF2 key derivation
- ⚡ Async/await support
- 🛡️ Type-safe with Pydantic
- 🧪 Comprehensive test suite
- 📚 Full documentation and examples

## Acknowledgments

Built with:
- [cryptography](https://cryptography.io/) - Cryptographic primitives
- [pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [httpx](https://www.python-httpx.org/) - HTTP client
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment management
