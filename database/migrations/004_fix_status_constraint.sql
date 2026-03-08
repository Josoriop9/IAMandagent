-- ============================================================================
-- Migration 004: Extend ledger_logs.status CHECK constraint
-- Applied: 2026-02-25
-- Supabase projects: hashed-dev ✅  |  production ✅
-- ============================================================================
-- Description:
--   The original CHECK constraint on ledger_logs.status only allowed
--   ('success', 'denied', 'error').  The guard() decorator emits
--   'permission_denied' for policy violations, which caused INSERT failures.
--   This migration drops the old constraint and adds an updated one.
--
-- Rollback:
--   ALTER TABLE ledger_logs DROP CONSTRAINT IF EXISTS ledger_logs_status_check;
--   ALTER TABLE ledger_logs ADD CONSTRAINT ledger_logs_status_check
--     CHECK (status IN ('success', 'denied', 'error'));
-- ============================================================================

ALTER TABLE ledger_logs
  DROP CONSTRAINT IF EXISTS ledger_logs_status_check;

ALTER TABLE ledger_logs
  ADD CONSTRAINT ledger_logs_status_check
  CHECK (status IN ('success', 'denied', 'error', 'permission_denied'));
