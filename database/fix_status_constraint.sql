-- ============================================================================
-- FIX: Update ledger_logs status constraint to include permission_denied
-- ============================================================================

-- Drop the old constraint
ALTER TABLE ledger_logs DROP CONSTRAINT IF EXISTS ledger_logs_status_check;

-- Add new constraint with additional status values
ALTER TABLE ledger_logs ADD CONSTRAINT ledger_logs_status_check 
    CHECK (status IN ('success', 'denied', 'error', 'pending', 'permission_denied'));

-- Update any existing rows (optional - in case you already have data)
UPDATE ledger_logs SET status = 'denied' WHERE status = 'permission_denied';

-- ============================================================================
-- SUCCESS!
-- Now the ledger_logs table accepts 'permission_denied' as a valid status
-- ============================================================================
