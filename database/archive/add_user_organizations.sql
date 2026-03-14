-- ============================================================================
-- Migration: Create user_organizations table + fix RLS policies
-- Run this in the Supabase SQL Editor
-- ============================================================================

-- 1. Create user_organizations table (links auth.users to organizations)
CREATE TABLE IF NOT EXISTS user_organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'owner',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_user ON user_organizations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_org ON user_organizations(organization_id);

-- 2. Fix RLS policies for CLI auth flow
-- Organizations
DROP POLICY IF EXISTS organizations_isolation ON organizations;
DROP POLICY IF EXISTS organizations_service_role ON organizations;
DROP POLICY IF EXISTS organizations_read ON organizations;

ALTER TABLE organizations DISABLE ROW LEVEL SECURITY;

-- User organizations
ALTER TABLE user_organizations DISABLE ROW LEVEL SECURITY;
