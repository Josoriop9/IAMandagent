-- ============================================================================
-- Fix: Set owner_id on organizations created by CLI (missing owner_id)
-- Run this in Supabase SQL Editor
-- ============================================================================

-- 1. Show current state
SELECT o.id, o.name, o.owner_id, o.api_key,
       uo.user_id, uo.role
FROM organizations o
LEFT JOIN user_organizations uo ON uo.organization_id = o.id
ORDER BY o.created_at DESC;

-- 2. Fix: Set owner_id from user_organizations for orgs missing it
UPDATE organizations o
SET owner_id = uo.user_id
FROM user_organizations uo
WHERE uo.organization_id = o.id
  AND uo.role = 'owner'
  AND o.owner_id IS NULL;

-- 3. Re-enable RLS on organizations with proper policy
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Drop all existing policies
DROP POLICY IF EXISTS organizations_isolation ON organizations;
DROP POLICY IF EXISTS organizations_service_role ON organizations;
DROP POLICY IF EXISTS organizations_read ON organizations;
DROP POLICY IF EXISTS organizations_user_access ON organizations;
DROP POLICY IF EXISTS organizations_allow_all ON organizations;

-- Service role can do everything (backend uses this)
CREATE POLICY organizations_service_role ON organizations
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- Authenticated users can see their own org (dashboard uses this)
CREATE POLICY organizations_user_access ON organizations
    FOR ALL TO authenticated
    USING (owner_id = auth.uid());

-- 4. Verify
SELECT o.id, o.name, o.owner_id FROM organizations o;
