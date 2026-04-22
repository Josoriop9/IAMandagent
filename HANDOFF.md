# Hashed — Handoff Document

> Generated: 2026-04-22 | Version: 0.3.4 | Branch: `main` | Last prompt: PROMPT 1 (canonical identity)

---

## Current State

- ✅ **Core SDK is production-ready and published to PyPI** as `hashed-sdk==0.3.4` — `hashed` CLI works end-to-end (login, init, agent list, logs, whoami, account-delete)
- ✅ **FastAPI backend** deployed on Railway; `SUPABASE_KEY` (service_role) is correctly set — all `/v1/*` endpoints return 200
- ✅ **428 tests passing, 74% coverage, 1 skipped** — CI passes on every push via GitHub Actions
- ✅ **AsyncLedger** is crash-safe (SQLite WAL + Fernet AES-128 encryption with PBKDF2 key derivation from API key)
- ✅ **Circuit breaker** (3 failures → open, 60s cooldown) guards all backend HTTP calls in `HashedCore`
- ✅ **`identity.py` now has `sign_operation()`** — SPEC §2.1-compliant canonical payload with `nonce`, `timestamp_ns`, `version`, `agent_id`; `sign_data()` marked deprecated
- ⚠️ **Ledger has no hash chain** — log entries are not linked; a forged/deleted entry mid-sequence is undetectable without the WAL
- ⚠️ **`sign_operation()` not yet wired into `core.py`** — `_execute_remote_guard` and `_log_to_all_transports` still use the old ad-hoc payload (PROMPT 3 pending)
- ⚠️ **`identity_store.py` coverage at 79%** — lines 244-284 (keyring fallback paths) not exercised in CI
- ⚠️ **Duplicate org bug in Supabase** is dormant (backend working now) but root cause not fixed — `auth_login` in `server.py` can still create a second org if `user_organizations` link is lost
- 🔴 **Dashboard `.single()` calls** on `organizations` will 406 if the duplicate org bug re-triggers (affects `agents/page.tsx`, `logs/page.tsx`, `policies/page.tsx`, `page.tsx`)
- ⏳ **MCP Server** and **`hashed ai`** CLI features — designed but not yet implemented

---

## Architecture Decisions Made This Session

| Decision | Rationale |
|---|---|
| **WAL encryption via PBKDF2 + Fernet** | API key already has 128-bit entropy; avoids storing a separate secret. AES-128-CBC + HMAC-SHA256. OWASP ASVS 4.0 L2 C-08 compliance |
| **Circuit breaker in `HashedCore` (not middleware)** | Keeps governance logic colocated with the caller; avoids coupling to ASGI stack |
| **SRP decomposition in `guard()`** | `_validate_local_policy`, `_execute_remote_guard`, `_log_to_all_transports`, `_log_denial`, `_log_error` — each has one reason to change |
| **Fail-open default** | `HASHED_FAIL_CLOSED=false` by default so SDK doesn't block AI agents when backend is unreachable; opt-in to strict mode |
| **`hashed init` auto-populates `.env`** | UX win — no manual copy-paste of API key after `hashed login` |
| **Exponential backoff in `_background_sync`** | Avoids hammering a down backend (10s → 20s → … → 300s cap) |
| **MCP Server plan** → `src/hashed/mcp_server.py` + `hashed mcp` CLI command + `mcp` optional dep | Exposes hashed tools to Claude/Cursor/Windsurf without modifying user code |
| **`hashed ai` plan** → subprocess tool-use, Anthropic Claude, `pip install hashed-sdk[ai]` | Natural language → hashed CLI commands |

---

## Files Modified This Session

### Previous session (Sprint 7 / v0.3.4)

| File | What changed |
|---|---|
| `docs/CLI_GUIDE.md` | Documented `hashed whoami --show-key` and `hashed init` auto-API-key behavior; bumped header to v0.3.4 |
| `src/hashed/cli.py` | Added `--show-key` flag to `whoami`; `init` command now writes `HASHED_API_KEY` to `.env` automatically |
| `src/hashed/core.py` | Sprint 7: SRP decomposition of `guard()`, circuit breaker, perf tracking, exponential backoff in `_background_sync` |
| `src/hashed/ledger.py` | WAL encryption (Fernet/PBKDF2), graceful migration of pre-encryption WAL rows, `wal_path=False` to disable durability |
| `server/server.py` | Fixed hardcoded `localhost:8000` → production URL; `SUPABASE_KEY` env var resolution |
| `.github/workflows/deploy.yml` | `--skip-existing` on PyPI upload; bumped coverage floor to 70% |
| `database/migrations/006_fix_handle_new_user_trigger.sql` | Replaced `gen_random_bytes` with `gen_random_uuid()` in the trigger |

### PROMPT 1 — Canonical identity payload (this session)

| File | What changed |
|---|---|
| `src/hashed/identity.py` | Added `sign_operation()` with SPEC §2.1 canonical payload (`version`, `agent_id`, `operation`, `amount`, `timestamp_ns`, `nonce`, `status`, `context`). Added `verify_signed_operation()` static method. Marked `sign_data()` as `DeprecationWarning`. Replaced `datetime.utcnow()` → `datetime.now(timezone.utc)`. Added `import os`, `import warnings`, `from time import time_ns` at module level. |
| `tests/test_identity.py` | Added `TestSignOperation` class with 6 tests: `test_sign_operation_has_required_fields`, `test_nonce_is_unique`, `test_canonical_is_deterministic`, `test_verify_signed_operation_valid`, `test_verify_signed_operation_tampered`, `test_replay_protection_via_nonce`. Total tests in file: 38. |

---

## Known Issues / TODOs

### 🔴 High Priority
- **`server.py` `auth_login` duplicate org prevention** — Before creating a new org, must check `organizations WHERE owner_id = user.id`. If found, reconstruct the `user_organizations` link instead of inserting a new org. Without this fix the bug can resurface on Railway instability.
- **Dashboard `.single()` → `.maybeSingle()`** — All 4 dashboard pages (`agents`, `logs`, `policies`, main `page.tsx`) use `.single()` on the `organizations` query. If 2 orgs exist, returns 406 and the dashboard shows empty state.

### 🟡 Medium Priority
- ~~**Canonical payload in `identity.py`**~~ — ✅ **DONE (PROMPT 1)**: `sign_operation()` added with full SPEC §2.1 envelope. `sign_data()` deprecated.
- **Hash chain in `AsyncLedger`** — Each WAL entry should include `prev_hash = SHA-256(previous_entry_json)`. Without it, a deleted entry mid-sequence is undetectable. **(PROMPT 2 — next)**
- **Wire `sign_operation()` into `core.py`** — `_execute_remote_guard` and `_log_to_all_transports` still build payloads ad-hoc. Must call `identity.sign_operation()` and embed the canonical envelope + signature. **(PROMPT 3)**

### 🟢 Lower Priority / Tech Debt
- `identity_store.py` lines 244-284 (keyring fallback) — not covered by tests (79% coverage)
- `ledger.py` lines 253-254, 271-273 (queue-full on WAL recovery) — edge case not tested
- `crypto/hasher.py` lines 145-148, 183-184 — untested error paths
- Repo rename from `IAMandagent` → TBD (~40 files with hardcoded `IAMandagent` references, including Railway URL which is a separate concern)
- `mypy` has `disallow_untyped_defs = true` but several modules use `Any` liberally — run `mypy src/` for full picture before next release
- **MCP Server** not implemented yet (`src/hashed/mcp_server.py` + `hashed mcp` command + `mcp` dep in `pyproject.toml`)
- **`hashed ai`** CLI not implemented yet (Anthropic Claude tool-use, `hashed-sdk[ai]` extras group)

---

## Last Commits

```
67feb6 (HEAD -> main) feat(identity): canonical payload with nonce, timestamp_ns, version per SPEC 2
46fa4a9 (origin/main) docs: update CLI_GUIDE for v0.3.4 new features
01ed285 fix: remove spurious f-prefix on plain string (ruff F541)
d0a345d (tag: v0.3.4) chore: bump version 0.3.3 → 0.3.4
78a1446 feat: hashed init auto-populates API key + whoami --show-key
317dd8b fix: skip email confirmation polling when HASHED_SKIP_EMAIL_CONFIRMATION=true
a991294 ci: fix deploy.yml skip-existing PyPI + bump coverage floor to 70%
eaf27e1 (tag: v0.3.3) fix: agent list & logs list now load .env via _get_sync_credentials() (v0.3.3)
fe895a0 chore: bump version 0.3.1 → 0.3.2 (adds hashed account-delete)
b9a026f feat(cli): add hashed account-delete — hyper-destructive account wipe
1bd91f3 fix(cli): replace hardcoded localhost:8000 with production URL
0107bfd fix(db): replace gen_random_bytes with gen_random_uuid() in handle_new_user trigger
034eb83 docs: add employer disclaimer + CONTRIBUTING.md
89ca4d7 (tag: v0.3.1) docs(release): v0.3.1 — SPEC.md, README God Mode, updated badges
588cead (tag: v0.3.0) chore(release): bump version 0.2.1 → 0.3.0
a4b5c79 merge(Sprint 7): circuit breaker, SRP refactor, perf tracking, backoff — 422 tests, core.py 91%
673360c (origin/feature/core-refactor, feature/core-refactor) fix(lint): move logging import to module level (ruff I001 CI fix)
e59fa52 fix(lint): sort imports in test_circuit_breaker.py (ruff I001)
bc165cc refactor(core): Sprint 7 principal-engineer quality refactor
72821e4 security: remove real API key + local paths from docs
```

---

## Test State

```
428 passed, 1 skipped, 54 warnings in 4.01s   ← +6 tests from TestSignOperation

Coverage summary (key modules):
  src/hashed/core.py              91%
  src/hashed/guard.py            100%
  src/hashed/exceptions.py       100%
  src/hashed/identity.py          96%   ← 2 uncovered lines in sign_operation exception path (minor)
  src/hashed/models.py            97%
  src/hashed/ledger.py            90%
  src/hashed/identity_store.py    79%   ← gap: keyring fallback paths
  src/hashed/crypto/hasher.py     83%   ← gap: error paths
  src/hashed/utils/http_client.py 95%
  TOTAL                           74%
```

---

## Planned Next Steps

Execute in this order — each is a self-contained prompt:

**1. ~~Canonical payload in `identity.py`~~** ✅ **DONE — commit `67feb6`**
> `sign_operation()` added with full SPEC §2.1 envelope (`version`, `agent_id`, `operation`, `amount`, `timestamp_ns`, `nonce`, `status`, `context`). `verify_signed_operation()` static method added. `sign_data()` deprecated. 38/38 tests green.

**2. Hash chain in `AsyncLedger`** ← **NEXT**
> In `ledger.py`, add `prev_hash` field to each WAL entry: `SHA-256(json.dumps(previous_entry, sort_keys=True))`. Genesis entry uses `prev_hash = "0" * 64`. Add `verify_chain()` method that walks WAL and validates the chain. Add tests in `test_ledger.py`.

**3. Wire new identity + ledger into `core.py`**
> Update `_execute_remote_guard` to pass the canonical signed envelope (with nonce + timestamp_ns) to the backend `/guard` endpoint. Update `_log_to_all_transports` to include `prev_hash` in metadata. Ensure `test_core.py` covers the new fields.

**4. LangChain integration (real `HashedCallbackHandler`)**
> In `src/hashed/integrations/langchain.py`, implement `HashedCallbackHandler(BaseCallbackHandler)` that calls `core.guard(tool_name)` on `on_tool_start` and logs result on `on_tool_end`. Add `examples/langchain_example.py`. Update `docs/FRAMEWORK_GUIDES.md`.

**5. CrewAI integration (`wrap_tool` + `HashedBaseTool`)**
> In `src/hashed/integrations/crewai.py`, implement `wrap_tool(crewai_tool, core)` decorator and `HashedBaseTool(BaseTool)` mixin. Add `examples/crewai_example.py`. Update `docs/FRAMEWORK_GUIDES.md`.

**6. Cleanup final**
> Run `mypy src/ --strict`, `ruff check src/ --fix`, add missing docstrings, bump version to 0.4.0, update CHANGELOG.md, tag release, publish to PyPI.
