# Database Migrations

All schema changes must be added as numbered SQL files in this directory and
run **in order** in the Supabase SQL Editor (dev first, then prod).

## Convention

```
NNN_short_description.sql
```

- `NNN` = zero-padded integer (001, 002, ...).
- Every statement must be **idempotent** (`IF NOT EXISTS`, `IF EXISTS`, `OR REPLACE`).
- Never edit a migration that has already been applied to production.
- Add a new numbered file for every change.

## Applied migrations (as of 2026-03-08)

| File | Description | Status |
|------|-------------|--------|
| `001_initial_schema.sql` | Base tables: organizations, agents, policies, ledger_logs, approval_queue, rate_limit_tracker | ✅ Applied dev + prod |
| `002_user_organizations.sql` | `user_organizations` junction table + `owner_id` on organizations | ✅ Applied dev + prod |
| `003_agent_appearance.sql` | `icon` + `color` columns on agents | ✅ Applied dev + prod |
| `004_fix_status_constraint.sql` | Allow `permission_denied` in ledger_logs.status CHECK | ✅ Applied dev + prod |
| `005_rls_policies.sql` | Enable RLS + 13 row-level security policies (C-01 security fix) | ✅ Applied dev + prod |

## How to run a new migration

1. Copy the template:
   ```bash
   cp database/migrations/000_template.sql database/migrations/006_my_change.sql
   ```
2. Write the SQL (idempotent statements only).
3. Test in **hashed-dev** Supabase project first.
4. Verify the backend still works (`hashed agent list`, `hashed logs list`).
5. Apply to **production** Supabase project.
6. Commit the file and update the table above.

## What NOT to do

- ❌ Do not edit schema.sql for ad-hoc changes — add a new migration file.
- ❌ Do not run migrations directly against production without testing in dev.
- ❌ Do not delete migration files (archive them in `database/archive/` instead).
