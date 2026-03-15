# Using Hashed SDK From Another Project

This guide explains how to use the Hashed SDK from a separate Python project.

---

## 🚀 Quick Start

### Step 1: Install the SDK

**Option A: From PyPI** *(recommended)*
```bash
pip install hashed-sdk
```

**Option B: From GitHub**
```bash
pip install git+https://github.com/Josoriop9/IAMandagent.git
```

**Option C: From Local Path** (Development)
```bash
cd /path/to/your/project
pip install -e /path/to/cloned/IAMandagent
```

### Step 2: Start the Backend

The SDK requires the Hashed backend to be running:

```bash
# In a separate terminal
cd /path/to/IAMandagent/server
python3 server.py
```

**Backend will run on:** `http://localhost:8000`

### Step 3: Configure Your Project

Create a `.env` file in your project root:

```bash
# .env
BACKEND_URL=http://localhost:8000
API_KEY=hashed_your_api_key_here
```

### Step 4: Use in Your Code

```python
import asyncio
from hashed import HashedCore
from hashed.config import HashedConfig

async def main():
    # Initialize
    config = HashedConfig()  # Auto-loads from .env
    core = HashedCore(
        config=config,
        agent_name="Your Agent",
        agent_type="your_type"
    )
    await core.initialize()
    
    # Define operations
    @core.guard("your_operation")
    async def do_something(param: str):
        # Your logic here
        return {"result": param}
    
    # Use
    result = await do_something("test")
    print(result)
    
    # Cleanup
    await core.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📁 Project Structure

### Your Project

```
your-project/
├── .env                  # ← Hashed configuration
├── requirements.txt      # ← Include hashed-sdk
├── your_agent.py         # ← Your agent code
└── README.md
```

### Hashed SDK (Separate — if running backend locally)

```
IAMandagent/
├── server/
│   └── server.py         # ← Must be running
├── dashboard/            # ← Optional
├── src/hashed/           # ← SDK source
└── examples/             # ← Reference examples
```

---

## 🔧 Complete Setup Guide

### 1. Dependencies

**requirements.txt** in your project:
```txt
# From PyPI (recommended)
hashed-sdk

# Or from GitHub
# hashed-sdk @ git+https://github.com/Josoriop9/IAMandagent.git

# Optional: If using with LLM
openai>=1.0.0
```

Install dependencies:
```bash
cd /path/to/your/project
pip install -r requirements.txt
```

### 2. Environment Configuration

**.env** file:
```bash
# Backend connection
BACKEND_URL=http://localhost:8000
API_KEY=hashed_your_api_key_here

# Optional: Enable auto-sync
ENABLE_AUTO_SYNC=true
SYNC_INTERVAL=300

# Optional: If using OpenAI
OPENAI_API_KEY=sk-your-key-here
```

### 3. Backend Services

**Terminal 1: Start Backend**
```bash
cd /path/to/IAMandagent/server
python3 server.py

# Output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2: Start Dashboard** (Optional)
```bash
cd /path/to/IAMandagent/dashboard
npm run dev

# Output:
# ready - started server on 0.0.0.0:3000
```

**Terminal 3: Your Agent**
```bash
cd /path/to/your/project
python3 your_agent.py
```

---

## 💻 Example Agent

Create `your_agent.py`:

```python
"""
Your Custom Agent Using Hashed SDK
"""

import asyncio
from hashed import HashedCore
from hashed.config import HashedConfig
from hashed.exceptions import PermissionError


async def main():
    # 1. Configuration
    config = HashedConfig(
        backend_url="http://localhost:8000",
        api_key=os.getenv("HASHED_API_KEY"),
        enable_auto_sync=True
    )
    
    # 2. Initialize agent
    core = HashedCore(
        config=config,
        agent_name="My Custom Agent",
        agent_type="custom_type"
    )
    
    print("Initializing agent...")
    await core.initialize()
    print(f"✓ Agent initialized: {core.identity.public_key_hex[:16]}...")
    
    # 3. Define operations with @guard
    @core.guard("process_data")
    async def process_data(data: str, amount: float):
        """Process some data with governance."""
        print(f"Processing: {data}, amount: ${amount}")
        # Your business logic here
        return {"status": "processed", "data": data, "amount": amount}
    
    @core.guard("send_notification")
    async def send_notification(message: str, recipient: str):
        """Send a notification."""
        print(f"Sending '{message}' to {recipient}")
        # Your notification logic here
        return {"sent": True, "recipient": recipient}
    
    # 4. Use your operations
    try:
        # This will be validated and logged
        result1 = await process_data("test-data", 100.0)
        print(f"Result: {result1}")
        
        result2 = await send_notification("Hello", "user@example.com")
        print(f"Result: {result2}")
        
    except PermissionError as e:
        print(f"❌ Operation blocked: {e}")
        print(f"Details: {e.details}")
    
    # 5. Cleanup
    print("\nShutting down...")
    await core.shutdown()
    print("✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python3 your_agent.py
```

---

## 🔒 Setting Up Policies

### Option 1: Via Backend API

```python
import httpx
import asyncio

async def setup_policies():
    async with httpx.AsyncClient() as client:
        # Create policy
        response = await client.post(
            "http://localhost:8000/v1/policies",
            headers={"X-API-KEY": "your-api-key"},
            json={
                "tool_name": "process_data",
                "allowed": True,
                "max_amount": 1000.0
            }
        )
        print(f"Policy created: {response.status_code}")

asyncio.run(setup_policies())
```

### Option 2: Local Policies (Testing)

```python
# In your agent code
core = HashedCore()
await core.initialize()

# Add local policies (not synced to backend)
core.policy_engine.add_policy("process_data", allowed=True, max_amount=500.0)
core.policy_engine.add_policy("send_notification", allowed=True)
core.policy_engine.add_policy("delete_data", allowed=False)
```

### Option 3: Via Dashboard

1. Open http://localhost:3000/dashboard
2. Go to "Policies" tab
3. Click "Create Policy"
4. Fill in details
5. Save

Policies automatically sync to your agent if `enable_auto_sync=True`.

---

## 🎯 For Cline (AI Assistant)

If you're using Cline in your other project, give it this context:

```
You are working on a Python project that uses the Hashed SDK for AI agent governance.

**Hashed SDK Documentation:**
- GitHub: https://github.com/Josoriop9/IAMandagent
- PyPI: https://pypi.org/project/hashed-sdk/
- API_REFERENCE.md, CLI_GUIDE.md, FRAMEWORK_GUIDES.md, INTEGRATION.md

**Installation:**
pip install hashed-sdk

**Required Backend:**
The Hashed backend runs at https://iamandagent-production.up.railway.app
(or locally: cd IAMandagent/server && python3 server.py)

**Basic Usage:**
from hashed import HashedCore
from hashed.config import HashedConfig

config = HashedConfig()
core = HashedCore(config=config, agent_name="Agent", agent_type="type")
await core.initialize()

@core.guard("operation")
async def my_function():
    # Your logic
    return {"result": "value"}

await my_function()
await core.shutdown()

**Environment:**
Create .env with:
HASHED_API_KEY=hashed_your_api_key_here  # Get via: hashed login
HASHED_BACKEND_URL=https://iamandagent-production.up.railway.app
```

---

## 🐛 Troubleshooting

### Error: "Cannot connect to backend"

**Solution:**
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not, start it
cd /path/to/IAMandagent/server
python3 server.py
```

### Error: "ModuleNotFoundError: No module named 'hashed'"

**Solution:**
```bash
# Install from PyPI
pip install hashed-sdk

# Or verify installation
pip list | grep hashed
```

### Error: "Authentication failed"

**Solution:**
Check your `.env` file has the correct `API_KEY` (get it via `hashed login`):
```bash
API_KEY=hashed_your_api_key_here
```

### Error: "Permission denied for operation"

**Solution:**
Check policies in dashboard or create policy:
```python
core.policy_engine.add_policy("your_operation", allowed=True)
```

---

## 📊 Viewing Results

### Dashboard

Open http://localhost:3000/dashboard to see:
- **Agents**: Your agent listed with status
- **Policies**: All active policies
- **Logs**: All operations (success/denied/error)

### Backend Logs

Check terminal where backend is running:
```
INFO: Agent registered: your_agent_public_key
INFO: Operation logged: process_data - success
INFO: Operation logged: send_notification - success
```

---

## ✅ Checklist

Before running your agent:

- [ ] Backend running (`http://localhost:8000`)
- [ ] SDK installed in your project
- [ ] `.env` file configured
- [ ] Policies created (or local policies set)
- [ ] Code imports `from hashed import HashedCore`
- [ ] Agent calls `await core.initialize()`
- [ ] Operations decorated with `@core.guard()`
- [ ] Agent calls `await core.shutdown()` on exit

---

## 🚀 Next Steps

1. **Read API_REFERENCE.md** for complete API documentation
2. **Check examples/** for more complex use cases
3. **Read SECURITY.md** for security best practices
4. **View dashboard** to see your agent in action

---

## 📚 Additional Resources

- **API Reference**: [docs/API_REFERENCE.md](API_REFERENCE.md)
- **Security Guide**: [SECURITY.md](../SECURITY.md)
- **Examples**: [examples/](../examples/)
- **Integration Guide**: [docs/INTEGRATION.md](INTEGRATION.md)

---

## 💡 Pro Tips

### Tip 1: Use Context Manager

```python
async with HashedCore(config=config) as core:
    @core.guard("operation")
    async def do_thing():
        return "result"
    
    await do_thing()
# Auto-cleanup on exit
```

### Tip 2: Handle Errors Gracefully

```python
from hashed.exceptions import PermissionError

try:
    await guarded_operation()
except PermissionError as e:
    # Operation was blocked by policy
    logger.warning(f"Blocked: {e}")
    # Fallback or escalate to human
```

### Tip 3: Use Auto-Sync in Production

```python
config = HashedConfig(
    enable_auto_sync=True,  # Policies auto-update
    sync_interval=300       # Every 5 minutes
)
```

### Tip 4: Check Policies Before Operations

```python
policy = core.policy_engine.get_policy("operation")
if policy and policy.allowed:
    # Safe to proceed
    await operation()
else:
    # Handle denial upfront
    print("Operation not allowed")
```

---

**Ready to build secure AI agents!** 🎉
