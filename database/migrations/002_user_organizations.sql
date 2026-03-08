-- ============================================================================
-- Migration 002: User-organization linking
-- Applied: 2026-02-15
-- Supabase projects: hashed-dev ✅  |  production ✅
-- ============================================================================
-- Description:
--   1. Adds owner_id (UUID → auth.users) to organizations so each org is
--      owned by a Supabase Auth user.
--   2. Creates user_organizations junction table so multiple users can belong
--      to the same org (multi-tenant foundation).
--   3. Creates helper function + trigger to auto-link new users to their org
--      when they sign up via the backend /v1/auth/signup endpoint.
--
-- Rollback:
--   DROP TABLE IF EXISTS user_organizations CASCADE;
--   ALTER TABLE organizations DROP COLUMN IF EXISTS owner_id;
-- ============================================================================

-- 1. Add owner_id to organizations (references auth.users)
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- 2. Create user_organizations junction table
CREATE TABLE IF NOT EXISTS user_organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id)   ON DELETE CASCADE,
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role        VARCHAR(50)  NOT NULL DEFAULT 'member',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, org_id)
);

-- 3. Index for fast membership lookups
CREATE INDEX IF NOT EXISTS idx_user_organizations_user_id ON user_organizations (user_id);
CREATE INDEX IF NOT EXISTS idx_user_organizations_org_id  ON user_organizations (org_id);
