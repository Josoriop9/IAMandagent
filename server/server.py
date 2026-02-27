"""
Hashed SDK - Control Plane API Server
FastAPI backend for AI Agent Governance
"""

import os
from datetime import datetime
from typing import List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="Hashed Control Plane API",
    description="AI Agent Governance - Policy & Audit Management",
    version="0.1.0",
)

# CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_key)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PolicyModel(BaseModel):
    tool_name: str
    max_amount: Optional[float] = None
    allowed: bool = True
    requires_approval: bool = False
    time_window: Optional[str] = None
    rate_limit_per: Optional[str] = None
    rate_limit_count: Optional[int] = None
    metadata: dict = Field(default_factory=dict)


class LogEntry(BaseModel):
    event_type: str
    data: dict
    metadata: dict = Field(default_factory=dict)
    timestamp: str


class LogBatchRequest(BaseModel):
    logs: List[LogEntry]
    agent_public_key: str


class AgentRegistration(BaseModel):
    name: str
    public_key: str
    agent_type: str = "general"
    description: Optional[str] = None


class ApprovalDecision(BaseModel):
    approved: bool
    approved_by: str
    rejection_reason: Optional[str] = None


# ============================================================================
# AUTHENTICATION
# ============================================================================

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-KEY")) -> dict:
    """
    Verify API key and return organization info.
    
    Raises:
        HTTPException: If API key is invalid
    """
    try:
        response = supabase.table("organizations").select("*").eq("api_key", x_api_key).eq("is_active", True).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        organization = response.data[0]
        
        # Set organization context for RLS
        # Note: This is simplified - in production, use proper session management
        return organization
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )


def verify_signature(public_key_hex: str, signature_hex: str, message: str) -> bool:
    """
    Verify Ed25519 signature.
    
    Args:
        public_key_hex: Public key in hex format
        signature_hex: Signature in hex format
        message: Original message that was signed
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        public_key_bytes = bytes.fromhex(public_key_hex)
        signature_bytes = bytes.fromhex(signature_hex)
        
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        message_bytes = message.encode('utf-8')
        
        public_key.verify(signature_bytes, message_bytes)
        return True
    except Exception:
        return False


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "hashed-control-plane"
    }


# ============================================================================
# AUTH ENDPOINTS (Signup, Login, Email Confirmation)
# ============================================================================

class AuthSignupRequest(BaseModel):
    email: str
    password: str
    org_name: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


@app.post("/v1/auth/signup", status_code=status.HTTP_201_CREATED)
async def auth_signup(request: AuthSignupRequest):
    """
    Sign up a new user and create their organization.
    
    1. Creates user in Supabase Auth (sends confirmation email)
    2. Stores pending org_name for post-confirmation setup
    """
    try:
        # Create user via Supabase Auth (admin API)
        auth_response = supabase.auth.admin.create_user({
            "email": request.email,
            "password": request.password,
            "email_confirm": False,  # Require email confirmation
            "user_metadata": {"org_name": request.org_name}
        })
        
        user = auth_response.user
        if not user:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        # Send confirmation email via Supabase magic link
        # (Supabase handles email sending automatically with create_user when email_confirm=False)
        # We need to manually trigger the confirmation email
        try:
            supabase.auth.admin.generate_link({
                "type": "signup",
                "email": request.email,
                "password": request.password,
            })
        except Exception:
            pass  # Link generation may fail if email already sent
        
        return {
            "message": "Account created! Check your email for confirmation.",
            "user_id": user.id,
            "email": request.email,
            "org_name": request.org_name,
            "email_confirmed": False
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "already been registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(status_code=409, detail="Email already registered. Try 'hashed login' instead.")
        raise HTTPException(status_code=400, detail=f"Signup failed: {error_msg}")


@app.post("/v1/auth/login")
async def auth_login(request: AuthLoginRequest):
    """
    Login and return org info + API key.
    
    If org doesn't exist yet (first login after email confirmation), creates it.
    """
    try:
        # Sign in via Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        user = auth_response.user
        session = auth_response.session
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not user.email_confirmed_at:
            raise HTTPException(status_code=403, detail="Email not confirmed. Check your inbox.")
        
        # Check if user already has an organization
        user_org = supabase.table("user_organizations")\
            .select("*, organizations(*)")\
            .eq("user_id", str(user.id))\
            .execute()
        
        if user_org.data and len(user_org.data) > 0:
            # Existing user - return their org info
            org = user_org.data[0]["organizations"]
            return {
                "message": "Login successful",
                "email": user.email,
                "org_name": org["name"],
                "api_key": org["api_key"],
                "org_id": org["id"],
                "backend_url": os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8000")
            }
        
        # New user (first login after confirmation) - create organization
        org_name = (user.user_metadata or {}).get("org_name", f"{request.email.split('@')[0]}'s Organization")
        
        # Generate API key with prefix
        import secrets
        api_key = f"hashed_{secrets.token_hex(32)}"
        
        # Create organization (with owner_id for dashboard compatibility)
        org_response = supabase.table("organizations").insert({
            "name": org_name,
            "api_key": api_key,
            "is_active": True,
            "owner_id": str(user.id)
        }).execute()
        
        org = org_response.data[0]
        
        # Link user to organization
        supabase.table("user_organizations").insert({
            "user_id": str(user.id),
            "organization_id": org["id"],
            "role": "owner"
        }).execute()
        
        return {
            "message": "Login successful! Organization created.",
            "email": user.email,
            "org_name": org["name"],
            "api_key": api_key,
            "org_id": org["id"],
            "backend_url": os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8000")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "Invalid login" in error_msg or "invalid" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password")
        raise HTTPException(status_code=400, detail=f"Login failed: {error_msg}")


@app.get("/v1/auth/check-confirmation")
async def check_email_confirmation(email: str):
    """
    Check if a user's email has been confirmed.
    Used by CLI polling during signup flow.
    """
    try:
        # List users and find by email
        users = supabase.auth.admin.list_users()
        
        for user in users:
            if user.email == email:
                confirmed = user.email_confirmed_at is not None
                return {
                    "email": email,
                    "confirmed": confirmed,
                    "confirmed_at": user.email_confirmed_at
                }
        
        raise HTTPException(status_code=404, detail="User not found")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


@app.get("/v1/auth/me")
async def auth_me(org: dict = Depends(verify_api_key)):
    """Get current user/org info from API key."""
    return {
        "org_name": org["name"],
        "org_id": org["id"],
        "api_key_prefix": org["api_key"][:20] + "...",
        "is_active": org["is_active"],
        "created_at": org.get("created_at")
    }


# ============================================================================
# SDK COMPATIBILITY ENDPOINTS (No /v1/ prefix for backward compatibility)
# ============================================================================

@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_agent_sdk(
    agent: AgentRegistration,
    org: dict = Depends(verify_api_key)
):
    """SDK compatibility endpoint for agent registration."""
    return await register_agent(agent, org)


@app.post("/guard")
async def guard_check(
    request: dict,
    org: dict = Depends(verify_api_key)
):
    """
    SDK compatibility endpoint for guard/policy checking.
    
    The SDK calls this before executing operations to check if allowed.
    """
    try:
        operation = request.get("operation")
        agent_id = request.get("agent_id")
        agent_public_key = request.get("agent_public_key")
        data = request.get("data", {})
        
        if not operation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="operation is required"
            )
        
        # Find agent
        if agent_public_key:
            agent_response = supabase.table("agents")\
                .select("*")\
                .eq("public_key", agent_public_key)\
                .eq("organization_id", org["id"])\
                .execute()
        elif agent_id:
            agent_response = supabase.table("agents")\
                .select("*")\
                .eq("id", agent_id)\
                .eq("organization_id", org["id"])\
                .execute()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="agent_id or agent_public_key is required"
            )
        
        if not agent_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        agent = agent_response.data[0]
        
        # Get policies for this operation
        # Check agent-specific policy first
        policy_response = supabase.table("policies")\
            .select("*")\
            .eq("tool_name", operation)\
            .eq("agent_id", agent["id"])\
            .eq("organization_id", org["id"])\
            .execute()
        
        # If no agent-specific policy, check org-wide
        if not policy_response.data:
            policy_response = supabase.table("policies")\
                .select("*")\
                .eq("tool_name", operation)\
                .is_("agent_id", "null")\
                .eq("organization_id", org["id"])\
                .execute()
        
        # Default allow if no policy
        if not policy_response.data:
            return {
                "allowed": True,
                "policy": None,
                "message": "No policy found - default allow"
            }
        
        policy = policy_response.data[0]
        
        # Check if operation is allowed
        if not policy["allowed"]:
            return {
                "allowed": False,
                "policy": policy,
                "message": f"Operation {operation} is not allowed by policy"
            }
        
        # Check if requires approval
        if policy["requires_approval"]:
            # Create approval request
            approval_data = {
                "organization_id": org["id"],
                "agent_id": agent["id"],
                "tool_name": operation,
                "request_data": data,
                "status": "pending"
            }
            
            approval = supabase.table("approval_queue").insert(approval_data).execute()
            
            return {
                "allowed": False,
                "requires_approval": True,
                "approval_id": approval.data[0]["id"],
                "policy": policy,
                "message": "Operation requires approval"
            }
        
        # Policy allows the operation
        return {
            "allowed": True,
            "policy": policy,
            "message": "Operation allowed"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check policy: {str(e)}"
        )


@app.post("/log", status_code=status.HTTP_202_ACCEPTED)
async def log_operation(
    request: dict,
    org: dict = Depends(verify_api_key)
):
    """
    SDK compatibility endpoint for logging operations.
    
    The SDK calls this after executing operations to create audit log.
    """
    try:
        operation = request.get("operation")
        agent_public_key = request.get("agent_public_key")
        agent_id = request.get("agent_id")
        status_value = request.get("status", "success")
        data = request.get("data", {})
        metadata = request.get("metadata", {})
        error = request.get("error")
        
        if not operation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="operation is required"
            )
        
        # Find agent
        if agent_public_key:
            agent_response = supabase.table("agents")\
                .select("id")\
                .eq("public_key", agent_public_key)\
                .eq("organization_id", org["id"])\
                .execute()
            agent_id = agent_response.data[0]["id"] if agent_response.data else None
        
        # Verify signature if present
        signature_valid = False
        if "signature" in metadata and agent_public_key:
            import json
            signature_valid = verify_signature(
                agent_public_key,
                metadata["signature"],
                json.dumps(data, sort_keys=True)
            )
        
        # Create log entry
        log_record = {
            "organization_id": org["id"],
            "agent_id": agent_id,
            "event_type": f"{operation}.{status_value}",
            "tool_name": operation,
            "amount": data.get("amount"),
            "signature": metadata.get("signature"),
            "public_key": agent_public_key,
            "status": status_value,
            "error_message": error,
            "data": data,
            "metadata": {**metadata, "signature_valid": signature_valid},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("ledger_logs").insert(log_record).execute()
        
        return {
            "log_id": response.data[0]["id"],
            "status": "logged",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log operation: {str(e)}"
        )


# ============================================================================
# AGENT MANAGEMENT
# ============================================================================

@app.post("/v1/agents/register", status_code=status.HTTP_201_CREATED)
async def register_agent(
    agent: AgentRegistration,
    org: dict = Depends(verify_api_key)
):
    """
    Register a new AI agent with the organization.
    
    Args:
        agent: Agent registration data
        org: Organization from API key authentication
        
    Returns:
        Registered agent information
    """
    try:
        # Check if agent with this public key already exists
        existing = supabase.table("agents").select("*").eq("public_key", agent.public_key).execute()
        
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with this public key already exists"
            )
        
        # Create new agent
        agent_data = {
            "organization_id": org["id"],
            "name": agent.name,
            "public_key": agent.public_key,
            "agent_type": agent.agent_type,
            "description": agent.description,
            "is_active": True
        }
        
        response = supabase.table("agents").insert(agent_data).execute()
        
        return {
            "agent": response.data[0],
            "message": "Agent registered successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register agent: {str(e)}"
        )


@app.get("/v1/agents")
async def list_agents(org: dict = Depends(verify_api_key)):
    """
    List all agents for the organization.
    
    Returns:
        List of agents
    """
    try:
        response = supabase.table("agents").select("*").eq("organization_id", org["id"]).execute()
        
        return {
            "agents": response.data,
            "count": len(response.data)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )


@app.delete("/v1/agents/{agent_id}", status_code=status.HTTP_200_OK)
async def delete_agent(
    agent_id: str,
    org: dict = Depends(verify_api_key),
):
    """
    Delete (deregister) an agent from the organization.

    This permanently removes the agent record, all its policies,
    and deactivates it. Audit logs are preserved for compliance.

    Args:
        agent_id: UUID of the agent to delete
        org: Organization from API key authentication

    Returns:
        Confirmation message

    Raises:
        404: If agent not found or does not belong to this org
    """
    try:
        # Verify agent belongs to this org before deleting
        existing = (
            supabase.table("agents")
            .select("id, name")
            .eq("id", agent_id)
            .eq("organization_id", org["id"])
            .execute()
        )

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found in this organization",
            )

        agent_name = existing.data[0]["name"]

        # Delete agent-specific policies first (FK constraint)
        supabase.table("policies").delete().eq("agent_id", agent_id).execute()

        # Delete the agent record
        supabase.table("agents").delete().eq("id", agent_id).execute()

        return {
            "message": f"Agent '{agent_name}' deleted successfully",
            "agent_id": agent_id,
            "deleted_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}",
        )


# ============================================================================
# POLICY SYNC
# ============================================================================

@app.get("/v1/policies/sync")
async def sync_policies(
    agent_public_key: str,
    org: dict = Depends(verify_api_key)
):
    """
    Sync policies for a specific agent.
    
    The SDK calls this endpoint to download current policies.
    Returns both agent-specific and organization-wide policies.
    
    Args:
        agent_public_key: Ed25519 public key of the agent
        org: Organization from API key authentication
        
    Returns:
        Agent info and applicable policies
    """
    try:
        # Find agent
        agent_response = supabase.table("agents")\
            .select("*")\
            .eq("public_key", agent_public_key)\
            .eq("organization_id", org["id"])\
            .execute()
        
        if not agent_response.data or len(agent_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        agent = agent_response.data[0]
        
        # Get agent-specific policies
        agent_policies = supabase.table("policies")\
            .select("*")\
            .eq("agent_id", agent["id"])\
            .eq("organization_id", org["id"])\
            .execute()
        
        # Get organization-wide policies (agent_id is NULL)
        org_policies = supabase.table("policies")\
            .select("*")\
            .is_("agent_id", "null")\
            .eq("organization_id", org["id"])\
            .execute()
        
        # Combine and format policies
        all_policies = {}
        
        # Add org-wide policies first (lower priority)
        for policy in org_policies.data:
            all_policies[policy["tool_name"]] = {
                "max_amount": policy["max_amount"],
                "allowed": policy["allowed"],
                "requires_approval": policy["requires_approval"],
                "time_window": policy["time_window"],
                "rate_limit_per": policy["rate_limit_per"],
                "rate_limit_count": policy["rate_limit_count"],
                "metadata": policy["metadata"],
                "priority": policy["priority"]
            }
        
        # Override with agent-specific policies (higher priority)
        for policy in agent_policies.data:
            all_policies[policy["tool_name"]] = {
                "max_amount": policy["max_amount"],
                "allowed": policy["allowed"],
                "requires_approval": policy["requires_approval"],
                "time_window": policy["time_window"],
                "rate_limit_per": policy["rate_limit_per"],
                "rate_limit_count": policy["rate_limit_count"],
                "metadata": policy["metadata"],
                "priority": policy["priority"]
            }
        
        return {
            "agent": {
                "id": agent["id"],
                "name": agent["name"],
                "public_key": agent["public_key"],
                "agent_type": agent["agent_type"]
            },
            "policies": all_policies,
            "sync_interval": 300,  # Seconds until next sync
            "synced_at": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync policies: {str(e)}"
        )


# ============================================================================
# LOG INGESTION
# ============================================================================

@app.post("/v1/logs/batch", status_code=status.HTTP_202_ACCEPTED)
async def receive_logs_batch(
    batch: LogBatchRequest,
    org: dict = Depends(verify_api_key)
):
    """
    Receive batch of logs from SDK.
    
    This is called by the AsyncLedger to send buffered logs.
    
    Args:
        batch: Batch of log entries
        org: Organization from API key authentication
        
    Returns:
        Acknowledgment of receipt
    """
    try:
        # Find agent by public key
        agent_response = supabase.table("agents")\
            .select("id")\
            .eq("public_key", batch.agent_public_key)\
            .eq("organization_id", org["id"])\
            .execute()
        
        agent_id = agent_response.data[0]["id"] if agent_response.data else None
        
        # Prepare log entries for insertion
        log_records = []
        for log in batch.logs:
            # Extract status from event_type (e.g., "transfer.success" -> "success")
            event_parts = log.event_type.split(".")
            status_value = event_parts[-1] if len(event_parts) > 1 else "success"
            tool_name = event_parts[0] if len(event_parts) > 1 else log.event_type
            
            # Verify signature if present
            signature_valid = False
            if "signature" in log.metadata and "public_key" in log.metadata:
                import json
                signature_valid = verify_signature(
                    log.metadata["public_key"],
                    log.metadata["signature"],
                    json.dumps(log.data, sort_keys=True)
                )
            
            log_record = {
                "organization_id": org["id"],
                "agent_id": agent_id,
                "event_type": log.event_type,
                "tool_name": tool_name,
                "amount": log.data.get("amount"),
                "signature": log.metadata.get("signature"),
                "public_key": log.metadata.get("public_key"),
                "status": status_value,
                "error_message": log.data.get("error"),
                "data": log.data,
                "metadata": {**log.metadata, "signature_valid": signature_valid},
                "timestamp": log.timestamp
            }
            log_records.append(log_record)
        
        # Bulk insert logs
        if log_records:
            supabase.table("ledger_logs").insert(log_records).execute()
        
        return {
            "received": len(batch.logs),
            "status": "accepted",
            "processed_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process logs: {str(e)}"
        )


# ============================================================================
# POLICY MANAGEMENT
# ============================================================================

@app.post("/v1/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: PolicyModel,
    agent_id: Optional[str] = None,
    org: dict = Depends(verify_api_key)
):
    """
    Create a new policy.
    
    Args:
        policy: Policy configuration
        agent_id: Optional agent ID (if None, policy applies to all agents)
        org: Organization from API key authentication
        
    Returns:
        Created policy
    """
    try:
        policy_data = {
            "organization_id": org["id"],
            "agent_id": agent_id,
            "tool_name": policy.tool_name,
            "max_amount": policy.max_amount,
            "allowed": policy.allowed,
            "requires_approval": policy.requires_approval,
            "time_window": policy.time_window,
            "rate_limit_per": policy.rate_limit_per,
            "rate_limit_count": policy.rate_limit_count,
            "metadata": policy.metadata
        }
        
        # Check if policy already exists (same tool + agent + org)
        existing_query = supabase.table("policies")\
            .select("id")\
            .eq("organization_id", org["id"])\
            .eq("tool_name", policy.tool_name)
        
        if agent_id:
            existing_query = existing_query.eq("agent_id", agent_id)
        else:
            existing_query = existing_query.is_("agent_id", "null")
        
        existing = existing_query.execute()
        
        if existing.data and len(existing.data) > 0:
            # Update existing policy
            response = supabase.table("policies")\
                .update(policy_data)\
                .eq("id", existing.data[0]["id"])\
                .execute()
            return {
                "policy": response.data[0],
                "message": "Policy updated successfully"
            }
        else:
            # Insert new policy
            response = supabase.table("policies").insert(policy_data).execute()
            return {
                "policy": response.data[0],
                "message": "Policy created successfully"
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create policy: {str(e)}"
        )


@app.get("/v1/policies")
async def list_policies(
    agent_id: Optional[str] = None,
    org: dict = Depends(verify_api_key)
):
    """List all policies for the organization."""
    try:
        query = supabase.table("policies").select("*").eq("organization_id", org["id"])
        
        if agent_id:
            query = query.eq("agent_id", agent_id)
        
        response = query.execute()
        
        return {
            "policies": response.data,
            "count": len(response.data)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list policies: {str(e)}"
        )


@app.delete("/v1/policies/{policy_id}", status_code=status.HTTP_200_OK)
async def delete_policy(
    policy_id: str,
    org: dict = Depends(verify_api_key),
):
    """
    Delete a specific policy by ID.

    Used by 'hashed policy push' to remove policies that were deleted locally.
    Verifies org ownership before deletion.

    Args:
        policy_id: UUID of the policy to delete
        org: Organization from API key authentication

    Returns:
        Confirmation with deleted tool_name

    Raises:
        404: If policy not found or does not belong to this org
    """
    try:
        # Verify policy belongs to this org
        existing = (
            supabase.table("policies")
            .select("id, tool_name, agent_id")
            .eq("id", policy_id)
            .eq("organization_id", org["id"])
            .execute()
        )

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy '{policy_id}' not found in this organization",
            )

        tool_name = existing.data[0]["tool_name"]

        # Delete the policy
        supabase.table("policies").delete().eq("id", policy_id).execute()

        return {
            "message": f"Policy '{tool_name}' deleted successfully",
            "policy_id": policy_id,
            "deleted_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete policy: {str(e)}",
        )


# ============================================================================
# AUDIT & ANALYTICS
# ============================================================================

@app.get("/v1/logs")
async def query_logs(
    agent_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    org: dict = Depends(verify_api_key)
):
    """
    Query audit logs with filters.
    
    Args:
        agent_id: Filter by agent ID
        tool_name: Filter by tool name
        status_filter: Filter by status (success, denied, error)
        limit: Maximum number of results
        offset: Pagination offset
        org: Organization from API key authentication
        
    Returns:
        Filtered log entries
    """
    try:
        query = supabase.table("ledger_logs")\
            .select("*")\
            .eq("organization_id", org["id"])\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .range(offset, offset + limit - 1)
        
        if agent_id:
            query = query.eq("agent_id", agent_id)
        if tool_name:
            query = query.eq("tool_name", tool_name)
        if status_filter:
            query = query.eq("status", status_filter)
        
        response = query.execute()
        
        return {
            "logs": response.data,
            "count": len(response.data),
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query logs: {str(e)}"
        )


@app.get("/v1/analytics/summary")
async def analytics_summary(org: dict = Depends(verify_api_key)):
    """
    Get analytics summary for the organization.
    
    Returns:
        Summary statistics and insights
    """
    try:
        # Use the pre-built view
        agents_summary = supabase.table("agent_activity_summary")\
            .select("*")\
            .eq("organization_id", org["id"])\
            .execute()
        
        policy_effectiveness = supabase.table("policy_effectiveness")\
            .select("*")\
            .eq("organization_id", org["id"])\
            .execute()
        
        return {
            "agents": agents_summary.data,
            "policy_effectiveness": policy_effectiveness.data,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate analytics: {str(e)}"
        )


# ============================================================================
# APPROVAL QUEUE (Human-in-the-loop)
# ============================================================================

@app.get("/v1/approvals/pending")
async def list_pending_approvals(org: dict = Depends(verify_api_key)):
    """List pending approval requests."""
    try:
        response = supabase.table("approval_queue")\
            .select("*")\
            .eq("organization_id", org["id"])\
            .eq("status", "pending")\
            .order("created_at", desc=False)\
            .execute()
        
        return {
            "approvals": response.data,
            "count": len(response.data)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list approvals: {str(e)}"
        )


@app.post("/v1/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    org: dict = Depends(verify_api_key)
):
    """Approve or reject a pending request."""
    try:
        update_data = {
            "status": "approved" if decision.approved else "rejected",
            "approved_by": decision.approved_by,
            "reviewed_at": datetime.utcnow().isoformat(),
            "rejection_reason": decision.rejection_reason
        }
        
        response = supabase.table("approval_queue")\
            .update(update_data)\
            .eq("id", approval_id)\
            .eq("organization_id", org["id"])\
            .eq("status", "pending")\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found or already processed"
            )
        
        return {
            "approval": response.data[0],
            "message": f"Request {'approved' if decision.approved else 'rejected'} successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}"
        )


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
