# Hashed SDK - Backend Integration Guide

Complete guide for integrating the Hashed SDK with the Control Plane backend.

## 🎯 Overview

The Hashed SDK provides **AI Agent Governance** through a client-server architecture:

```
┌─────────────────┐        ┌──────────────────┐        ┌─────────────────┐
│   AI Agent      │◄──────►│  Hashed SDK      │◄──────►│  Backend API    │
│  (Your Code)    │        │  (Client)        │        │  (Control Plane)│
└─────────────────┘        └──────────────────┘        └─────────────────┘
                                    │                            │
                                    │                            │
                           ┌────────▼────────┐          ┌────────▼────────┐
                           │  - Identity     │          │  - Policies     │
                           │  - Policy Cache │          │  - Audit Logs   │
                           │  - Local Guard  │          │  - Analytics    │
                           └─────────────────┘          └─────────────────┘
```

## 📋 Prerequisites

### 1. Database Setup (Supabase)

```bash
# 1. Create a Supabase project at https://supabase.com
# 2. Run the schema in the SQL Editor
cat database/schema.sql | pbcopy  # Copy to clipboard
# Paste into Supabase SQL Editor and execute
```

### 2. Backend Server

```bash
# Install dependencies
cd server
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Start server
python server.py
```

Server will be available at `http://localhost:8000`

### 3. SDK Installation

```bash
# Install the SDK
pip install -e .
```

## 🚀 Quick Start

### Step 1: Configure SDK with Backend

```python
from hashed import HashedCore
from hashed.config import HashedConfig

# Create configuration
config = HashedConfig(
    backend_url="http://localhost:8000",
    api_key="your-api-key-here",
    enable_auto_sync=True,
    sync_interval=300,  # Sync every 5 minutes
)

# Create core with agent info
core = HashedCore(
    config=config,
    agent_name="Customer Service Bot",
    agent_type="customer_service",
)
```

### Step 2: Initialize (Auto-registration & Sync)

```python
# Initialize performs:
# 1. Registers agent with backend (if not exists)
# 2. Downloads policies from backend
# 3. Starts audit ledger
# 4. Starts background policy sync
await core.initialize()
```

### Step 3: Define Tools with @guard Decorator

```python
@core.guard("transfer_money")
async def transfer_money(amount: float, to_account: str):
    # Your tool logic here
    return {"status": "success", "amount": amount}

@core.guard("read_database")
async def read_data(query: str):
    # Your logic here
    return {"data": [...]}
```

### Step 4: Execute Operations

```python
# Operations are automatically:
# - Signed with agent identity
# - Validated against policies
# - Logged to backend for audit

try:
    result = await transfer_money(amount=500, to_account="alice")
    print(f"Success: {result}")
except PermissionError as e:
    print(f"Blocked: {e}")
```

### Step 5: Cleanup

```python
# Shutdown gracefully
await core.shutdown()
```

## 🔄 How It Works

### 1. Initialization Flow

```
SDK Startup
    ↓
┌───────────────────────────────────────┐
│ 1. Generate/Load Ed25519 Identity    │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 2. POST /v1/agents/register           │
│    → Agent registered in backend      │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 3. GET /v1/policies/sync              │
│    → Download policies to local cache │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 4. Start AsyncLedger worker           │
│    → Queue logs for backend           │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 5. Start background sync task         │
│    → Re-sync policies every N minutes │
└───────────────────────────────────────┘
```

### 2. Operation Execution Flow

```
@core.guard("tool_name")
async def tool(...):
    ↓
┌─────────────────────────────────────────────┐
│ 1. Validate against cached policies        │
│    (Fast - no network call)                 │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 2. Sign operation with Ed25519 identity    │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 3. Execute tool function                    │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 4. Queue audit log (non-blocking)          │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 5. AsyncLedger batches and sends to        │
│    POST /v1/logs/batch (every 5s)          │
└─────────────────────────────────────────────┘
```

### 3. Policy Sync Flow

```
Background Task (every 5 minutes)
    ↓
┌─────────────────────────────────────────────┐
│ GET /v1/policies/sync?agent_public_key=...│
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ Update local PolicyEngine cache            │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ New policies take effect immediately       │
│ (no restart required)                       │
└─────────────────────────────────────────────┘
```

## 📖 Complete Example

See `examples/backend_integration.py` for a full working example.

```bash
# Run the example
python examples/backend_integration.py
```

## 🎛️ Configuration Options

### HashedConfig Parameters

```python
config = HashedConfig(
    # Backend Configuration
    backend_url="http://localhost:8000",
    api_key="your-api-key-here",
    
    # Policy Sync
    enable_auto_sync=True,      # Auto-sync policies
    sync_interval=300,          # Seconds between syncs
    
    # HTTP Settings
    timeout=30.0,               # Request timeout
    max_retries=3,              # Retry failed requests
    verify_ssl=True,            # SSL verification
    
    # Ledger
    ledger_endpoint="/v1/logs/batch",  # Log endpoint path
    
    # Debug
    debug=False,                # Enable debug logging
)
```

### HashedCore Parameters

```python
core = HashedCore(
    config=config,
    agent_name="My Agent",             # Agent name (for registration)
    agent_type="customer_service",     # Agent type category
    identity=None,                     # Optional: provide existing identity
    ledger_endpoint=None,              # Optional: override ledger endpoint
)
```

## 🔧 Managing Policies

### Via Backend API

```bash
# List all policies
curl http://localhost:8000/v1/policies \
  -H "X-API-KEY: your-api-key"

# Create new policy
curl -X POST http://localhost:8000/v1/policies \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "transfer_money",
    "max_amount": 1000.0,
    "allowed": true
  }'

# Policy will be synced to agents automatically
```

### Via Dashboard (Future)

A web dashboard will provide:
- Visual policy editor
- Real-time agent monitoring
- Audit log viewer
- Analytics and insights

## 📊 Querying Audit Logs

### Via API

```bash
# Get recent logs
curl "http://localhost:8000/v1/logs?limit=100" \
  -H "X-API-KEY: your-api-key"

# Filter by agent
curl "http://localhost:8000/v1/logs?agent_id=xxx&limit=50" \
  -H "X-API-KEY: your-api-key"

# Filter by tool
curl "http://localhost:8000/v1/logs?tool_name=transfer_money" \
  -H "X-API-KEY: your-api-key"

# Filter by status
curl "http://localhost:8000/v1/logs?status_filter=denied" \
  -H "X-API-KEY: your-api-key"
```

### Analytics Summary

```bash
curl http://localhost:8000/v1/analytics/summary \
  -H "X-API-KEY: your-api-key"
```

Returns:
- Agent activity summary
- Policy effectiveness metrics
- Success/failure rates
- Most used tools

## 🚨 Error Handling

### Agent Registration Failures

```python
try:
    await core.initialize()
except Exception as e:
    if "registration failed" in str(e):
        # Agent already exists or network issue
        logger.warning(f"Registration issue: {e}")
        # SDK continues with cached policies if available
```

### Policy Sync Failures

```python
# Sync failures are non-fatal
# SDK continues using cached policies
try:
    await core.sync_policies_from_backend()
except Exception as e:
    logger.error(f"Policy sync failed: {e}")
    # Agent continues with last known policies
```

### Ledger Send Failures

```python
# Logs are queued and retried automatically
# No action needed - AsyncLedger handles retries
```

## 🔒 Security Best Practices

### 1. API Key Management

```python
# ❌ DON'T hardcode API keys
config = HashedConfig(api_key="test_key_123...")

# ✅ DO use environment variables
import os
config = HashedConfig(
    api_key=os.getenv("HASHED_API_KEY")
)
```

### 2. SSL/TLS in Production

```python
# ✅ Always verify SSL in production
config = HashedConfig(
    backend_url="https://api.hashed.com",  # HTTPS
    verify_ssl=True,                        # Verify cert
)
```

### 3. Identity Management

```python
# ✅ Persist and reuse agent identities
from hashed import IdentityManager

# Export identity
private_key_pem = identity.export_private_key(password=b"secure_password")
with open("agent_identity.pem", "wb") as f:
    f.write(private_key_pem)

# Reload identity
with open("agent_identity.pem", "rb") as f:
    identity = IdentityManager.from_private_key_bytes(
        f.read(),
        password=b"secure_password"
    )
```

## 🎯 Use Cases

### 1. Customer Service Agent

```python
config = HashedConfig(...)
core = HashedCore(config, agent_name="CS Bot", agent_type="customer_service")
await core.initialize()

# Policies (managed in backend):
# - customer_chat: allowed
# - access_pii: allowed
# - make_refund: max_amount=100
# - modify_orders: allowed=False
```

### 2. Data Analysis Agent

```python
core = HashedCore(config, agent_name="Analytics Bot", agent_type="data_analysis")

# Policies:
# - db_read: allowed
# - db_write: allowed=False
# - generate_report: allowed
# - external_api: allowed=False
```

### 3. DevOps Agent

```python
core = HashedCore(config, agent_name="Deploy Bot", agent_type="devops")

# Policies:
# - deploy_staging: allowed
# - deploy_production: requires_approval=True
# - rollback: allowed
# - ssh_access: time_window="business_hours"
```

## 📈 Monitoring & Observability

### Logging

```python
import logging

# Enable SDK logging
logging.basicConfig(level=logging.INFO)

# Or configure specific loggers
logging.getLogger("hashed.core").setLevel(logging.DEBUG)
logging.getLogger("hashed.ledger").setLevel(logging.INFO)
```

### Metrics to Track

1. **Policy Violations**: Denied operations count
2. **Sync Health**: Policy sync success rate
3. **Ledger Health**: Log delivery success rate
4. **Operation Latency**: Time from request to completion

## 🐛 Troubleshooting

### Issue: "Agent registration failed"

**Solution**: Check backend is running and accessible

```bash
curl http://localhost:8000/health
```

### Issue: "Policy sync failed"

**Solution**: Verify API key and agent exists

```bash
curl http://localhost:8000/v1/agents \
  -H "X-API-KEY: your-api-key"
```

### Issue: Logs not appearing in backend

**Solution**: Flush ledger manually and check logs

```python
await core.ledger.flush()
# Check backend logs
```

### Issue: Policies not updating

**Solution**: Trigger manual sync

```python
await core.sync_policies_from_backend()
```

## 🔄 Migration from Standalone to Backend

```python
# OLD: Standalone mode
core = create_core(
    ledger_endpoint="https://...",
    policies={
        "transfer": {"max_amount": 1000},
    }
)

# NEW: Backend-integrated mode
config = HashedConfig(
    backend_url="http://localhost:8000",
    api_key="your-api-key",
)
core = HashedCore(config=config, agent_name="My Agent")
# Policies loaded automatically from backend!
```

## 📚 Additional Resources

- **SDK Documentation**: See `README.md`
- **Backend API**: See `server/README.md`
- **Database Schema**: See `database/schema.sql`
- **Examples**: See `examples/` directory

## 💬 Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/hashed-sdk
- Documentation: https://docs.hashed.dev
- Email: support@hashed.dev
