-- ============================================================================
-- Fix RLS Policies for Dashboard Access
-- The dashboard uses Supabase Auth, so we need to update RLS policies
-- ============================================================================

-- Drop old policies that use app.current_organization_id
DROP POLICY IF EXISTS organizations_isolation ON organizations;
DROP POLICY IF EXISTS organizations_user_access ON organizations;
DROP POLICY IF EXISTS agents_isolation ON agents;
DROP POLICY IF EXISTS policies_isolation ON policies;
DROP POLICY IF EXISTS ledger_logs_isolation ON ledger_logs;
DROP POLICY IF EXISTS approval_queue_isolation ON approval_queue;
DROP POLICY IF EXISTS rate_limit_tracker_isolation ON rate_limit_tracker;

-- ============================================================================
-- NEW POLICIES: Use auth.uid() to link with owner_id
-- ============================================================================

-- Organizations: users can see their own organization
CREATE POLICY organizations_user_access ON organizations
    FOR ALL
    TO authenticated
    USING (owner_id = auth.uid());

-- Allow service role to bypass RLS (for backend API)
CREATE POLICY organizations_service_role ON organizations
    FOR ALL
    TO service_role
    USING (true);

-- Agents: users can see agents in their organization
CREATE POLICY agents_user_access ON agents
    FOR ALL
    TO authenticated
    USING (
        organization_id IN (
            SELECT id FROM organizations WHERE owner_id = auth.uid()
        )
    );

CREATE POLICY agents_service_role ON agents
    FOR ALL
    TO service_role
    USING (true);

-- Policies: users can see policies in their organization
CREATE POLICY policies_user_access ON policies
    FOR ALL
    TO authenticated
    USING (
        organization_id IN (
            SELECT id FROM organizations WHERE owner_id = auth.uid()
        )
    );

CREATE POLICY policies_service_role ON policies
    FOR ALL
    TO service_role
    USING (true);

-- Ledger Logs: users can see logs in their organization
CREATE POLICY ledger_logs_user_access ON ledger_logs
    FOR ALL
    TO authenticated
    USING (
        organization_id IN (
            SELECT id FROM organizations WHERE owner_id = auth.uid()
        )
    );

CREATE POLICY ledger_logs_service_role ON ledger_logs
    FOR ALL
    TO service_role
    USING (true);

-- Approval Queue: users can see approvals in their organization
CREATE POLICY approval_queue_user_access ON approval_queue
    FOR ALL
    TO authenticated
    USING (
        organization_id IN (
            SELECT id FROM organizations WHERE owner_id = auth.uid()
        )
    );

CREATE POLICY approval_queue_service_role ON approval_queue
    FOR ALL
    TO service_role
    USING (true);

-- Rate Limit Tracker: users can see rate limits in their organization
CREATE POLICY rate_limit_tracker_user_access ON rate_limit_tracker
    FOR ALL
    TO authenticated
    USING (
        organization_id IN (
            SELECT id FROM organizations WHERE owner_id = auth.uid()
        )
    );

CREATE POLICY rate_limit_tracker_service_role ON rate_limit_tracker
    FOR ALL
    TO service_role
    USING (true);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Check that policies are correctly applied
SELECT 
    schemaname,
    tablename,
    policyname,
    roles,
    cmd,
    qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
