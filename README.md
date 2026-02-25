# Hashed SDK

**Governance & Audit Framework for AI Agents**

A professional Python SDK that provides cryptographic identity, policy enforcement, and immutable audit logging for AI agents. Built for production-grade AI systems that require accountability, compliance, and security.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What is Hashed?

Hashed is a complete governance framework for AI agents that ensures:

- **🔐 Cryptographic Identity**: Ed25519 keypairs for agent authentication
- **🛡️ Policy Enforcement**: Define and enforce rules for agent operations  
- **📝 Immutable Audit Trail**: Every operation is cryptographically signed and logged
- **🎛️ Control Dashboard**: Web UI for monitoring agents, policies, and operations
- **💾 Persistent Identity**: Agents maintain identity across restarts
- **🔄 Real-time Sync**: Policies and logs sync automatically with backend

**Perfect for:** Customer service bots, data analysis agents, autonomous trading systems, or any AI agent that needs governance.

---

## ✨ Key Features

### 🔐 Identity Management
- **Cryptographic Identities**: Ed25519 keypairs for each agent
- **Persistent Storage**: Encrypted key storage with AES-256
- **Automatic Registration**: Agents self-register with backend on startup
- **Signature Verification**: All operations cryptographically signed

### 🛡️ Policy Enforcement  
- **Declarative Policies**: Define max amounts, allow/deny, approval requirements
- **Local + Remote**: Policies enforced locally and validated with backend
- **@guard Decorator**: Protect any function with a simple decorator
- **Real-time Sync**: Policies sync automatically from control plane

### 📝 Audit Logging
- **Immutable Trail**: All operations logged with signatures
- **Success + Failures**: Log both successful and denied operations
- **Rich Metadata**: Capture context, amounts, timestamps, errors
- **Dashboard Visibility**: All logs visible in real-time web UI

### 🎛️ Control Dashboard
- **Agent Monitoring**: Track all registered agents
- **Policy Management**: View and create governance rules
- **Audit Logs**: Search and filter operation history
- **Real-time Updates**: Auto-refresh every 5 seconds

---

## 🚀 Quick Start

### Installation

```bash
# Install the SDK
pip install -e git+https://github.com/yourrepo/hashed.git#egg=hashed-sdk

# Or for local development
cd hashed-sdk
pip install -e .
```

### Basic Usage

```python
import asyncio
from hashed import HashedCore, HashedConfig

# Configure connection to backend
config = HashedConfig(
    backend_url="http://localhost:8000",
    api_key="your_api_key_here"
)

# Create core with identity
core = HashedCore(
    config=config,
    agent_name="My First Agent",
    agent_type="customer_service"
)

async def main():
    # Initialize (registers agent, syncs policies)
    await core.initialize()
    
    # Define a guarded operation
    @core.guard("send_email")
    async def send_email(to: str, subject: str, body: str):
        # Your email logic here
        return {"status": "sent", "to": to}
    
    # Execute - automatically validated and logged
    result = await send_email(
        to="user@example.com",
        subject="Hello",
        body="Test message"
    )
    
    # Cleanup
    await core.shutdown()

asyncio.run(main())
```

---

## 📚 Core Concepts

### 1. Cryptographic Identity

Each agent has a unique Ed25519 keypair that identifies it:

```python
from hashed import IdentityManager

# Generate new identity (ephemeral)
identity = IdentityManager()
print(f"Public Key: {identity.public_key_hex}")

# Sign operations
signature = identity.sign_message("operation_data")

# Verify signatures
is_valid = identity.verify_signature("operation_data", signature)
```

### 2. Persistent Identity

For agents that need to maintain identity across restarts:

```python
from hashed import load_or_create_identity
import os

# Load existing or create new (with encryption)
identity = load_or_create_identity(
    filepath="./secrets/agent_key.pem",
    password=os.getenv("AGENT_PASSWORD")
)

# Use with HashedCore
core = HashedCore(
    config=config,
    identity=identity,  # ← Persistent identity
    agent_name="My Agent"
)
```

**Benefits:**
- Same public key across restarts
- Continuous audit trail
- Dashboard shows single agent (not duplicates)
- Policy targeting by specific agent

### 3. Policy Enforcement

Define rules for what agents can/cannot do:

```python
# Add policies locally
core.policy_engine.add_policy(
    tool_name="send_email",
    allowed=True,
    max_amount=100.0,  # Max 100 emails
    metadata={"description": "Email sending policy"}
)

core.policy_engine.add_policy(
    tool_name="delete_database",
    allowed=False,  # Completely blocked
    metadata={"reason": "Too dangerous"}
)

# Push policies to dashboard (so they're visible)
await core.push_policies_to_backend()
```

### 4. Guarded Operations

Protect operations with the `@guard` decorator:

```python
@core.guard("transfer_money", amount_param="amount")
async def transfer_money(amount: float, to_account: str):
    """
    Transfer money with automatic:
    - Policy validation
    - Operation signing  
    - Audit logging
    - Error handling
    """
    # Your transfer logic
    return {"status": "completed", "amount": amount}

# Execute - policy is checked automatically
try:
    result = await transfer_money(amount=500.0, to_account="12345")
    print("Transfer successful")
except PermissionError as e:
    print(f"Transfer blocked: {e}")
```

**What happens:**
1. Local policy check (fast)
2. Backend policy validation (if connected)
3. Operation signing with agent identity
4. Function execution (if allowed)
5. Result logged to backend/ledger
6. If denied: PermissionError raised, denial logged

### 5. Audit Trail

Every operation is automatically logged:

```python
# Logs are sent automatically, no manual logging needed
await send_email(to="user@example.com", ...)

# View in dashboard: http://localhost:3000/dashboard/logs
# Or query programmatically via backend API
```

**Each log entry contains:**
- Tool name
- Status (success/denied/error)
- Timestamp
- Agent public key
- Cryptographic signature
- Operation parameters (sanitized)
- Result or error message

---

## 🎨 Examples

### Complete Agent with LLM Integration

```python
"""
AI Agent with OpenAI + Hashed Governance
"""
import asyncio
from openai import AsyncOpenAI
from hashed import HashedCore, HashedConfig, load_or_create_identity

# Initialize
openai = AsyncOpenAI()
identity = load_or_create_identity("./secrets/agent.pem", "password123")
core = HashedCore(
    config=HashedConfig(),
    identity=identity,
    agent_name="Customer Service Bot",
    agent_type="customer_service"
)

async def main():
    await core.initialize()
    
    # Define policies
    core.policy_engine.add_policy("send_email", allowed=True, max_amount=50.0)
    core.policy_engine.add_policy("refund", allowed=True, max_amount=500.0)
    core.policy_engine.add_policy("database_delete", allowed=False)
    
    # Push to dashboard
    await core.push_policies_to_backend()
    
    # Define guarded tools
    @core.guard("send_email", amount_param="count")
    async def send_email(to: str, subject: str, count: int = 1):
        # Email logic
        return {"sent": count}
    
    @core.guard("process_refund", amount_param="amount")
    async def process_refund(amount: float, reason: str):
        # Refund logic
        return {"refunded": amount}
    
    # Use with LLM
    tools = [
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send email to customer",
                "parameters": { ... }
            }
        },
        # ... more tools
    ]
    
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Send refund email"}],
        tools=tools
    )
    
    # Execute tool calls (with automatic governance)
    for tool_call in response.choices[0].message.tool_calls:
        if tool_call.function.name == "send_email":
            result = await send_email(**json.loads(tool_call.function.arguments))
    
    await core.shutdown()

asyncio.run(main())
```

See [examples/](examples/) for more:
- [persistent_agent.py](examples/persistent_agent.py) - Full persistent identity example
- [basic_usage.py](examples/basic_usage.py) - Simple getting started
- [async_usage.py](examples/async_usage.py) - Async patterns

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your AI Agent                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  HashedCore (SDK)                                │   │
│  │  • IdentityManager (Ed25519)                     │   │
│  │  • PolicyEngine (Local validation)               │   │
│  │  • @guard decorator                              │   │
│  │  • AsyncLedger (Logging)                         │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                    HTTPS │ (mTLS ready)
                          │
┌─────────────────────────▼───────────────────────────────┐
│              Backend API (FastAPI)                      │
│  • Agent registration                                   │
│  • Policy storage & sync                                │
│  • Audit log persistence                                │
│  • Signature verification                               │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Supabase
                          ▼
┌─────────────────────────────────────────────────────────┐
│               PostgreSQL Database                        │
│  • agents (registry)                                    │
│  • policies (rules)                                     │
│  • ledger_logs (immutable audit trail)                 │
│  • organizations (multi-tenant)                         │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Real-time
                          ▼
┌─────────────────────────────────────────────────────────┐
│            Dashboard (Next.js + React)                  │
│  • Agent monitoring                                     │
│  • Policy management                                    │
│  • Audit log viewer (auto-refresh)                     │
│  • Analytics & reports                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Project Structure

```
hashed-sdk/
├── src/hashed/
│   ├── __init__.py              # Main exports
│   ├── core.py                  # HashedCore (main class)
│   ├── config.py                # Configuration
│   ├── identity.py              # IdentityManager (Ed25519)
│   ├── identity_store.py        # Persistent identity functions
│   ├── guard.py                 # PolicyEngine + @guard
│   ├── ledger.py                # AsyncLedger (logging)
│   ├── exceptions.py            # Custom exceptions
│   ├── models.py                # Pydantic models
│   ├── client.py                # Legacy client (deprecated)
│   ├── crypto/                  # Cryptography
│   │   ├── __init__.py
│   │   └── hasher.py
│   └── utils/                   # Utilities
│       ├── __init__.py
│       └── http_client.py
├── tests/                       # Test suite
│   ├── test_core.py
│   ├── test_identity.py
│   ├── test_identity_store.py
│   ├── test_guard.py
│   └── ...
├── examples/                    # Usage examples
│   ├── persistent_agent.py
│   ├── basic_usage.py
│   └── secrets/.gitignore
├── server/                      # Backend API
│   ├── server.py               # FastAPI app
│   ├── requirements.txt
│   └── README.md
├── dashboard/                   # Web UI (Next.js)
│   ├── app/
│   ├── lib/
│   └── package.json
├── database/                    # DB schema
│   └── schema.sql
├── docs/                        # Documentation
│   ├── API_REFERENCE.md
│   ├── INTEGRATION.md
│   ├── SECURITY.md
│   └── USAGE_FROM_OTHER_PROJECT.md
└── pyproject.toml              # Project config
```

---

## 🛠️ Development

### Setup

```bash
# Clone repo
git clone https://github.com/yourrepo/hashed-sdk.git
cd hashed-sdk

# Install SDK
pip install -e .

# Start backend
cd server
pip install -r requirements.txt
python server.py

# Start dashboard (separate terminal)
cd dashboard
npm install
npm run dev

# Run tests
pytest
```

### Running the Full Stack

```bash
# Terminal 1: Backend
cd server && python server.py

# Terminal 2: Dashboard  
cd dashboard && npm run dev

# Terminal 3: Your agent
python your_agent.py

# Access dashboard
open http://localhost:3000
```

---

## 🔒 Security

### Identity Storage

Persistent identities are stored encrypted:

```python
# Encrypted with AES-256
identity = load_or_create_identity(
    filepath="./secrets/agent.pem",
    password="strong_password_from_env"  # Never hardcode!
)

# File permissions: 0600 (owner read/write only)
# Password from: Environment variable, secrets manager, etc.
```

### Best Practices

✅ **DO:**
- Use environment variables for passwords
- Store keys in `./secrets/` with `.gitignore`
- Use strong passwords (32+ chars, generated)
- Rotate keys periodically
- Use mTLS for production backend
- Review audit logs regularly

❌ **DON'T:**
- Hardcode passwords in code
- Commit `.pem` files to git
- Reuse passwords across agents
- Disable signature verification
- Ignore policy violations in logs

See [SECURITY.md](SECURITY.md) for complete security guide.

---

## 📖 Documentation

- **[API Reference](API_REFERENCE.md)** - Complete API docs
- **[Integration Guide](INTEGRATION.md)** - Integrate with your project
- **[Setup Guide](SETUP_GUIDE.md)** - Production setup
- **[Security Guide](SECURITY.md)** - Security best practices
- **[Usage from Other Projects](USAGE_FROM_OTHER_PROJECT.md)** - External usage

---

## 🔄 Recent Updates

### v0.2.0 (Latest)

**New Features:**
- ✨ Persistent identity system (`load_or_create_identity`)
- ✨ Push policies to dashboard (`push_policies_to_backend`)
- ✨ Auto-refresh dashboard (5 second polling)
- 🐛 Fixed double logging issue (backend OR local, not both)
- 📝 Complete documentation overhaul

**Breaking Changes:**
- `HashedClient` deprecated → Use `HashedCore`
- Hashing-focused API removed (use `cryptography` directly)

### v0.1.0

- 🔐 Cryptographic identity (Ed25519)
- 🛡️ Policy engine with `@guard` decorator
- 📝 Immutable audit logging
- 🎛️ Web dashboard (Next.js)
- 🔄 Auto-sync with backend

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- [cryptography](https://cryptography.io/) - Ed25519, AES-256
- [FastAPI](https://fastapi.tiangolo.com/) - Backend API
- [Next.js](https://nextjs.org/) - Dashboard UI
- [Supabase](https://supabase.com/) - Database + Auth
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourrepo/hashed-sdk/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourrepo/hashed-sdk/discussions)
- **Email**: support@hashed.example.com

---

**Built with ❤️ for responsible AI**
