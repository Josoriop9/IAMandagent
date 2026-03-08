-- ============================================================================
-- CLEAN SLATE: Delete all data but keep the org and user
-- Run this in Supabase SQL Editor to start fresh
-- ============================================================================

-- Step 1: Delete all logs
DELETE FROM ledger_logs;

-- Step 2: Delete all policies  
DELETE FROM policies;

-- Step 3: Delete all approval queue items
DELETE FROM approval_queue;

-- Step 4: Delete all agents
DELETE FROM agents;

-- Step 5: Verify clean state
SELECT 'agents' as table_name, count(*) as rows FROM agents
UNION ALL
SELECT 'policies', count(*) FROM policies
UNION ALL
SELECT 'ledger_logs', count(*) FROM ledger_logs
UNION ALL
SELECT 'organizations', count(*) FROM organizations;

-- ============================================================================
-- FIX: Make ledger_logs.agent_id SET NULL on agent delete
-- (so deleting agents doesn't delete logs)
-- ============================================================================

-- Drop the existing foreign key and recreate with ON DELETE SET NULL
ALTER TABLE ledger_logs 
  DROP CONSTRAINT IF EXISTS ledger_logs_agent_id_fkey;

ALTER TABLE ledger_logs 
  ADD CONSTRAINT ledger_logs_agent_id_fkey 
  FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL;

-- Same for policies - SET NULL so global policies survive agent deletion
ALTER TABLE policies 
  DROP CONSTRAINT IF EXISTS policies_agent_id_fkey;

ALTER TABLE policies 
  ADD CONSTRAINT policies_agent_id_fkey 
  FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL;

-- Verify constraints
SELECT
  tc.constraint_name,
  tc.table_name,
  kcu.column_name,
  rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('ledger_logs', 'policies')
  AND kcu.column_name = 'agent_id';
