# Hashed Control Plane API — Reference

> Version: 0.1.0  
> Base URL: `http://localhost:8000` (dev) / `https://api.hashed.dev` (prod)  
> Authentication: `X-API-KEY: hashed_<your_key>` header on all `/v1/*` endpoints

---

## Authentication

All `/v1/*` endpoints require the `X-API-KEY` header:

```bash
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/agents
```

---

## Health

### `GET /health`

Check if the server is running.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-26T22:00:00",
  "service": "hashed-control-plane"
}
```

---

## Auth Endpoints

### `POST /v1/auth/signup`

Create a new user account and organization.

```bash
curl -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "you@company.com", "password": "secret", "org_name": "Acme Corp"}'
```

**Body:**
```json
{
  "email": "you@company.com",
  "password": "secret",
  "org_name": "Acme Corp"
}
```

**Response `201`:**
```json
{
  "message": "Account created! Check your email for confirmation.",
  "user_id": "uuid",
  "email": "you@company.com",
  "org_name": "Acme Corp",
  "email_confirmed": false
}
```

---

### `POST /v1/auth/login`

Authenticate and get API key.

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@company.com", "password": "secret"}'
```

**Response `200`:**
```json
{
  "message": "Login successful",
  "email": "you@company.com",
  "org_name": "Acme Corp",
  "api_key": "hashed_abc123...",
  "org_id": "uuid",
  "backend_url": "http://localhost:8000"
}
```

**Errors:**
- `401` — Invalid credentials
- `403` — Email not confirmed

---

### `GET /v1/auth/check-confirmation`

Check if a user's email has been confirmed (used by CLI during signup polling).

```bash
curl "http://localhost:8000/v1/auth/check-confirmation?email=you@company.com"
```

**Response:**
```json
{
  "email": "you@company.com",
  "confirmed": true,
  "confirmed_at": "2026-02-26T22:00:00"
}
```

---

### `GET /v1/auth/me`

Get current organization info from API key.

```bash
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/auth/me
```

**Response:**
```json
{
  "org_name": "Acme Corp",
  "org_id": "uuid",
  "api_key_prefix": "hashed_abc123...",
  "is_active": true,
  "created_at": "2026-02-26T22:00:00"
}
```

---

## Agent Management

### `POST /v1/agents/register`

Register a new AI agent with the organization.

```bash
curl -X POST http://localhost:8000/v1/agents/register \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Agent 5",
    "public_key": "a3f1b2c4...",
    "agent_type": "analyst",
    "description": "Research and summarization agent"
  }'
```

**Body:**
```json
{
  "name": "Research Agent 5",
  "public_key": "a3f1b2c4...",
  "agent_type": "analyst",
  "description": "Optional description"
}
```

**Response `201`:**
```json
{
  "agent": {
    "id": "uuid",
    "name": "Research Agent 5",
    "public_key": "a3f1b2c4...",
    "agent_type": "analyst",
    "organization_id": "org-uuid",
    "is_active": true,
    "created_at": "2026-02-26T22:00:00"
  },
  "message": "Agent registered successfully"
}
```

**Errors:**
- `409` — Agent with this public key already exists

> **Note:** The SDK calls this automatically on `await core.initialize()`. On first run (201 response), it also auto-pushes local policies.

---

### `GET /v1/agents`

List all agents for the organization.

```bash
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/agents
```

**Response:**
```json
{
  "agents": [
    {
      "id": "uuid",
      "name": "Research Agent 5",
      "public_key": "a3f1b2c4...",
      "agent_type": "analyst",
      "is_active": true,
      "created_at": "2026-02-26T22:00:00"
    }
  ],
  "count": 1
}
```

---

### `DELETE /v1/agents/{agent_id}`

Permanently delete an agent and all its policies. Audit logs are preserved.

```bash
curl -X DELETE \
  -H "X-API-KEY: hashed_abc123..." \
  http://localhost:8000/v1/agents/uuid-here
```

**Response `200`:**
```json
{
  "message": "Agent 'Research Agent 5' deleted successfully",
  "agent_id": "uuid",
  "deleted_at": "2026-02-26T22:00:00"
}
```

**Errors:**
- `404` — Agent not found or not in this organization

> **Note:** Use `hashed agent delete "Research Agent 5"` from the CLI — it also cleans up `.hashed_policies.json`.

---

## Policy Management

### `POST /v1/policies`

Create or update a policy. If a policy for the same `tool_name` + `agent_id` already exists, it is updated.

```bash
# Global policy (no agent_id)
curl -X POST http://localhost:8000/v1/policies \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "search_web", "allowed": true}'

# Agent-specific policy
curl -X POST "http://localhost:8000/v1/policies?agent_id=uuid-here" \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "process_payment", "allowed": true, "max_amount": 500.0}'
```

**Query params:**
| Param | Description |
|-------|-------------|
| `agent_id` | Optional. If omitted, policy is global (applies to all agents). |

**Body:**
```json
{
  "tool_name": "process_payment",
  "allowed": true,
  "max_amount": 500.0,
  "requires_approval": false,
  "time_window": null,
  "rate_limit_per": null,
  "rate_limit_count": null,
  "metadata": {}
}
```

**Response `201`:**
```json
{
  "policy": {
    "id": "policy-uuid",
    "tool_name": "process_payment",
    "allowed": true,
    "max_amount": 500.0,
    "agent_id": "agent-uuid",
    "organization_id": "org-uuid"
  },
  "message": "Policy created successfully"
}
```

---

### `GET /v1/policies`

List all policies for the organization.

```bash
# All policies
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/policies

# Filter by agent
curl -H "X-API-KEY: hashed_abc123..." \
  "http://localhost:8000/v1/policies?agent_id=uuid-here"
```

**Query params:**
| Param | Description |
|-------|-------------|
| `agent_id` | Optional. Filter by agent UUID. |

**Response:**
```json
{
  "policies": [
    {
      "id": "policy-uuid",
      "tool_name": "search_web",
      "allowed": true,
      "max_amount": null,
      "agent_id": null,
      "organization_id": "org-uuid",
      "created_at": "2026-02-26T22:00:00"
    }
  ],
  "count": 1
}
```

---

### `DELETE /v1/policies/{policy_id}`

Delete a specific policy by ID. Used by `hashed policy push` to remove policies that were deleted locally.

```bash
curl -X DELETE \
  -H "X-API-KEY: hashed_abc123..." \
  http://localhost:8000/v1/policies/policy-uuid-here
```

**Response `200`:**
```json
{
  "message": "Policy 'search_web' deleted successfully",
  "policy_id": "policy-uuid",
  "deleted_at": "2026-02-26T22:00:00"
}
```

**Errors:**
- `404` — Policy not found or not in this organization

---

### `GET /v1/policies/sync`

Download all active policies for a specific agent (used by the SDK on startup).

```bash
curl -H "X-API-KEY: hashed_abc123..." \
  "http://localhost:8000/v1/policies/sync?agent_public_key=a3f1b2c4..."
```

**Query params:**
| Param | Description |
|-------|-------------|
| `agent_public_key` | Ed25519 public key hex of the agent |

**Response:**
```json
{
  "agent": {
    "id": "agent-uuid",
    "name": "Research Agent 5",
    "public_key": "a3f1b2c4...",
    "agent_type": "analyst"
  },
  "policies": {
    "search_web": {
      "allowed": true,
      "max_amount": null,
      "requires_approval": false
    },
    "process_payment": {
      "allowed": true,
      "max_amount": 500.0,
      "requires_approval": false
    }
  },
  "sync_interval": 300,
  "synced_at": "2026-02-26T22:00:00"
}
```

**Policy resolution:** agent-specific policies override global ones.

---

## Guard (SDK Compatibility)

### `POST /guard`

Check if an operation is allowed before executing. Called by the SDK's `@core.guard()` decorator.

```bash
curl -X POST http://localhost:8000/guard \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "process_payment",
    "agent_public_key": "a3f1b2c4...",
    "data": {"amount": 200.0}
  }'
```

**Body:**
```json
{
  "operation": "process_payment",
  "agent_public_key": "a3f1b2c4...",
  "data": {"amount": 200.0}
}
```

**Response — Allowed:**
```json
{
  "allowed": true,
  "policy": { "tool_name": "process_payment", "max_amount": 500.0 },
  "message": "Operation allowed"
}
```

**Response — Denied:**
```json
{
  "allowed": false,
  "policy": { "tool_name": "delete_data", "allowed": false },
  "message": "Operation delete_data is not allowed by policy"
}
```

**Response — Requires Approval:**
```json
{
  "allowed": false,
  "requires_approval": true,
  "approval_id": "approval-uuid",
  "message": "Operation requires approval"
}
```

---

## Audit Logging

### `POST /log`

Log a completed operation to the audit trail. Called by the SDK after each guarded operation.

```bash
curl -X POST http://localhost:8000/log \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "process_payment",
    "agent_public_key": "a3f1b2c4...",
    "status": "success",
    "data": {"amount": 200.0, "result": "payment completed"},
    "metadata": {"signature": "sig_hex..."}
  }'
```

**Response `202`:**
```json
{
  "log_id": "log-uuid",
  "status": "logged",
  "timestamp": "2026-02-26T22:00:00"
}
```

---

### `GET /v1/logs`

Query audit logs with filters.

```bash
# Recent logs
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/logs

# Filter by agent and status
curl -H "X-API-KEY: hashed_abc123..." \
  "http://localhost:8000/v1/logs?agent_id=uuid&status_filter=denied&limit=50"
```

**Query params:**
| Param | Default | Description |
|-------|---------|-------------|
| `agent_id` | none | Filter by agent UUID |
| `tool_name` | none | Filter by tool name |
| `status_filter` | none | `success`, `denied`, `error` |
| `limit` | `100` | Max records to return |
| `offset` | `0` | Pagination offset |

**Response:**
```json
{
  "logs": [
    {
      "id": "log-uuid",
      "tool_name": "process_payment",
      "status": "success",
      "amount": 200.0,
      "agent_id": "agent-uuid",
      "signature": "sig_hex...",
      "timestamp": "2026-02-26T22:00:00"
    }
  ],
  "count": 1,
  "limit": 100,
  "offset": 0
}
```

---

### `POST /v1/logs/batch`

Batch log ingestion (used by the SDK's `AsyncLedger`).

```bash
curl -X POST http://localhost:8000/v1/logs/batch \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_public_key": "a3f1b2c4...",
    "logs": [
      {
        "event_type": "process_payment.success",
        "data": {"amount": 200.0},
        "metadata": {"signature": "sig_hex..."},
        "timestamp": "2026-02-26T22:00:00"
      }
    ]
  }'
```

**Response `202`:**
```json
{
  "received": 1,
  "status": "accepted",
  "processed_at": "2026-02-26T22:00:00"
}
```

---

## Approval Queue (Human-in-the-Loop)

### `GET /v1/approvals/pending`

List pending approval requests.

```bash
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/approvals/pending
```

**Response:**
```json
{
  "approvals": [
    {
      "id": "approval-uuid",
      "tool_name": "delete_production_db",
      "agent_id": "agent-uuid",
      "request_data": {},
      "status": "pending",
      "created_at": "2026-02-26T22:00:00"
    }
  ],
  "count": 1
}
```

---

### `POST /v1/approvals/{approval_id}/decide`

Approve or reject a pending request.

```bash
# Approve
curl -X POST http://localhost:8000/v1/approvals/approval-uuid/decide \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "approved_by": "admin@company.com"}'

# Reject
curl -X POST http://localhost:8000/v1/approvals/approval-uuid/decide \
  -H "X-API-KEY: hashed_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "approved_by": "admin@company.com", "rejection_reason": "Too risky"}'
```

**Response:**
```json
{
  "approval": {
    "id": "approval-uuid",
    "status": "approved",
    "approved_by": "admin@company.com",
    "reviewed_at": "2026-02-26T22:00:00"
  },
  "message": "Request approved successfully"
}
```

---

## Analytics

### `GET /v1/analytics/summary`

Get activity summary across all agents.

```bash
curl -H "X-API-KEY: hashed_abc123..." http://localhost:8000/v1/analytics/summary
```

**Response:**
```json
{
  "agents": [
    {
      "agent_name": "Research Agent 5",
      "total_operations": 142,
      "denied_operations": 3,
      "last_active": "2026-02-26T22:00:00"
    }
  ],
  "policy_effectiveness": [
    {
      "tool_name": "delete_data",
      "total_attempts": 5,
      "denied_count": 5,
      "denial_rate": 1.0
    }
  ],
  "generated_at": "2026-02-26T22:00:00"
}
```

---

## SDK Compatibility Endpoints

These endpoints have no `/v1/` prefix for backward compatibility with older SDK versions:

| Endpoint | Equivalent |
|----------|------------|
| `POST /register` | `POST /v1/agents/register` |
| `POST /guard` | Policy check (see above) |
| `POST /log` | Operation log (see above) |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request / validation error |
| `401` | Invalid or missing API key |
| `403` | Email not confirmed |
| `404` | Resource not found |
| `409` | Conflict (duplicate resource) |
| `500` | Internal server error |

---

## Endpoint Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | ❌ | Health check |
| POST | `/v1/auth/signup` | ❌ | Create account |
| POST | `/v1/auth/login` | ❌ | Login + get API key |
| GET | `/v1/auth/check-confirmation` | ❌ | Check email confirmation |
| GET | `/v1/auth/me` | ✅ | Current org info |
| POST | `/v1/agents/register` | ✅ | Register agent |
| GET | `/v1/agents` | ✅ | List agents |
| DELETE | `/v1/agents/{id}` | ✅ | Delete agent |
| POST | `/v1/policies` | ✅ | Create/update policy |
| GET | `/v1/policies` | ✅ | List policies |
| DELETE | `/v1/policies/{id}` | ✅ | Delete policy |
| GET | `/v1/policies/sync` | ✅ | Sync policies to agent |
| POST | `/guard` | ✅ | Check operation allowed |
| POST | `/log` | ✅ | Log an operation |
| GET | `/v1/logs` | ✅ | Query audit logs |
| POST | `/v1/logs/batch` | ✅ | Batch log ingestion |
| GET | `/v1/approvals/pending` | ✅ | List pending approvals |
| POST | `/v1/approvals/{id}/decide` | ✅ | Approve/reject |
| GET | `/v1/analytics/summary` | ✅ | Activity summary |
