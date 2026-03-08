-- ============================================================================
-- Debug Script: Check User-Organization Linkage
-- ============================================================================

-- 1. Check all users
SELECT 
    'USERS' as table_name,
    email,
    id as user_id,
    created_at
FROM auth.users
ORDER BY created_at DESC;

-- 2. Check all organizations
SELECT 
    'ORGANIZATIONS' as table_name,
    name,
    id as org_id,
    owner_id,
    api_key,
    created_at
FROM organizations
ORDER BY created_at DESC;

-- 3. Check user-organization linkage
SELECT 
    'USER-ORG LINKAGE' as info,
    u.email as user_email,
    o.name as organization_name,
    o.id as org_id,
    o.api_key,
    o.owner_id,
    CASE 
        WHEN o.owner_id IS NULL THEN '❌ NO OWNER'
        WHEN o.owner_id = u.id THEN '✅ LINKED'
        ELSE '⚠️ DIFFERENT OWNER'
    END as status
FROM auth.users u
LEFT JOIN organizations o ON o.owner_id = u.id
ORDER BY u.created_at DESC;

-- 4. Check agents (all)
SELECT 
    'AGENTS' as table_name,
    name,
    agent_type,
    id,
    organization_id,
    public_key,
    is_active,
    created_at
FROM agents
ORDER BY created_at DESC
LIMIT 10;

-- 5. Check agents linked to your organizations
SELECT 
    'YOUR AGENTS' as info,
    u.email as owner_email,
    o.name as org_name,
    a.name as agent_name,
    a.agent_type,
    a.id as agent_id,
    a.is_active,
    a.created_at
FROM agents a
JOIN organizations o ON a.organization_id = o.id
LEFT JOIN auth.users u ON o.owner_id = u.id
ORDER BY a.created_at DESC
LIMIT 10;

-- 6. Check policies
SELECT 
    'POLICIES' as table_name,
    tool_name,
    organization_id,
    allowed,
    max_amount,
    created_at
FROM policies
ORDER BY created_at DESC
LIMIT 10;

-- 7. Check logs
SELECT 
    'LOGS' as table_name,
    tool_name,
    status,
    organization_id,
    created_at
FROM ledger_logs
ORDER BY created_at DESC
LIMIT 10;

-- 8. Count by organization
SELECT 
    'COUNTS BY ORG' as info,
    o.name as org_name,
    o.api_key,
    u.email as owner_email,
    (SELECT COUNT(*) FROM agents WHERE organization_id = o.id) as agent_count,
    (SELECT COUNT(*) FROM policies WHERE organization_id = o.id) as policy_count,
    (SELECT COUNT(*) FROM ledger_logs WHERE organization_id = o.id) as log_count
FROM organizations o
LEFT JOIN auth.users u ON o.owner_id = u.id
ORDER BY o.created_at DESC;
