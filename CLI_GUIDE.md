# Hashed CLI Guide

**Professional Command-Line Interface for AI Agent Governance**

The Hashed CLI provides a complete set of tools for managing AI agents, identities, policies, and audit logs without requiring access to the paid web dashboard.

---

## 🚀 Installation

```bash
# Install the SDK with CLI
pip install -e git+https://github.com/YOUR-REPO/hashed-sdk.git#egg=hashed-sdk

# Or from local directory
cd hashed-sdk
pip install -e .
```

After installation, the `hashed` command will be available globally.

---

## 📚 Quick Start

### Initialize a New Agent Project

```bash
# Create a new agent with interactive prompts
hashed init --name "My Agent" --type "customer_service"

# This creates:
# - ./secrets/agent_key.pem (encrypted identity)
# - .env (configuration file)
# - agent.py (example script)
# - ./secrets/.gitignore
```

**What it does:**
- ✅ Generates cryptographic identity (Ed25519)
- ✅ Creates encrypted key file
- ✅ Sets up project structure
- ✅ Creates example agent code

---

## 🔑 Identity Management

### Create a New Identity

```bash
# Interactive (prompts for password)
hashed identity create

# With custom path
hashed identity create --output ./my-keys/agent.pem

# Non-interactive (from env var)
export HASHED_IDENTITY_PASSWORD="strong_password"
hashed identity create
```

### Show Identity Information

```bash
# Display public key and details
hashed identity show

# From custom file
hashed identity show --file ./my-keys/agent.pem
```

**Output:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Identity Information                     │
├─────────────┬───────────────────────────────────────────────┤
│ File        │ ./secrets/agent_key.pem                       │
│ Public Key  │ a1b2c3d4e5f6...                               │
│ Algorithm   │ Ed25519                                        │
└─────────────┴───────────────────────────────────────────────┘
```

### Sign a Message

```bash
# Sign data with your identity
hashed identity sign "important message"
```

---

## 🛡️ Policy Management

Policies define what operations agents can perform. The CLI stores policies locally in `.hashed_policies.json`.

### Add a Policy

```bash
# Allow operation with no limits
hashed policy add send_email --allow

# Allow with max amount limit
hashed policy add transfer_money --allow --max-amount 1000.0

# Deny operation completely
hashed policy add delete_database --deny
```

### List All Policies

```bash
# Table format (default)
hashed policy list

# JSON format
hashed policy list --format json
```

**Output:**
```
┌─────────────────┬─────────┬────────────┬────────────┐
│ Tool            │ Allowed │ Max Amount │ Created    │
├─────────────────┼─────────┼────────────┼────────────┤
│ send_email      │ ✓ Yes   │ -          │ 2026-02-24 │
│ transfer_money  │ ✓ Yes   │ 1000.0     │ 2026-02-24 │
│ delete_database │ ✗ No    │ -          │ 2026-02-24 │
└─────────────────┴─────────┴────────────┴────────────┘
```

### Test a Policy

Test if an operation would be allowed without actually executing it:

```bash
# Test basic operation
hashed policy test send_email

# Test with amount
hashed policy test transfer_money --amount 500.0
# ✓ ALLOWED - Amount 500.0 is within limit 1000.0

hashed policy test transfer_money --amount 1500.0
# ✗ DENIED - Amount 1500.0 exceeds max 1000.0
```

### Remove a Policy

```bash
hashed policy remove send_email
```

---

## 🤖 Agent Management

**Note:** Agent commands require a running backend server.

### List Registered Agents

```bash
# Show all agents in your organization
hashed agent list
```

**Output:**
```
┌────────────────────────┬──────────────┬──────────────────┬──────────┐
│ Name                   │ Type         │ Public Key       │ Status   │
├────────────────────────┼──────────────┼──────────────────┼──────────┤
│ Customer Support Bot   │ service      │ a1b2c3d4e5f6...  │ 🟢 Active│
│ Data Analysis Agent    │ analysis     │ f6e5d4c3b2a1...  │ 🟢 Active│
│ Security Monitor       │ security     │ 1a2b3c4d5e6f...  │ 🔴 Inactive│
└────────────────────────┴──────────────┴──────────────────┴──────────┘
```

---

## 📝 Audit Logs

**Note:** Log commands require a running backend server.

### View Recent Logs

```bash
# Show last 10 logs
hashed logs list

# Show last 50 logs
hashed logs list --limit 50

# Filter by status
hashed logs list --status success
hashed logs list --status denied
hashed logs list --status error
```

**Output:**
```
┌──────────────────────┬──────────────┬────────────┬────────────────────┐
│ Time                 │ Tool         │ Status     │ Agent              │
├──────────────────────┼──────────────┼────────────┼────────────────────┤
│ 2026-02-24 22:15:30  │ send_email   │ ✓ success  │ Customer Support   │
│ 2026-02-24 22:14:12  │ refund       │ ✓ success  │ Customer Support   │
│ 2026-02-24 22:13:45  │ delete_user  │ ✗ denied   │ Security Monitor   │
│ 2026-02-24 22:12:03  │ query_db     │ ⚠ error    │ Data Agent         │
└──────────────────────┴──────────────┴────────────┴────────────────────┘
```

---

## ⚙️ Configuration

The CLI reads configuration from environment variables or `.env` file:

```bash
# .env file
HASHED_BACKEND_URL=http://localhost:8000
HASHED_API_KEY=your_api_key_here
HASHED_IDENTITY_PASSWORD=your_strong_password
```

### Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HASHED_BACKEND_URL` | Backend API URL | `http://localhost:8000` |
| `HASHED_API_KEY` | API key for authentication | None |
| `HASHED_IDENTITY_PASSWORD` | Password for identity encryption | None (prompts) |

---

## 🎯 Common Workflows

### 1. Start a New Agent Project

```bash
# Initialize project
hashed init --name "My Bot" --type "chatbot"

# View your identity
hashed identity show

# Add policies
hashed policy add send_message --allow --max-amount 100.0
hashed policy add access_database --allow

# Test policies
hashed policy test send_message --amount 50
# ✓ ALLOWED

# Run your agent
python agent.py
```

### 2. Develop Without Backend (Offline Mode)

```bash
# Create identity
hashed identity create

# Manage policies locally
hashed policy add operation1 --allow
hashed policy add operation2 --deny
hashed policy list

# Test policies
hashed policy test operation1  # ✓ ALLOWED
hashed policy test operation2  # ✗ DENIED

# Your agent will work with local policies only
# (no backend required)
```

### 3. Monitor Production Agent

```bash
# List all agents
hashed agent list

# View recent activity
hashed logs list --limit 100

# Filter for errors
hashed logs list --status error

# Filter for denied operations
hashed logs list --status denied
```

### 4. Policy Development & Testing

```bash
# Add test policies
hashed policy add test_op --allow --max-amount 100.0

# Test various scenarios
hashed policy test test_op --amount 50   # Within limit
hashed policy test test_op --amount 150  # Exceeds limit

# Adjust policy
hashed policy remove test_op
hashed policy add test_op --allow --max-amount 200.0

# Test again
hashed policy test test_op --amount 150  # Now allowed
```

---

## 🔒 Security Best Practices

### Identity Files

```bash
# ✅ DO: Store in ./secrets/ (gitignored)
hashed identity create --output ./secrets/agent.pem

# ✅ DO: Use strong passwords
export HASHED_IDENTITY_PASSWORD="$(openssl rand -base64 32)"

# ❌ DON'T: Hardcode passwords
hashed identity create --password "weak123"  # BAD

# ❌ DON'T: Commit .pem files to git
# (./secrets/.gitignore prevents this)
```

### Password Management

```bash
# ✅ DO: Use environment variables
export HASHED_IDENTITY_PASSWORD="strong_password_from_vault"

# ✅ DO: Use secrets manager in production
# AWS Secrets Manager, HashiCorp Vault, etc.

# ❌ DON'T: Store in plain text files
```

---

## 📦 CLI Command Reference

### Global Commands

```bash
hashed version              # Show version
hashed --help               # Show help
```

### Identity Commands

```bash
hashed identity create      # Create new identity
hashed identity show        # Show identity info
hashed identity sign MSG    # Sign a message
```

### Policy Commands

```bash
hashed policy add TOOL      # Add policy
hashed policy list          # List all policies
hashed policy remove TOOL   # Remove policy
hashed policy test TOOL     # Test if allowed
```

### Agent Commands

```bash
hashed agent list           # List agents (requires backend)
```

### Log Commands

```bash
hashed logs list            # View audit logs (requires backend)
```

---

## 🐛 Troubleshooting

### Command Not Found

```bash
# Reinstall the package
pip install -e .

# Verify installation
which hashed
pip show hashed-sdk
```

### Backend Connection Errors

```bash
# Check if backend is running
curl http://localhost:8000/health

# Verify configuration
echo $HASHED_BACKEND_URL
echo $HASHED_API_KEY

# Test with curl
curl -H "X-API-KEY: $HASHED_API_KEY" \
     $HASHED_BACKEND_URL/v1/agents
```

### Identity Password Issues

```bash
# If you forgot password, you need to create new identity
# (old identity cannot be recovered)
mv ./secrets/agent_key.pem ./secrets/agent_key.pem.old
hashed identity create

# Or use password from environment
export HASHED_IDENTITY_PASSWORD="your_password"
hashed identity show
```

---

## 💡 Tips & Tricks

### Bash Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias hi='hashed identity'
alias hp='hashed policy'
alias ha='hashed agent'
alias hl='hashed logs'

# Now you can use:
hi show
hp list
ha list
hl list
```

### Output to JSON

```bash
# Parse with jq
hashed policy list --format json | jq '.send_email'

# Export policies
hashed policy list --format json > policies_backup.json
```

### Watch Logs in Real-time

```bash
# Poor man's live tail (refresh every 2 seconds)
watch -n 2 "hashed logs list --limit 10"
```

---

## 🔄 Migrating from Dashboard to CLI

If you're currently using the web dashboard, here's how to transition:

| Dashboard Feature | CLI Equivalent |
|-------------------|----------------|
| View Agents | `hashed agent list` |
| View Policies | `hashed policy list` |
| Add Policy | `hashed policy add TOOL --allow` |
| View Logs | `hashed logs list` |
| Filter Logs | `hashed logs list --status denied` |
| Agent Setup | `hashed init --name "Agent"` |

---

## 📖 Examples

See `/examples` directory for complete agent examples:

- `examples/persistent_agent.py` - Agent with persistent identity
- `examples/basic_usage.py` - Simple getting started
- `examples/async_usage.py` - Async patterns

Run examples:

```bash
cd examples
python persistent_agent.py
```

---

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/yourrepo/hashed-sdk/issues)
- **Docs**: [Full Documentation](https://docs.hashed.example.com)
- **CLI Help**: `hashed --help` or `hashed COMMAND --help`

---

## 🎉 That's It!

You now have a fully functional CLI for managing AI agents without needing the paid dashboard. Happy coding! 🚀

```bash
# Start building!
hashed init --name "My Awesome Agent"
```
