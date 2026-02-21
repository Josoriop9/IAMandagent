# 🔒 Hashed Security Guide

## Critical Security Principles

### 1. **Agents Cannot Modify Their Own Policies**

This is the most important security rule. If an AI agent can modify its own governance rules, it can bypass all restrictions.

---

## 🛡️ Defense Layers

### Layer 1: Architecture Separation

```
┌─────────────────────────────────┐
│  POLICY MANAGEMENT              │
│  (Humans Only)                  │
│  - Dashboard UI                 │
│  - Admin API                    │
│  - Direct DB access             │
└─────────────────────────────────┘
              ↓
        (Read Only)
              ↓
┌─────────────────────────────────┐
│  POLICY CONSUMPTION             │
│  (Agents)                       │
│  - @guard decorator             │
│  - Validation only              │
│  - No write access              │
└─────────────────────────────────┘
```

### Layer 2: API Key Types

**Admin API Keys** (for humans):
- Format: `hashed_admin_[64 chars]`
- Can: Create/modify/delete policies
- Can: Manage agents
- Can: View all logs
- Use: Dashboard, admin scripts

**Agent API Keys** (for AI agents):
- Format: `hashed_agent_[64 chars]`
- Can: Register agent
- Can: Read policies (sync)
- Can: Send logs
- **Cannot**: Create/modify policies
- Use: Agent runtime

### Layer 3: Never Expose Policy Management as @guard

```python
# ❌ DANGEROUS - DO NOT DO THIS
@core.guard("manage_policy")  # ← Agent can call this!
async def create_policy(tool_name: str, allowed: bool):
    core.policy_engine.add_policy(...)  # SECURITY HOLE
    
# ✅ SAFE - Policy management not guarded
async def admin_create_policy_internal(tool_name: str, allowed: bool):
    # Only admin scripts can call this
    # Not decorated with @guard
    # Not available to LLM as a tool
    ...
```

### Layer 4: Backend Validation

```python
# Backend validates API key type
@app.post("/v1/policies")
async def create_policy(policy: PolicyCreate, api_key: str):
    if not is_admin_key(api_key):
        raise HTTPException(403, "Only admin keys can modify policies")
    
    # Admin key verified, allow policy creation
    ...
```

### Layer 5: Database RLS

```sql
-- Only organization owners can modify policies
CREATE POLICY policies_owner_only ON policies
    FOR INSERT
    USING (
        auth.uid() = (
            SELECT owner_id FROM organizations 
            WHERE id = organization_id
        )
    );
```

---

## ✅ Security Checklist

Before deploying agents with Hashed:

- [ ] Policy management is **never** decorated with `@guard`
- [ ] Agents use **agent API keys**, not admin keys
- [ ] Backend validates API key type before policy modifications
- [ ] RLS policies prevent unauthorized database writes
- [ ] Audit logging enabled for all policy changes
- [ ] Rate limiting on policy modifications (max 10/hour)
- [ ] Alerts configured for policy changes
- [ ] Critical policies require multi-person approval
- [ ] Regular security audits of policy changes

---

## 🚨 Common Vulnerabilities

### ❌ Vulnerability 1: LLM Can Modify Policies

```python
# WRONG
tools = [
    {"name": "update_policy", "function": update_policy}  # ← LLM can call
]

# The LLM can now:
# 1. Increase its own limits
# 2. Enable disabled operations
# 3. Bypass all governance
```

**Fix**: Never expose policy management as a tool/function to the LLM.

### ❌ Vulnerability 2: Shared API Keys

```python
# WRONG
HASHED_API_KEY = "same_key_for_admin_and_agents"

# If agent compromised, attacker has admin access
```

**Fix**: Use separate admin and agent API keys.

### ❌ Vulnerability 3: No Audit Trail

```python
# WRONG
def update_policy(tool_name, allowed):
    policy_engine.add_policy(tool_name, allowed)
    # No logging of who changed what
```

**Fix**: Always log policy changes with timestamp, user, and old/new values.

### ❌ Vulnerability 4: Direct PolicyEngine Access

```python
# WRONG
@core.guard("do_something")
async def dangerous_function():
    # Function has access to core object
    core.policy_engine.add_policy("bypass", allowed=True)  # ← Can modify!
```

**Fix**: Don't pass `core` or `policy_engine` to guarded functions.

---

## 🔐 Secure Patterns

### Pattern 1: Immutable Policies

```python
class ImmutablePolicyEngine(PolicyEngine):
    def __init__(self, policies: dict):
        super().__init__()
        self._policies = policies
        self._locked = True
    
    def add_policy(self, *args, **kwargs):
        if self._locked:
            raise PolicyLockError("Policies are immutable at runtime")
        super().add_policy(*args, **kwargs)
```

### Pattern 2: Policy Change Approval

```python
class ApprovalWorkflow:
    async def request_policy_change(self, policy: Policy, requested_by: str):
        # Create pending change
        change_id = create_pending_change(policy, requested_by)
        
        # Notify admins for approval
        await notify_admins(change_id)
        
        # Wait for approval
        return change_id
    
    async def approve_change(self, change_id: str, approved_by: str):
        if approved_by == get_change_requester(change_id):
            raise ValueError("Cannot approve own change")
        
        # Apply change
        apply_policy_change(change_id)
```

### Pattern 3: Audit Everything

```python
@audit_log
async def create_policy(policy: Policy, created_by: str):
    # Log: who, what, when
    logger.info(f"Policy created: {policy.tool_name} by {created_by}")
    
    # Store in audit table
    await db.execute("""
        INSERT INTO policy_audit (action, policy, user, timestamp)
        VALUES ('created', $1, $2, NOW())
    """, policy, created_by)
    
    # Create policy
    await db.execute("INSERT INTO policies ...")
```

---

## 📊 Monitoring & Alerts

### Metrics to Track:

1. **Policy Changes**
   - Count per day
   - Who made changes
   - Alert if > 5 changes/day

2. **Failed Policy Modifications**
   - Attempts by agent keys
   - Alert on any attempt

3. **Policy Violations**
   - Operations blocked by policies
   - Frequent violations may indicate attack

4. **Suspicious Patterns**
   - Policy loosened then tightened
   - Multiple policy changes in short time
   - Policy changes during off-hours

---

## 🎯 Recommendations by Environment

### Development
```python
# Local policies OK
core = create_core(policies={
    "test_op": {"allowed": True}
})

# No backend needed
# Quick iteration
```

### Staging
```python
# Backend with test API keys
config = HashedConfig(
    backend_url="https://staging.api.hashed.io",
    api_key=os.getenv("HASHED_STAGING_AGENT_KEY")
)

# Read-only agent key
# Policies managed via dashboard
```

### Production
```python
# Backend with production API keys
config = HashedConfig(
    backend_url="https://api.hashed.io",
    api_key=os.getenv("HASHED_PROD_AGENT_KEY"),
    enable_auto_sync=True,
    sync_interval=300  # 5 minutes
)

# Agent key with read-only policies
# Multi-approval for policy changes
# Full audit logging
# Alerting on all policy changes
```

---

## 🚀 Deployment Checklist

Before going to production:

1. **Key Management**
   - [ ] Admin keys rotated monthly
   - [ ] Agent keys different from admin keys
   - [ ] Keys stored in secrets manager (not in code)
   - [ ] Keys have expiration dates

2. **Access Control**
   - [ ] Only 2-3 people have admin keys
   - [ ] Agent keys can only read policies
   - [ ] Backend enforces key type validation
   - [ ] RLS policies active in database

3. **Monitoring**
   - [ ] Policy change alerts configured
   - [ ] Failed modification attempts logged
   - [ ] Dashboard shows policy change history
   - [ ] Weekly security reviews scheduled

4. **Incident Response**
   - [ ] Plan for compromised agent key
   - [ ] Plan for compromised admin key
   - [ ] Rollback procedure for bad policies
   - [ ] Emergency policy freeze procedure

---

## 📚 Additional Resources

- [OWASP AI Security Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [Hashed Documentation](./README.md)
- [Integration Guide](./INTEGRATION.md)

---

## 🆘 Reporting Security Issues

If you find a security vulnerability:

1. **DO NOT** open a public issue
2. Email: security@hashed.dev
3. Include: Description, impact, reproduction steps
4. We'll respond within 24 hours

---

**Remember**: The best security is defense in depth. No single layer is perfect, but together they create a robust system.

🔒 **Stay Secure!**
