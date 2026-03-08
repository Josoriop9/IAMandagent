# database/archive

Contains SQL scripts that were run **ad-hoc** during development to fix issues
or investigate problems. These scripts are **already applied** to both
`hashed-dev` and production Supabase projects.

They are kept here for historical reference — do NOT run them again.

| File | What it did | Applied |
|------|------------|---------|
| `clean_slate.sql` | Drops and recreates all tables (nuclear reset) | dev only |
| `debug_and_fix.sql` | Investigated schema inconsistencies + applied fixes | dev only |
| `debug_check.sql` | Read-only diagnostic queries | dev only |
| `fix_cli_org_owner.sql` | Linked existing orgs to Supabase Auth users (backfill) | dev + prod |
| `fix_rls_for_dashboard.sql` | Interim RLS fix before the canonical migration 005 | dev + prod |

> ⚠️ **Do not run these.** For new schema changes, add a numbered file to
> `database/migrations/` instead.
