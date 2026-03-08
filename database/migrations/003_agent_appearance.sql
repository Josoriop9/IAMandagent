-- ============================================================================
-- Migration 003: Agent appearance columns
-- Applied: 2026-02-20
-- Supabase projects: hashed-dev ✅  |  production ✅
-- ============================================================================
-- Description:
--   Adds icon and color columns to the agents table so each agent can have
--   a visual identity in the dashboard (emoji icon + theme colour).
--
-- Rollback:
--   ALTER TABLE agents DROP COLUMN IF EXISTS icon;
--   ALTER TABLE agents DROP COLUMN IF EXISTS color;
-- ============================================================================

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS icon  VARCHAR(50) DEFAULT 'robot',
  ADD COLUMN IF NOT EXISTS color VARCHAR(50) DEFAULT 'purple';
