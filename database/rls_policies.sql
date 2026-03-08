-- ============================================================================
-- RLS (Row Level Security) Migration — C-01 Remediation
-- Standard: OWASP ASVS 4.0 L2
--
-- Enables RLS on all tables that hold organisation data.
-- Authenticated users (Supabase JWT / anon key) can only access data that
-- belongs to their organisation.  The backend service_role key BYPASSES RLS
-- by design — no backend changes are required.
--
-- ⚠️  Run in DEV first (hashed-dev project), verify backend still works,
--     then run in PROD.
--
-- Run order:
--   1. Enable RLS on each table
--   2. Create SELECT / INSERT / UPDATE / DELETE policies per table
-- ============================================================================

-- ── Step 1: Enable RLS ───────────────────────────────────────────────────────
-- Each table that stores org-scoped data gets RLS enabled.
-- rate_limit_tracker is infrastructure-only (no org data) — excluded.

ALTER TABLE organizations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents             ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies           ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_logs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_queue     ENABLE ROW LEVEL SECURITY;

-- ── Step 2: user_organizations ──────────────────────────────────────────────
-- Users can only see their own membership record.
-- This is the anchor for all other org-scoped policies below.

CREATE POLICY "user_orgs_own_select"
    ON user_organizations
    FOR SELECT
    USING (user_id = auth.uid());

-- ── Step 3: organizations ────────────────────────────────────────────────────
-- Users can read orgs they belong to.
-- Only the org owner can update org metadata (name, etc.).
-- INSERT/DELETE are service_role only (backend manages org lifecycle).

CREATE POLICY "orgs_member_select"
    ON organizations
    FOR SELECT
    USING (
        id IN (
            SELECT organization_id
            FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "orgs_owner_update"
    ON organizations
    FOR UPDATE
    USING (owner_id = auth.uid());

-- ── Step 4: agents ───────────────────────────────────────────────────────────
-- Org members have full CRUD on agents within their org.

CREATE POLICY "agents_member_select"
    ON agents FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "agents_member_insert"
    ON agents FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "agents_member_update"
    ON agents FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "agents_member_delete"
    ON agents FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

-- ── Step 5: policies ─────────────────────────────────────────────────────────
-- Org members have full CRUD on policies within their org.
-- Policy modification by agent keys (not JWT users) is blocked at the API
-- layer in server.py (verify_api_key → org check), not here.

CREATE POLICY "policies_member_select"
    ON policies FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "policies_member_insert"
    ON policies FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "policies_member_update"
    ON policies FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "policies_member_delete"
    ON policies FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

-- ── Step 6: ledger_logs ──────────────────────────────────────────────────────
-- Read-only for org members via JWT.
-- INSERT comes from the backend (service_role) — no user INSERT policy needed.
-- This prevents agents or users from injecting fake log entries directly.

CREATE POLICY "ledger_logs_member_select"
    ON ledger_logs FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

-- ── Step 7: approval_queue ───────────────────────────────────────────────────
-- Org members can view and update (approve/reject) pending requests.
-- INSERT is backend-only (service_role), handled in /guard endpoint.

CREATE POLICY "approval_member_select"
    ON approval_queue FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "approval_member_update"
    ON approval_queue FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM user_organizations
            WHERE user_id = auth.uid()
        )
    );

-- ── Verification ─────────────────────────────────────────────────────────────
-- After applying, run these queries to verify:
--
--   SELECT tablename, rowsecurity FROM pg_tables
--   WHERE schemaname = 'public'
--   ORDER BY tablename;
--   -- All critical tables should show rowsecurity = true
--
--   SELECT schemaname, tablename, policyname, cmd, qual
--   FROM pg_policies
--   WHERE schemaname = 'public'
--   ORDER BY tablename, policyname;
--   -- All policies above should appear
-- ============================================================================
