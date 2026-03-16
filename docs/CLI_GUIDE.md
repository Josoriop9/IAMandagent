# Hashed CLI — Complete Reference

> Version: 0.2.1  
> Install: `pip install hashed-sdk`

The `hashed` CLI lets you manage AI agent identities, governance policies, and audit logs without touching the web dashboard.

---

## Installation & Setup

```bash
pip install hashed-sdk

# Verify installation and version
hashed --help
hashed version
```

---

## Authentication

### `hashed version`

Print the installed SDK version.

```bash
hashed version
# hashed-sdk v0.2.1
```

---

### `hashed signup`

Create a new account and organization.

```bash
hashed signup
# Defaults to production backend: https://iamandagent-production.up.railway.app
hashed signup --backend http://localhost:8000  # Use local backend
```

**Interactive prompts:**
- Email
- Password (min 6 chars)
- Organization name

After signup, a confirmation email is sent. The CLI polls for confirmation automatically (up to 6 minutes). On confirmation, your API key is saved to `~/.hashed/credentials.json`.

---

### `hashed login`

Authenticate and save credentials locally.

```bash
hashed login
hashed login --email user@company.com
# Defaults to production backend; override with --backend
hashed login --email user@company.com --backend http://localhost:8000
```

| Flag | Default | Description |
|------|---------|-------------|
| `--email`, `-e` | (prompted) | Email address |
| `--password`, `-p` | (prompted) | Password |
| `--backend`, `-b` | `http://localhost:8000` | Backend URL |

Credentials are saved to `~/.hashed/credentials.json` with `600` permissions.

---

### `hashed logout`

Remove saved credentials.

```bash
hashed logout
```

---

### `hashed whoami`

Show current session info.

```bash
hashed whoami
```

**Output:**
```
╭─────────────────────────────────╮
│  Current Session                │
├──────────────┬──────────────────┤
│ Email        │ you@company.com  │
│ Organization │ Acme Corp        │
│ API Key      │ hashed_abc123... │
│ Backend      │ http://localhost │
╰──────────────┴──────────────────╯
```

---

## Agent Management

### `hashed init`

Initialize a new AI agent — creates identity keypair, `.env` config, and agent script.

```bash
hashed init --name "Research Agent" --type analyst
hashed init --name "Payment Bot" --type finance --framework langchain
hashed init --name "Support Bot" --type assistant --framework crewai --interactive
hashed init --name "Cloud Agent" --type cloud --framework strands
hashed init --name "Multi Agent" --type orchestrator --framework autogen -i --force
```

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | **required** | Agent display name |
| `--type`, `-t` | `general` | Agent type (finance, analyst, assistant, cloud…) |
| `--framework`, `--fw` | `plain` | AI framework: `plain`, `langchain`, `crewai`, `strands`, `autogen` |
| `--interactive`, `-i` | `false` | Add interactive REPL loop (chat mode) |
| `--force`, `-f` | `false` | Overwrite existing files |
| `--config/--no-config` | `true` | Create `.env` config file |

**What it creates:**
```
./secrets/research_agent_key.pem   ← encrypted Ed25519 identity
./research_agent.py                ← agent script with @core.guard() tools
./.env                             ← config (HASHED_BACKEND_URL, HASHED_API_KEY...)
```

**Supported frameworks:**

| Framework | Install |
|-----------|---------|
| `plain` | No extra deps |
| `langchain` | `pip install "hashed-sdk[langchain]"` |
| `crewai` | `pip install "hashed-sdk[crewai]"` |
| `strands` | `pip install "hashed-sdk[strands]"` |
| `autogen` | `pip install "hashed-sdk[autogen]"` |

---

### `hashed agent list`

List all agents registered in the backend.

```bash
hashed agent list
```

**Output:**
```
╭──────────────────────────────────────────────────────╮
│  Registered Agents                                   │
├──────────────────┬──────────┬──────────────┬────────┤
│ Name             │ Type     │ Public Key   │ Status │
├──────────────────┼──────────┼──────────────┼────────┤
│ Research Agent 5 │ analyst  │ a3f1b2c4...  │ 🟢     │
│ Payment Bot      │ finance  │ 9e7d2a1f...  │ 🟢     │
╰──────────────────┴──────────┴──────────────┴────────╯
```

---

### `hashed agent delete`

Permanently delete an agent from the backend and clean up its local policies.

```bash
# By name (case-insensitive)
hashed agent delete "Research Agent 5"

# Skip confirmation prompt
hashed agent delete "Research Agent 5" --yes

# By agent ID (from hashed agent list)
hashed agent delete --id abc123-uuid-here
```

| Flag | Default | Description |
|------|---------|-------------|
| `name` | **required** (unless --id) | Agent name (case-insensitive match) |
| `--id` | none | Agent UUID (alternative to name) |
| `--yes`, `-y` | false | Skip "Are you sure?" confirmation |

**What it does:**
1. Finds agent by name or ID
2. Prompts for confirmation (unless `--yes`)
3. Calls `DELETE /v1/agents/{id}` — removes agent + its backend policies
4. Removes agent's entry from `.hashed_policies.json`
5. Does **NOT** delete the local `.pem` identity file

---

## Policy Management

### `hashed policy add`

Add or update a policy rule (global or per-agent).

```bash
# Global policy (applies to all agents)
hashed policy add search_web --allow
hashed policy add delete_production_db --deny

# Agent-specific policy
hashed policy add process_payment --allow --agent "Payment Bot"
hashed policy add process_payment --allow -m 500 --agent "Payment Bot"

# Deny a specific tool for a specific agent
hashed policy add delete_data --deny --agent "Research Agent 5"
```

| Flag | Default | Description |
|------|---------|-------------|
| `tool_name` | **required** | Tool/operation name |
| `--allow/--deny` | `--allow` | Allow or deny the operation |
| `--max-amount`, `-m` | none | Maximum allowed amount (for financial ops) |
| `--agent` | none | Agent name (omit for global policy) |
| `--config`, `-c` | `.hashed_policies.json` | Policy file path |

---

### `hashed policy list`

List policies from the local `.hashed_policies.json`.

```bash
hashed policy list                        # All policies
hashed policy list -a "Payment Bot"       # Only for one agent
hashed policy list --format json          # JSON output
```

| Flag | Default | Description |
|------|---------|-------------|
| `--agent`, `-a` | none | Filter by agent name |
| `--format`, `-f` | `table` | Output format: `table` or `json` |
| `--config`, `-c` | `.hashed_policies.json` | Policy file path |

---

### `hashed policy remove`

Remove a policy from the local JSON. Run `hashed policy push` afterward to sync to backend.

```bash
# Remove global policy
hashed policy remove search_web

# Remove agent-specific policy
hashed policy remove delete_data -a "Research Agent 5"
```

| Flag | Default | Description |
|------|---------|-------------|
| `tool_name` | **required** | Tool/operation name |
| `--agent`, `-a` | none | Agent name (omit for global) |
| `--config`, `-c` | `.hashed_policies.json` | Policy file path |

---

### `hashed policy test`

Test if an operation would be allowed (dry-run, local only).

```bash
hashed policy test process_payment -a "Payment Bot" -m 200
hashed policy test delete_data -a "Research Agent 5"
hashed policy test search_web
```

| Flag | Default | Description |
|------|---------|-------------|
| `tool_name` | **required** | Tool to test |
| `--agent`, `-a` | none | Test as a specific agent |
| `--amount`, `-m` | none | Amount to test against max_amount |
| `--config`, `-c` | `.hashed_policies.json` | Policy file path |

**Resolution order:** agent-specific → global → default allow

---

### `hashed policy push`

Full sync: local JSON → backend (Supabase). Upserts new/updated policies AND deletes removed ones.

```bash
hashed policy push
hashed policy push --config ./custom_policies.json
```

**Algorithm:**
1. Fetch current backend policies
2. Upsert all local policies (POST)
3. Find backend policies not in local → DELETE them

**Output example:**
```
ℹ Using backend: http://localhost:8000
✓ search_web (global)
✓ process_payment (agent:payment_bot)

ℹ Checking for removed policies...
🗑️  delete_data (agent:research_agent_5) — removed from backend

✓ Policy sync complete: 2 upserted, 1 removed
```

---

### `hashed policy pull`

Download policies from backend → overwrite local JSON.

```bash
hashed policy pull
```

Useful for: syncing a new machine, restoring from backend, or seeing what another team member pushed.

---

## Audit Logs

### `hashed logs list`

View recent audit logs from the backend.

```bash
hashed logs list                    # Last 10 logs
hashed logs list -l 50             # Last 50
hashed logs list --status denied   # Only blocked operations
hashed logs list --status success  # Only successful
hashed logs list --status error    # Only errors
```

| Flag | Default | Description |
|------|---------|-------------|
| `--limit`, `-l` | `10` | Number of logs to show |
| `--status`, `-s` | none | Filter: `success`, `denied`, `error` |

**Output example:**
```
╭─────────────────────────────────────────────────────────────────╮
│  Recent Logs (last 10)                                          │
├─────────────────────┬────────────────────┬──────────┬──────────┤
│ Time                │ Tool               │ Status   │ Agent    │
├─────────────────────┼────────────────────┼──────────┼──────────┤
│ 2026-02-26 22:00:01 │ process_payment    │ ✓ success│ Pay Bot  │
│ 2026-02-26 22:00:03 │ delete_data        │ ✗ denied │ Research │
╰─────────────────────┴────────────────────┴──────────┴──────────╯
```

---

## Key Rotation

### `hashed rotate-key`

Rotate your organization's API key. The old key is **immediately invalidated** and a new one is saved to `~/.hashed/credentials.json`. Rate limited to 3 rotations per hour.

```bash
hashed rotate-key
```

**Output:**
```
🔄 Rotating API key...
✅ API key rotated successfully
   New key: hashed_xyz789... (saved to ~/.hashed/credentials.json)
   ⚠️  Update HASHED_API_KEY in all running agents and cloud environments.
```

> **After rotation:** update `HASHED_API_KEY` in Railway, Vercel, or any environment that uses the old key.

---

## ☠️ Danger Zone

### `hashed account-delete`

> **⚠️ HYPER-DESTRUCTIVE COMMAND — There is NO undo. Data is gone forever.**

Permanently deletes **everything** associated with your account:

| Deleted | Detail |
|---------|--------|
| Organization | The org record itself |
| Agents | ALL agents in the org |
| Policies | ALL policies (global + per-agent) |
| Audit logs | ALL ledger entries |
| Approval queue | ALL pending approvals |
| Auth user | Your Supabase Auth account |

```bash
# Interactive mode — requires typing email to confirm
hashed account-delete

# Skip confirmation prompts (CI/testing ONLY — extremely dangerous)
hashed account-delete --yes
```

| Flag | Default | Description |
|------|---------|-------------|
| `--yes`, `-y` | `false` | Skip confirmation prompts |
| `--backend`, `-b` | (from credentials) | Override backend URL |

**What happens step by step:**

1. Shows a red "DANGER ZONE" warning panel with org name + email
2. Asks you to **type your email exactly** (anti-fat-finger check)
3. Asks a final `yes/no` confirmation
4. Calls `DELETE /v1/auth/account` on the backend
5. Backend deletes org (cascades all data) then deletes Auth user
6. Clears your local `~/.hashed/credentials.json`

**Example output:**

```
╭─────────────────────────── ⚠️  DANGER ZONE ───────────────────────────╮
│  ☠️  HYPER-DESTRUCTIVE OPERATION                                       │
│                                                                        │
│  This will PERMANENTLY delete:                                        │
│    • Organization: Acme Corp                                          │
│    • ALL agents, policies, audit logs                                 │
│    • Account: you@company.com                                         │
│                                                                        │
│  There is NO undo. Data is gone forever.                              │
╰────────────────────────────────────────────────────────────────────────╯

To confirm, type your email address: you@company.com
Email: you@company.com
FINAL WARNING: Delete everything permanently? [y/N]: y

╭──── Deleted ────╮
│  ✓ Account permanently deleted   │
│  Org ID: abc123...               │
│  Auth user deleted: True         │
│  Deleted at: 2026-03-15T23:00:00 │
╰──────────────────╯
```

**When to use this:**
- Cleaning up a test account to start fresh
- Closing an organization that's no longer needed
- CI/CD teardown scripts (use `--yes`)

---

## Identity Management

### `hashed identity create`

Generate a new Ed25519 keypair and save encrypted to file.

```bash
hashed identity create
hashed identity create -o ./secrets/my_agent.pem
hashed identity create -o ./secrets/my_agent.pem -p mypassword
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `./secrets/agent_key.pem` | Output file path |
| `--password`, `-p` | (prompted) | Encryption password |

---

### `hashed identity show`

Display identity info (public key).

```bash
hashed identity show
hashed identity show -f ./secrets/research_agent_key.pem
```

| Flag | Default | Description |
|------|---------|-------------|
| `--file`, `-f` | `./secrets/agent_key.pem` | Identity file path |
| `--password`, `-p` | `$HASHED_IDENTITY_PASSWORD` | Decryption password |

---

### `hashed identity sign`

Sign a message with the identity keypair.

```bash
hashed identity sign "hello world"
hashed identity sign "hello world" -f ./secrets/research_agent_key.pem
```

---

### `hashed identity export`

Export a `.pem` identity as a single-line base64 string for **cloud and serverless deployments** — Railway, AWS Lambda, Google Cloud Run, Kubernetes Secrets, GitHub Actions, etc.

Instead of copying a `.pem` file to your server (insecure), encode it once locally and set it as an environment variable in your cloud provider.

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent NAME` | `-a` | Agent name — looks up `~/.hashed/agents/<name>.pem` |
| `--file PATH` | `-f` | Custom path to the `.pem` file |
| `--password PASS` | `-p` | Decryption password (if key was saved encrypted) |
| `--quiet` | `-q` | Print only the base64 string (no decoration) |

#### Examples

```bash
# Export a named agent (human-readable output + setup guide)
hashed identity export --agent my-prod-agent

# Export to clipboard (macOS)
hashed identity export --agent my-prod-agent --quiet | pbcopy

# Export for use in a shell script or CI pipeline
export HASHED_AGENT_PRIVATE_KEY=$(hashed identity export -a my-prod-agent -q)

# Export from a custom path
hashed identity export --file ./secrets/agent.pem --quiet
```

#### Cloud provider setup

After running the command, set the output as an environment variable:

**Railway:**
```
Dashboard → Your Service → Variables → Add Variable
  Name:  HASHED_AGENT_PRIVATE_KEY
  Value: <paste base64 output>
```

**AWS (Systems Manager Parameter Store — recommended):**
```bash
aws ssm put-parameter \
  --name "/myapp/HASHED_AGENT_PRIVATE_KEY" \
  --value "$(hashed identity export -a my-agent -q)" \
  --type SecureString
```

**GitHub Actions (Repository Secret):**
```
Settings → Secrets and variables → Actions → New repository secret
  Name:  HASHED_AGENT_PRIVATE_KEY
  Value: <paste base64 output>
```

**Kubernetes:**
```bash
kubectl create secret generic hashed-identity \
  --from-literal=HASHED_AGENT_PRIVATE_KEY="$(hashed identity export -a my-agent -q)"
```

#### Agent code (zero changes required)

```python
# Your agent code — no changes needed for cloud deployment
from hashed import HashedCore

# HashedCore auto-detects HASHED_AGENT_PRIVATE_KEY env var
core = HashedCore(agent_name="my-prod-agent")
```

> **If your key was saved with a password**, also set `HASHED_AGENT_PRIVATE_KEY_PASSWORD` in your cloud provider.

---

## Complete Workflow

### First-time setup

```bash
# 1. Create account
hashed signup

# 2. Define policies (before creating agent)
hashed policy add search_web --allow --agent "Research Agent 5"
hashed policy add summarize_text --allow --agent "Research Agent 5"
hashed policy add delete_data --deny --agent "Research Agent 5"

# 3. Create agent (generates script + identity)
hashed init --name "Research Agent 5" --type analyst --framework langchain --interactive

# 4. Run agent — first launch auto-registers + pushes policies
python3 research_agent_5.py

# 5. View audit logs
hashed logs list
```

### Update policies on existing agent

```bash
# Add new policy
hashed policy add send_email --allow --agent "Research Agent 5"

# Remove a policy
hashed policy remove search_web --agent "Research Agent 5"

# Sync to backend (diff-sync: adds new, removes deleted)
hashed policy push
```

### Delete an agent

```bash
hashed agent delete "Research Agent 5" --yes
# ✓ Agent deleted from backend
# ✓ Policies removed from .hashed_policies.json
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HASHED_BACKEND_URL` | Backend URL (default: `https://iamandagent-production.up.railway.app`) |
| `HASHED_API_KEY` | API key for authentication |
| `HASHED_IDENTITY_PASSWORD` | Password for identity file decryption |
| `HASHED_AGENT_PRIVATE_KEY` | Base64-encoded Ed25519 key (cloud/serverless deployments) |
| `HASHED_AGENT_PRIVATE_KEY_PASSWORD` | Password for encrypted cloud key |
| `OPENAI_API_KEY` | Required for LangChain / CrewAI / AutoGen |
| `OPENAI_MODEL` | Default: `gpt-4o-mini` |
| `AWS_REGION` | Required for Strands (Bedrock) |
| `BEDROCK_MODEL_ID` | Default: `us.amazon.nova-pro-v1:0` |

---

## Credentials File

Saved to `~/.hashed/credentials.json` (permissions: `600`):

```json
{
  "email": "you@company.com",
  "org_name": "Acme Corp",
  "api_key": "hashed_abc123...",
  "org_id": "uuid-here",
  "backend_url": "http://localhost:8000",
  "logged_in_at": "2026-02-26T22:00:00"
}
```

---

## Policy File Format

`.hashed_policies.json` structure:

```json
{
  "global": {
    "search_web": {
      "allowed": true,
      "max_amount": null,
      "created_at": "2026-02-26T22:00:00"
    }
  },
  "agents": {
    "research_agent_5": {
      "process_payment": {
        "allowed": true,
        "max_amount": 500.0,
        "created_at": "2026-02-26T22:00:00"
      },
      "delete_data": {
        "allowed": false,
        "max_amount": null,
        "created_at": "2026-02-26T22:00:00"
      }
    }
  }
}
```

**Policy resolution order:**
1. Agent-specific policy (highest priority)
2. Global policy
3. Default: **allow** (if no policy found)
