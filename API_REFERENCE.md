# Hashed SDK - Complete API Reference

Complete API documentation for the Hashed SDK - AI Agent Governance & Security Layer.

---

## Table of Contents

- [Installation](#installation)
- [Core Classes](#core-classes)
  - [HashedCore](#hashedcore)
  - [HashedConfig](#hashedconfig)
  - [PolicyEngine](#policyengine)
  - [IdentityManager](#identitymanager)
  - [AsyncLedger](#asyncledger)
- [Decorators](#decorators)
- [Models](#models)
- [Exceptions](#exceptions)
- [Utilities](#utilities)

---

## Installation

```bash
# From local (development)
pip install -e /path/to/hashed-sdk

# From GitHub
pip install git+https://github.com/YOUR-USER/hashed-sdk.git

# From PyPI (when published)
pip install hashed-sdk

# With LLM support
pip install hashed-sdk[examples]
```

---

## Core Classes

### HashedCore

Main entry point for the Hashed SDK. Provides agent identity, policy enforcement, and audit logging.

#### Constructor

```python
HashedCore(
    config: Optional[HashedConfig] = None,
    agent_name: Optional[str] = None,
    agent_type: Optional[str] = None
)
```

**Parameters:**
- `config` (HashedConfig, optional): Configuration object. If None, uses default config.
- `agent_name` (str, optional): Human-readable name for the agent
- `agent_type` (str, optional): Type/category of agent (e.g., "customer_service", "financial")

**Returns:** HashedCore instance

**Example:**
```python
from hashed import HashedCore
from hashed.config import HashedConfig

# Simple usage
core = HashedCore()

# With configuration
config = HashedConfig(
    backend_url="http://localhost:8000",
    api_key="your-key-here"
)
core = HashedCore(
    config=config,
    agent_name="Customer Support Bot",
    agent_type="customer_service"
)
```

#### Methods

##### `initialize()`

```python
async def initialize() -> None
```

Initialize the agent: registers with backend, syncs policies, starts background tasks.

**Returns:** None

**Raises:**
- `ConnectionError`: If backend is unreachable
- `AuthenticationError`: If API key is invalid

**Example:**
```python
core = HashedCore(config=config)
await core.initialize()
```

##### `shutdown()`

```python
async def shutdown() -> None
```

Gracefully shutdown the agent: syncs remaining logs, closes connections.

**Returns:** None

**Example:**
```python
await core.shutdown()
```

##### `guard(tool_name: str)`

```python
def guard(tool_name: str) -> Callable
```

Decorator to protect functions with policy enforcement and audit logging.

**Parameters:**
- `tool_name` (str): Name of the operation/tool to guard

**Returns:** Decorator function

**Raises:**
- `PermissionError`: If operation is not allowed by policy
- `PolicyNotFoundError`: If policy doesn't exist (in strict mode)

**Example:**
```python
@core.guard("transfer_money")
async def transfer(amount: float, to: str):
    # Your business logic here
    return {"status": "success"}

# Usage
await transfer(100.0, "user@example.com")
# ✓ Validated against policy
# ✓ Logged with crypto signature
# ✓ Error handling automatic
```

#### Properties

##### `identity`

```python
@property
def identity() -> IdentityManager
```

Access to the agent's cryptographic identity.

**Returns:** IdentityManager instance

**Example:**
```python
print(core.identity.public_key_hex)  # Agent's public key
signature = core.identity.sign_message("data")  # Sign data
```

##### `policy_engine`

```python
@property
def policy_engine() -> PolicyEngine
```

Access to the policy engine for managing policies.

**Returns:** PolicyEngine instance

**Example:**
```python
# Add local policy
core.policy_engine.add_policy("operation", allowed=True, max_amount=1000.0)

# List all policies
policies = core.policy_engine.list_policies()

# Get specific policy
policy = core.policy_engine.get_policy("operation")
```

##### `ledger`

```python
@property
def ledger() -> AsyncLedger
```

Access to the audit ledger.

**Returns:** AsyncLedger instance

**Example:**
```python
# Ledger logs automatically via @guard
# Access for custom logging if needed
await core.ledger.log_operation(...)
```

#### Context Manager Support

```python
async with HashedCore(config=config) as core:
    @core.guard("operation")
    async def do_thing():
        return "done"
    
    await do_thing()

# Automatically initialized and shutdown
```

---

### HashedConfig

Configuration object for HashedCore.

#### Constructor

```python
HashedConfig(
    backend_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 30,
    enable_auto_sync: bool = False,
    sync_interval: int = 300,
    verify_ssl: bool = True
)
```

**Parameters:**
- `backend_url` (str, optional): Backend API URL. Defaults to env var `BACKEND_URL` or `http://localhost:8000`
- `api_key` (str, optional): API key for backend. Defaults to env var `API_KEY`
- `timeout` (int): Request timeout in seconds. Default: 30
- `enable_auto_sync` (bool): Enable automatic policy sync. Default: False
- `sync_interval` (int): Sync interval in seconds. Default: 300 (5 min)
- `verify_ssl` (bool): Verify SSL certificates. Default: True

**Example:**
```python
from hashed.config import HashedConfig

# Auto-load from .env
config = HashedConfig()

# Manual configuration
config = HashedConfig(
    backend_url="https://api.your-domain.com",
    api_key="hashed_admin_abc123...",
    enable_auto_sync=True,
    sync_interval=300
)
```

#### Environment Variables

The config automatically reads from environment variables:

```bash
# .env file
BACKEND_URL=http://localhost:8000
API_KEY=your-api-key-here
```

---

### PolicyEngine

Manages and validates policies for operations.

#### Methods

##### `add_policy()`

```python
def add_policy(
    tool_name: str,
    allowed: bool = True,
    max_amount: Optional[float] = None,
    requires_approval: bool = False,
    metadata: Optional[dict] = None
) -> None
```

Add or update a policy.

**Parameters:**
- `tool_name` (str): Name of the tool/operation
- `allowed` (bool): Whether operation is allowed. Default: True
- `max_amount` (float, optional): Maximum amount limit (for financial ops)
- `requires_approval` (bool): Whether operation requires approval. Default: False
- `metadata` (dict, optional): Additional metadata

**Example:**
```python
engine = core.policy_engine

engine.add_policy("transfer_money", allowed=True, max_amount=500.0)
engine.add_policy("delete_user", allowed=False)
engine.add_policy("send_email", allowed=True)
```

##### `get_policy()`

```python
def get_policy(tool_name: str) -> Optional[Policy]
```

Get policy for a specific tool.

**Parameters:**
- `tool_name` (str): Name of the tool

**Returns:** Policy object or None if not found

**Example:**
```python
policy = engine.get_policy("transfer_money")
if policy and policy.allowed:
    print(f"Max amount: ${policy.max_amount}")
```

##### `list_policies()`

```python
def list_policies() -> Dict[str, Policy]
```

Get all policies.

**Returns:** Dictionary mapping tool names to Policy objects

**Example:**
```python
policies = engine.list_policies()
for tool_name, policy in policies.items():
    print(f"{tool_name}: {policy.allowed}")
```

##### `validate()`

```python
def validate(
    tool_name: str,
    amount: Optional[float] = None,
    **context
) -> bool
```

Validate an operation against its policy.

**Parameters:**
- `tool_name` (str): Name of the tool
- `amount` (float, optional): Amount for financial operations
- `**context`: Additional context

**Returns:** True if allowed, False otherwise

**Raises:**
- `PermissionError`: If operation is not allowed

**Example:**
```python
try:
    engine.validate("transfer_money", amount=250.0)
    print("Operation allowed")
except PermissionError as e:
    print(f"Blocked: {e}")
```

---

### IdentityManager

Manages cryptographic identity for the agent.

#### Methods

##### `generate_keypair()`

```python
@staticmethod
def generate_keypair() -> Tuple[bytes, bytes]
```

Generate a new Ed25519 keypair.

**Returns:** Tuple of (private_key_bytes, public_key_bytes)

**Example:**
```python
from hashed.identity import IdentityManager

private_key, public_key = IdentityManager.generate_keypair()
```

##### `sign_message()`

```python
def sign_message(self, message: Union[str, bytes]) -> bytes
```

Sign a message with the agent's private key.

**Parameters:**
- `message` (str | bytes): Message to sign

**Returns:** Signature bytes

**Example:**
```python
identity = core.identity
signature = identity.sign_message("important data")
```

##### `verify_signature()`

```python
@staticmethod
def verify_signature(
    public_key: bytes,
    message: Union[str, bytes],
    signature: bytes
) -> bool
```

Verify a signature.

**Parameters:**
- `public_key` (bytes): Public key to verify with
- `message` (str | bytes): Original message
- `signature` (bytes): Signature to verify

**Returns:** True if signature is valid, False otherwise

**Example:**
```python
is_valid = IdentityManager.verify_signature(
    public_key=identity.public_key,
    message="data",
    signature=signature
)
```

#### Properties

##### `public_key`

```python
@property
def public_key() -> bytes
```

Agent's public key (raw bytes).

##### `public_key_hex`

```python
@property
def public_key_hex() -> str
```

Agent's public key as hex string.

**Example:**
```python
print(f"Agent ID: {core.identity.public_key_hex}")
```

---

### AsyncLedger

Manages audit logging to backend.

#### Methods

##### `log_operation()`

```python
async def log_operation(
    tool_name: str,
    status: str,
    duration_ms: float,
    parameters: dict,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None
) -> None
```

Log an operation to the audit trail.

**Parameters:**
- `tool_name` (str): Name of the operation
- `status` (str): Status ("success", "denied", "error")
- `duration_ms` (float): Duration in milliseconds
- `parameters` (dict): Operation parameters
- `result` (dict, optional): Operation result
- `error` (str, optional): Error message if failed
- `metadata` (dict, optional): Additional metadata

**Note:** Logging is automatic when using `@core.guard()`. Manual logging is rarely needed.

**Example:**
```python
await core.ledger.log_operation(
    tool_name="custom_operation",
    status="success",
    duration_ms=15.5,
    parameters={"param": "value"},
    result={"output": "data"}
)
```

---

## Decorators

### @core.guard()

The primary way to protect functions with Hashed.

**Signature:**
```python
@core.guard(tool_name: str)
async def your_function(...) -> Any:
    ...
```

**What it does:**
1. ✅ Validates operation against policy
2. ✅ Signs operation with crypto identity
3. ✅ Executes function if allowed
4. ✅ Logs result to audit trail
5. ✅ Handles errors gracefully

**Example:**
```python
@core.guard("process_refund")
async def process_refund(amount: float, order_id: str, reason: str):
    """Process customer refund."""
    # Your logic here
    stripe.refunds.create(amount=amount, order_id=order_id)
    return {"status": "refunded", "amount": amount}

# Usage
try:
    result = await process_refund(100.0, "ORD-123", "damaged")
    print(f"Success: {result}")
except PermissionError as e:
    print(f"Blocked: {e}")
```

---

## Models

All models use Pydantic for validation and serialization.

### Policy

```python
class Policy(BaseModel):
    tool_name: str
    allowed: bool = True
    max_amount: Optional[float] = None
    requires_approval: bool = False
    metadata: Optional[dict] = None
```

**Example:**
```python
from hashed.models import Policy

policy = Policy(
    tool_name="transfer_money",
    allowed=True,
    max_amount=500.0
)
```

### Agent

```python
class Agent(BaseModel):
    name: str
    type: str
    public_key: str
    status: str = "active"
```

### LogEntry

```python
class LogEntry(BaseModel):
    tool_name: str
    status: str
    timestamp: datetime
    duration_ms: float
    parameters: dict
    result: Optional[dict] = None
    error: Optional[str] = None
    public_key: str
    signature: str
```

---

## Exceptions

### PermissionError

```python
class PermissionError(Exception):
    """Raised when operation is not allowed by policy."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        self.details = details
        super().__init__(message)
```

**Example:**
```python
from hashed.exceptions import PermissionError

try:
    await transfer_money(10000)
except PermissionError as e:
    print(e)  # "Amount 10000 exceeds maximum allowed 500.0"
    print(e.details)  # {'tool_name': 'transfer_money', 'amount': 10000, ...}
```

### PolicyNotFoundError

```python
class PolicyNotFoundError(Exception):
    """Raised when policy is not found."""
```

### AuthenticationError

```python
class AuthenticationError(Exception):
    """Raised when API key is invalid."""
```

---

## Utilities

### HTTP Client

```python
from hashed.utils.http_client import AsyncHTTPClient

# Used internally, but available if needed
client = AsyncHTTPClient(
    base_url="http://localhost:8000",
    api_key="your-key",
    timeout=30
)

response = await client.get("/endpoint")
```

### Crypto Utilities

```python
from hashed.crypto.hasher import hash_data, verify_hash

# Hash data
hash_value = hash_data("sensitive data")

# Verify
is_valid = verify_hash("sensitive data", hash_value)
```

---

## Complete Usage Example

```python
import asyncio
from hashed import HashedCore
from hashed.config import HashedConfig
from hashed.exceptions import PermissionError

async def main():
    # 1. Configuration
    config = HashedConfig(
        backend_url="http://localhost:8000",
        api_key="your-api-key",
        enable_auto_sync=True
    )
    
    # 2. Initialize
    core = HashedCore(
        config=config,
        agent_name="My Agent",
        agent_type="custom"
    )
    await core.initialize()
    
    # 3. Define operations
    @core.guard("send_email")
    async def send_email(to: str, subject: str, body: str):
        # Your email logic
        print(f"Sending email to {to}")
        return {"sent": True}
    
    @core.guard("transfer_money")
    async def transfer_money(amount: float, to: str):
        # Your transfer logic
        print(f"Transferring ${amount} to {to}")
        return {"status": "success", "amount": amount}
    
    # 4. Use operations
    try:
        # Allowed
        await send_email("user@example.com", "Hello", "World")
        
        # May be blocked by policy
        await transfer_money(10000.0, "recipient")
        
    except PermissionError as e:
        print(f"Operation blocked: {e}")
        print(f"Details: {e.details}")
    
    finally:
        # 5. Cleanup
        await core.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Backend Requirements

The SDK requires a running backend server:

```bash
# Start backend
cd /path/to/hashed-sdk/server
python3 server.py

# Backend runs on http://localhost:8000
```

Optional dashboard:
```bash
cd /path/to/hashed-sdk/dashboard
npm run dev

# Dashboard on http://localhost:3000
```

---

## Type Hints

All public APIs include complete type hints for IDE support:

```python
from hashed import HashedCore
from hashed.config import HashedConfig
from hashed.models import Policy
from typing import Optional

# Full IntelliSense/autocomplete support
config: HashedConfig = HashedConfig()
core: HashedCore = HashedCore(config=config)
policy: Optional[Policy] = core.policy_engine.get_policy("tool")
```

---

## Quick Reference

```python
# Initialize
from hashed import HashedCore
from hashed.config import HashedConfig

config = HashedConfig()  # Auto-loads from .env
core = HashedCore(config=config, agent_name="Agent", agent_type="type")
await core.initialize()

# Guard functions
@core.guard("operation_name")
async def my_operation(param: str):
    return {"result": "value"}

# Use
result = await my_operation("test")

# Shutdown
await core.shutdown()
```

---

For more examples, see `/examples` directory in the SDK repository.
