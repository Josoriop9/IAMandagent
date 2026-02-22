-- ============================================================================
-- DIAGNOSTIC & FIX SCRIPT
-- Run this in Supabase SQL Editor to diagnose and fix the dashboard visibility
-- ============================================================================

-- STEP 1: See what users exist in auth
SELECT 
    id as auth_user_id,
    email,
    created_at
FROM auth.users
ORDER BY created_at;

-- STEP 2: See what organizations exist
SELECT 
    id,
    name,
    api_key,
    owner_id,
    is_active,
    created_at
FROM organizations
ORDER BY created_at;

-- STEP 3: Check if owner_id is linked to any user
SELECT 
    o.id as org_id,
    o.name as org_name,
    o.api_key,
    o.owner_id,
    u.email as owner_email
FROM organizations o
LEFT JOIN auth.users u ON u.id = o.owner_id;

-- STEP 4: See if there are logs
SELECT 
    id,
    tool_name,
    status,
    organization_id,
    agent_id,
    timestamp
FROM ledger_logs
ORDER BY timestamp DESC
LIMIT 10;

-- STEP 5: See if there are agents
SELECT
    id,
    name,
    public_key,
    organization_id,
    is_active
FROM agents
ORDER BY created_at DESC;

-- ============================================================================
-- FIX: Link your auth user to the organization
-- ============================================================================
-- Run AFTER seeing the IDs from STEP 1 and STEP 2

-- Replace YOUR_AUTH_USER_ID with the id from STEP 1 (your email's auth user)
-- Replace YOUR_ORG_ID with the id from STEP 2

-- UPDATE organizations 
-- SET owner_id = 'YOUR_AUTH_USER_ID'
-- WHERE id = 'YOUR_ORG_ID';

-- ============================================================================
-- OR: Auto-link the first user to the first org (if only one of each)
-- ============================================================================
-- This links the ONLY user to the ONLY organization
-- ONLY run this if you have exactly 1 user and 1 organization

UPDATE organizations
SET owner_id = (SELECT id FROM auth.users LIMIT 1)
WHERE owner_id IS NULL
   OR owner_id NOT IN (SELECT id FROM auth.users);

-- STEP 6: Verify the fix
SELECT 
    o.id as org_id,
    o.name as org_name,
    o.owner_id,
    u.email as owner_email
FROM organizations o
LEFT JOIN auth.users u ON u.id = o.owner_id;

-- STEP 7: Verify logs can be read (should show count > 0 after running your agent)
SELECT 
    COUNT(*) as total_logs,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
    COUNT(CASE WHEN status = 'denied' THEN 1 END) as denied_count
FROM ledger_logs
WHERE organization_id IN (
    SELECT id FROM organizations WHERE owner_id IN (SELECT id FROM auth.users)
);
