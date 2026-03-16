-- ============================================================================
-- HASHED SDK — SUPABASE DATABASE SCHEMA (Consolidated)
-- AI Agent Governance Control Plane
--
-- This is the single source of truth for the database schema.
-- Run this file in the Supabase SQL Editor to set up a fresh environment.
-- Idempotent: safe to re-run (uses IF NOT EXISTS / OR REPLACE).
--
-- Last updated: 2026-03-05
-- Changes from v1:
--   - Added user_organizations table (auth.users ↔ organizations link)
--   - Added owner_id column to organizations
--   - Disabled RLS on all tables (service_role key handles security at API layer)
--   - Removed broken RLS policies (used current_setting which is not set by backend)
-- ============================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ORGANIZATIONS TABLE (Multi-tenancy)
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    api_key     VARCHAR(255) UNIQUE NOT NULL,
    owner_id    UUID,                           -- links to auth.users.id
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    settings    JSONB DEFAULT '{
        "max_agents": 100,
        "retention_days": 90,
        "allow_external_tools": true
    }'::jsonb,
    is_active   BOOLEAN DEFAULT true,
    CONSTRAINT organizations_name_check CHECK (length(name) >= 2)
);

-- ============================================================================
-- 2. USER_ORGANIZATIONS TABLE (auth.users ↔ organizations many-to-many)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,              -- auth.users.id
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role            VARCHAR(50) NOT NULL DEFAULT 'owner',   -- 'owner', 'admin', 'member'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_user ON user_organizations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_org  ON user_organizations(organization_id);

-- ============================================================================
-- 3. AGENTS TABLE (AI Agents with cryptographic identity)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    public_key      VARCHAR(64) UNIQUE NOT NULL,   -- Ed25519 public key (32 bytes hex = 64 chars)
    agent_type      VARCHAR(50) NOT NULL DEFAULT 'general',
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    metadata        JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT agents_name_check CHECK (length(name) >= 2),
    CONSTRAINT agents_public_key_check CHECK (length(public_key) = 64)
);

-- ============================================================================
-- 4. POLICIES TABLE (Permission rules for agents)
-- ============================================================================
CREATE TABLE IF NOT EXISTS policies (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id          UUID REFERENCES agents(id) ON DELETE CASCADE,   -- NULL = org-wide
    tool_name         VARCHAR(255) NOT NULL,
    max_amount        NUMERIC(20, 2),
    allowed           BOOLEAN DEFAULT true,
    requires_approval BOOLEAN DEFAULT false,
    time_window       VARCHAR(50),
    rate_limit_per    VARCHAR(20),
    rate_limit_count  INTEGER,
    priority          INTEGER DEFAULT 0,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    created_by        VARCHAR(255),
    metadata          JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT policies_tool_name_check CHECK (length(tool_name) >= 1),
    CONSTRAINT policies_rate_limit_check CHECK (
        (rate_limit_per IS NULL AND rate_limit_count IS NULL) OR
        (rate_limit_per IS NOT NULL AND rate_limit_count IS NOT NULL)
    )
);

-- One policy per tool per agent (NULL agent_id = global sentinel UUID)
CREATE UNIQUE INDEX IF NOT EXISTS idx_policies_unique
    ON policies(organization_id, COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::UUID), tool_name);

-- ============================================================================
-- 5. LEDGER_LOGS TABLE (Immutable audit log)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ledger_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES agents(id) ON DELETE SET NULL,
    event_type      VARCHAR(100) NOT NULL,
    tool_name       VARCHAR(255),
    amount          NUMERIC(20, 2),
    signature       TEXT,
    public_key      VARCHAR(64),
    status          VARCHAR(50) NOT NULL,
    error_message   TEXT,
    duration_ms     INTEGER,
    data            JSONB DEFAULT '{}'::jsonb,
    metadata        JSONB DEFAULT '{}'::jsonb,
    timestamp       TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT ledger_logs_status_check CHECK (status IN ('success', 'denied', 'error', 'pending'))
);

-- ============================================================================
-- 6. APPROVAL_QUEUE TABLE (Human-in-the-loop)
-- ============================================================================
CREATE TABLE IF NOT EXISTS approval_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id         UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_name        VARCHAR(255) NOT NULL,
    request_data     JSONB NOT NULL,
    signature        TEXT,
    public_key       VARCHAR(64),
    status           VARCHAR(50) DEFAULT 'pending',
    approved_by      VARCHAR(255),
    reviewed_at      TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    CONSTRAINT approval_queue_status_check CHECK (status IN ('pending', 'approved', 'rejected', 'expired'))
);

-- ============================================================================
-- 7. RATE_LIMIT_TRACKER TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS rate_limit_tracker (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_name       VARCHAR(255) NOT NULL,
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    count           INTEGER DEFAULT 1,
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, agent_id, tool_name, window_start)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_organizations_api_key ON organizations(api_key) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_organizations_active   ON organizations(is_active);
CREATE INDEX IF NOT EXISTS idx_organizations_owner    ON organizations(owner_id);

CREATE INDEX IF NOT EXISTS idx_agents_org         ON agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_agents_public_key  ON agents(public_key);
CREATE INDEX IF NOT EXISTS idx_agents_org_active  ON agents(organization_id, is_active);
CREATE INDEX IF NOT EXISTS idx_agents_type        ON agents(agent_type);

CREATE INDEX IF NOT EXISTS idx_policies_org      ON policies(organization_id);
CREATE INDEX IF NOT EXISTS idx_policies_agent    ON policies(agent_id);
CREATE INDEX IF NOT EXISTS idx_policies_tool     ON policies(tool_name);
CREATE INDEX IF NOT EXISTS idx_policies_org_tool ON policies(organization_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_policies_priority ON policies(priority DESC);

CREATE INDEX IF NOT EXISTS idx_ledger_org            ON ledger_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_ledger_agent          ON ledger_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_ledger_timestamp      ON ledger_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_created_at     ON ledger_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_event_type     ON ledger_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_ledger_tool           ON ledger_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_ledger_status         ON ledger_logs(status);
CREATE INDEX IF NOT EXISTS idx_ledger_org_timestamp  ON ledger_logs(organization_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_agent_timestamp ON ledger_logs(agent_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_approval_org     ON approval_queue(organization_id);
CREATE INDEX IF NOT EXISTS idx_approval_agent   ON approval_queue(agent_id);
CREATE INDEX IF NOT EXISTS idx_approval_status  ON approval_queue(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_approval_expires ON approval_queue(expires_at) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_rate_limit_org_agent ON rate_limit_tracker(organization_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_rate_limit_tool      ON rate_limit_tracker(tool_name);
CREATE INDEX IF NOT EXISTS idx_rate_limit_window    ON rate_limit_tracker(window_start, window_end);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations;
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_policies_updated_at ON policies;
CREATE TRIGGER update_policies_updated_at
    BEFORE UPDATE ON policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION update_agent_last_seen()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.agent_id IS NOT NULL THEN
        UPDATE agents SET last_seen_at = NEW.timestamp WHERE id = NEW.agent_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_agent_last_seen_trigger ON ledger_logs;
CREATE TRIGGER update_agent_last_seen_trigger
    AFTER INSERT ON ledger_logs
    FOR EACH ROW EXECUTE FUNCTION update_agent_last_seen();

-- Trigger: auto-create organization when a new user signs up via Supabase Auth
-- NOTE: Uses gen_random_uuid() — no pgcrypto dependency required.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    new_api_key TEXT;
BEGIN
    -- Generate unique API key (native Postgres 13+ — no extension needed)
    new_api_key := 'hashed_' || replace(
        gen_random_uuid()::text || gen_random_uuid()::text,
        '-',
        ''
    );

    INSERT INTO public.organizations (name, api_key, owner_id)
    VALUES (
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email) || '''s Organization',
        new_api_key,
        NEW.id
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- ROW LEVEL SECURITY — DISABLED
-- The backend uses the service_role key which has full access.
-- Security is enforced at the FastAPI layer via API key validation.
-- Enable RLS only if you expose Supabase directly to clients (not via backend).
-- ============================================================================

ALTER TABLE organizations      DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_organizations DISABLE ROW LEVEL SECURITY;
ALTER TABLE agents             DISABLE ROW LEVEL SECURITY;
ALTER TABLE policies           DISABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_logs        DISABLE ROW LEVEL SECURITY;
ALTER TABLE approval_queue     DISABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limit_tracker DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

CREATE OR REPLACE VIEW agent_activity_summary AS
SELECT
    a.id              AS agent_id,
    a.name            AS agent_name,
    a.agent_type,
    COUNT(l.id)                                           AS total_operations,
    COUNT(CASE WHEN l.status = 'success' THEN 1 END)     AS successful_operations,
    COUNT(CASE WHEN l.status = 'denied'  THEN 1 END)     AS denied_operations,
    COUNT(CASE WHEN l.status = 'error'   THEN 1 END)     AS error_operations,
    MAX(l.timestamp)                                      AS last_activity,
    a.organization_id
FROM agents a
LEFT JOIN ledger_logs l ON a.id = l.agent_id
GROUP BY a.id, a.name, a.agent_type, a.organization_id;

CREATE OR REPLACE VIEW policy_effectiveness AS
SELECT
    p.tool_name,
    p.allowed,
    p.max_amount,
    COUNT(DISTINCT l.id)                                        AS usage_count,
    COUNT(DISTINCT CASE WHEN l.status = 'denied' THEN l.id END) AS denied_count,
    p.organization_id
FROM policies p
LEFT JOIN ledger_logs l
    ON p.tool_name = l.tool_name
   AND p.organization_id = l.organization_id
GROUP BY p.id, p.tool_name, p.allowed, p.max_amount, p.organization_id;

-- ============================================================================
-- TABLE COMMENTS
-- ============================================================================

COMMENT ON TABLE organizations      IS 'Multi-tenant organizations using AI agent governance';
COMMENT ON TABLE user_organizations IS 'Links auth.users to organizations (many-to-many)';
COMMENT ON TABLE agents             IS 'AI agents with Ed25519 cryptographic identities';
COMMENT ON TABLE policies           IS 'Permission policies for agent operations';
COMMENT ON TABLE ledger_logs        IS 'Immutable audit log of all agent operations';
COMMENT ON TABLE approval_queue     IS 'Queue for operations requiring human approval';
COMMENT ON TABLE rate_limit_tracker IS 'Tracks API usage for rate limiting enforcement';

COMMENT ON COLUMN organizations.owner_id    IS 'auth.users.id of the organization creator';
COMMENT ON COLUMN agents.public_key         IS 'Ed25519 public key (64 char hex = 32 bytes)';
COMMENT ON COLUMN policies.agent_id         IS 'NULL = policy applies to all agents in org';
COMMENT ON COLUMN policies.priority         IS 'Higher priority overrides lower when multiple match';
COMMENT ON COLUMN ledger_logs.signature     IS 'Ed25519 signature for non-repudiation';
