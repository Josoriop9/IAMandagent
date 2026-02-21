-- ============================================================================
-- HASHED SDK - SUPABASE DATABASE SCHEMA
-- AI Agent Governance Control Plane
-- ============================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ORGANIZATIONS TABLE (Multi-tenancy)
-- ============================================================================
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{
        "max_agents": 100,
        "retention_days": 90,
        "allow_external_tools": true
    }'::jsonb,
    is_active BOOLEAN DEFAULT true,
    CONSTRAINT organizations_name_check CHECK (length(name) >= 2)
);

-- ============================================================================
-- 2. AGENTS TABLE (AI Agents with cryptographic identity)
-- ============================================================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    public_key VARCHAR(64) UNIQUE NOT NULL,  -- Ed25519 public key (32 bytes hex = 64 chars)
    agent_type VARCHAR(50) NOT NULL DEFAULT 'general',  -- 'customer_service', 'data_analysis', 'devops', etc
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT agents_name_check CHECK (length(name) >= 2),
    CONSTRAINT agents_public_key_check CHECK (length(public_key) = 64)
);

-- ============================================================================
-- 3. POLICIES TABLE (Permission rules for agents)
-- ============================================================================
CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,  -- NULL = applies to all agents in org
    tool_name VARCHAR(255) NOT NULL,
    max_amount NUMERIC(20, 2),  -- NULL = unlimited
    allowed BOOLEAN DEFAULT true,
    requires_approval BOOLEAN DEFAULT false,
    time_window VARCHAR(50),  -- 'business_hours', 'weekends', 'always', etc
    rate_limit_per VARCHAR(20),  -- 'second', 'minute', 'hour', 'day', 'month'
    rate_limit_count INTEGER,
    priority INTEGER DEFAULT 0,  -- Higher priority policies override lower ones
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255),  -- User who created the policy
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT policies_tool_name_check CHECK (length(tool_name) >= 1),
    CONSTRAINT policies_rate_limit_check CHECK (
        (rate_limit_per IS NULL AND rate_limit_count IS NULL) OR
        (rate_limit_per IS NOT NULL AND rate_limit_count IS NOT NULL)
    )
);

-- Unique constraint: one policy per tool per agent (or global if agent_id is NULL)
CREATE UNIQUE INDEX idx_policies_unique ON policies(organization_id, COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::UUID), tool_name);

-- ============================================================================
-- 4. LEDGER_LOGS TABLE (Immutable audit log)
-- ============================================================================
CREATE TABLE ledger_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,  -- 'tool_name.success', 'tool_name.denied', 'tool_name.error'
    tool_name VARCHAR(255),
    amount NUMERIC(20, 2),
    signature TEXT,  -- Ed25519 signature (hex)
    public_key VARCHAR(64),  -- Public key used for signing
    status VARCHAR(50) NOT NULL,  -- 'success', 'denied', 'error', 'pending'
    error_message TEXT,
    duration_ms INTEGER,  -- Execution time in milliseconds
    data JSONB DEFAULT '{}'::jsonb,  -- Operation data
    metadata JSONB DEFAULT '{}'::jsonb,  -- Additional metadata (signature, timestamp, etc)
    timestamp TIMESTAMPTZ NOT NULL,  -- When the operation occurred
    created_at TIMESTAMPTZ DEFAULT NOW(),  -- When the log was received
    CONSTRAINT ledger_logs_status_check CHECK (status IN ('success', 'denied', 'error', 'pending'))
);

-- ============================================================================
-- 5. APPROVAL_QUEUE TABLE (Human-in-the-loop approvals)
-- ============================================================================
CREATE TABLE approval_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    request_data JSONB NOT NULL,
    signature TEXT,
    public_key VARCHAR(64),
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'expired'
    approved_by VARCHAR(255),  -- User ID or email who approved/rejected
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    CONSTRAINT approval_queue_status_check CHECK (status IN ('pending', 'approved', 'rejected', 'expired'))
);

-- ============================================================================
-- 6. RATE_LIMIT_TRACKER TABLE (Track usage for rate limiting)
-- ============================================================================
CREATE TABLE rate_limit_tracker (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    count INTEGER DEFAULT 1,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, agent_id, tool_name, window_start)
);

-- ============================================================================
-- INDEXES for Performance
-- ============================================================================

-- Organizations
CREATE INDEX idx_organizations_api_key ON organizations(api_key) WHERE is_active = true;
CREATE INDEX idx_organizations_active ON organizations(is_active);

-- Agents
CREATE INDEX idx_agents_org ON agents(organization_id);
CREATE INDEX idx_agents_public_key ON agents(public_key);
CREATE INDEX idx_agents_org_active ON agents(organization_id, is_active);
CREATE INDEX idx_agents_type ON agents(agent_type);

-- Policies
CREATE INDEX idx_policies_org ON policies(organization_id);
CREATE INDEX idx_policies_agent ON policies(agent_id);
CREATE INDEX idx_policies_tool ON policies(tool_name);
CREATE INDEX idx_policies_org_tool ON policies(organization_id, tool_name);
CREATE INDEX idx_policies_priority ON policies(priority DESC);

-- Ledger Logs (Most queried table)
CREATE INDEX idx_ledger_org ON ledger_logs(organization_id);
CREATE INDEX idx_ledger_agent ON ledger_logs(agent_id);
CREATE INDEX idx_ledger_timestamp ON ledger_logs(timestamp DESC);
CREATE INDEX idx_ledger_created_at ON ledger_logs(created_at DESC);
CREATE INDEX idx_ledger_event_type ON ledger_logs(event_type);
CREATE INDEX idx_ledger_tool ON ledger_logs(tool_name);
CREATE INDEX idx_ledger_status ON ledger_logs(status);
CREATE INDEX idx_ledger_org_timestamp ON ledger_logs(organization_id, timestamp DESC);
CREATE INDEX idx_ledger_agent_timestamp ON ledger_logs(agent_id, timestamp DESC);

-- Approval Queue
CREATE INDEX idx_approval_org ON approval_queue(organization_id);
CREATE INDEX idx_approval_agent ON approval_queue(agent_id);
CREATE INDEX idx_approval_status ON approval_queue(status) WHERE status = 'pending';
CREATE INDEX idx_approval_expires ON approval_queue(expires_at) WHERE status = 'pending';

-- Rate Limit Tracker
CREATE INDEX idx_rate_limit_org_agent ON rate_limit_tracker(organization_id, agent_id);
CREATE INDEX idx_rate_limit_tool ON rate_limit_tracker(tool_name);
CREATE INDEX idx_rate_limit_window ON rate_limit_tracker(window_start, window_end);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_policies_updated_at BEFORE UPDATE ON policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update agent last_seen_at when logs are created
CREATE OR REPLACE FUNCTION update_agent_last_seen()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agents
    SET last_seen_at = NEW.timestamp
    WHERE id = NEW.agent_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_agent_last_seen_trigger AFTER INSERT ON ledger_logs
    FOR EACH ROW EXECUTE FUNCTION update_agent_last_seen();

-- Auto-expire pending approvals
CREATE OR REPLACE FUNCTION expire_pending_approvals()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE approval_queue
    SET status = 'expired'
    WHERE status = 'pending' AND expires_at < NOW();
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Run expiration check hourly (configure with pg_cron or external cron)
-- CREATE TRIGGER expire_approvals_trigger AFTER INSERT ON approval_queue
--     FOR EACH ROW EXECUTE FUNCTION expire_pending_approvals();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limit_tracker ENABLE ROW LEVEL SECURITY;

-- Organizations: users can only see their own org
CREATE POLICY organizations_isolation ON organizations
    FOR ALL
    USING (id = current_setting('app.current_organization_id', true)::UUID);

-- Agents: scoped to organization
CREATE POLICY agents_isolation ON agents
    FOR ALL
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Policies: scoped to organization
CREATE POLICY policies_isolation ON policies
    FOR ALL
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Ledger Logs: scoped to organization (read-only for clients)
CREATE POLICY ledger_logs_isolation ON ledger_logs
    FOR ALL
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Approval Queue: scoped to organization
CREATE POLICY approval_queue_isolation ON approval_queue
    FOR ALL
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Rate Limit Tracker: scoped to organization
CREATE POLICY rate_limit_tracker_isolation ON rate_limit_tracker
    FOR ALL
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- ============================================================================
-- SEED DATA (For testing)
-- ============================================================================

-- Create a test organization
INSERT INTO organizations (name, api_key) VALUES
    ('Test Organization', 'test_api_key_12345678901234567890123456789012');

-- Get the organization ID for reference
DO $$
DECLARE
    test_org_id UUID;
BEGIN
    SELECT id INTO test_org_id FROM organizations WHERE api_key = 'test_api_key_12345678901234567890123456789012';
    
    -- Create a test agent
    INSERT INTO agents (organization_id, name, public_key, agent_type, description) VALUES
        (test_org_id, 'Customer Service Agent', 'a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890', 'customer_service', 'Handles customer inquiries and support');
    
    -- Create test policies
    INSERT INTO policies (organization_id, agent_id, tool_name, max_amount, allowed) VALUES
        (test_org_id, NULL, 'customer_chat', NULL, true),
        (test_org_id, NULL, 'db_read', NULL, true),
        (test_org_id, NULL, 'db_write', NULL, false),
        (test_org_id, NULL, 'make_refund', 100.00, true),
        (test_org_id, NULL, 'external_api', NULL, false);
END $$;

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

-- Agent activity summary
CREATE OR REPLACE VIEW agent_activity_summary AS
SELECT
    a.id as agent_id,
    a.name as agent_name,
    a.agent_type,
    COUNT(l.id) as total_operations,
    COUNT(CASE WHEN l.status = 'success' THEN 1 END) as successful_operations,
    COUNT(CASE WHEN l.status = 'denied' THEN 1 END) as denied_operations,
    COUNT(CASE WHEN l.status = 'error' THEN 1 END) as error_operations,
    MAX(l.timestamp) as last_activity,
    a.organization_id
FROM agents a
LEFT JOIN ledger_logs l ON a.id = l.agent_id
GROUP BY a.id, a.name, a.agent_type, a.organization_id;

-- Policy effectiveness
CREATE OR REPLACE VIEW policy_effectiveness AS
SELECT
    p.tool_name,
    p.allowed,
    p.max_amount,
    COUNT(l.id) as usage_count,
    COUNT(CASE WHEN l.status = 'denied' THEN 1 END) as denied_count,
    p.organization_id
FROM policies p
LEFT JOIN ledger_logs l ON p.tool_name = l.tool_name AND p.organization_id = l.organization_id
GROUP BY p.id, p.tool_name, p.allowed, p.max_amount, p.organization_id;

-- ============================================================================
-- GRANTS (Adjust based on your Supabase role configuration)
-- ============================================================================

-- Grant permissions to authenticated users (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE organizations IS 'Multi-tenant organizations using the AI agent governance system';
COMMENT ON TABLE agents IS 'AI agents with cryptographic identities (Ed25519 public keys)';
COMMENT ON TABLE policies IS 'Permission policies for agent operations';
COMMENT ON TABLE ledger_logs IS 'Immutable audit log of all agent operations';
COMMENT ON TABLE approval_queue IS 'Queue for operations requiring human approval';
COMMENT ON TABLE rate_limit_tracker IS 'Tracks API usage for rate limiting enforcement';

COMMENT ON COLUMN agents.public_key IS 'Ed25519 public key (64 character hex string)';
COMMENT ON COLUMN policies.agent_id IS 'NULL means policy applies to all agents in the organization';
COMMENT ON COLUMN policies.priority IS 'Higher priority policies override lower ones when multiple policies match';
COMMENT ON COLUMN ledger_logs.signature IS 'Ed25519 signature of the operation for non-repudiation';
