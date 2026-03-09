# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Rate limiting on all API endpoints
- API key expiration + rotation endpoint
- Integration tests for CLI commands
- Ledger durability (persist buffer to disk)

---

## [0.2.0] — 2026-03-08

### 🧪 Quality Sprint — Test Coverage 17% → 62%

Full coverage sprint across 4 sessions, growing the suite from ~30 tests to **312 tests** and raising total coverage from 17% to 62%.

### Added

#### Tests (`tests/`)

**`tests/test_core_backend.py`** *(expanded — 33 new tests)*
- `HashedCore.initialize()` with real HTTP mock: registers agent (201 new / 409 existing), syncs policies, starts background task
- `_register_agent()` — all status paths: 201 (new agent), 409 (existing), 500 (error)
- `sync_policies_from_backend()` — success with policies, no-http-client fallback, 500 error
- `_push_local_json_policies()` — flat format, structured global/agents format, no file found, malformed JSON
- `@guard()` with backend: fail-open (unreachable backend allows), fail-closed (unreachable denies), success logged to `/log`, denial logged to `/log`
- `shutdown()` — stops sync task and HTTP client cleanly

**`tests/test_core_coverage.py`** *(new — 14 tests)*
- `push_policies_to_backend()` — success (2 POST per policy), agent-not-found skip, no HTTP client noop, no local policies noop, 500 raises, 409 counts as success
- `_push_local_json_policies()` agent section — snake_case matching pushes with `agent_id`, agent not found skips scoped policies
- `_background_sync()` — runs ≥1 iteration with mocked sleep, error in iteration caught + task continues
- `shutdown()` with `_ledger` set → `ledger.stop()` awaited
- `@guard()` on sync `def` — runs via `sync_wrapper`, denial returns string

**`tests/test_http_client.py`** *(expanded — ~40 new tests)*
- `HashedHTTPClient` retry logic: 429 rate-limit back-off, 503 retry, max retries exceeded
- Auth header injection, SSL config, timeout propagation
- `aclose()` cleanup

**`tests/test_ledger.py`** *(expanded)*
- WAL crash recovery: buffer flushed after restart from partial WAL
- `ledger.log()` with and without backend, flush on buffer full
- `ledger.stop()` flushes pending events

**`tests/test_identity.py`** *(new — 26 tests)*
- `IdentityManager.__init__` with provided private key (else branch)
- `sign_message()` determinism, exception path → `HashedCryptoError` (mock C-ext)
- `verify_signature()` with explicit `public_key` argument, wrong key returns False
- `sign_data()` canonical JSON, exception path → `HashedCryptoError`
- `verify_signed_data()` — valid, tampered signature, tampered data, missing field
- `export_private_key()` with password → encrypted PEM, roundtrip with/without password
- `from_private_key_bytes()` — wrong password, garbage bytes, wrong key type (ECDSA)
- Public key properties: 32-byte raw, 64-char hex, roundtrip

**`tests/test_guard.py`** *(expanded — 22 new tests)*
- `Policy.validate()` — all branches: `allowed=False`, within limit, at boundary, exceeds limit, `amount=None` with max
- `PolicyEngine.remove_policy()` — removes, raises `KeyError` on missing
- `PolicyEngine.has_policy()` — True/False
- `PolicyEngine.set_default_policy()` — deny-all blocks unknowns, max_amount enforced on unknowns
- `PolicyEngine.check_permission()` — returns False on denied, False on exceeded, True on allowed
- `PolicyEngine.list_policies()` — returns defensive copy
- `PolicyEngine.bulk_add_policies()` — adds all at once
- `PolicyEngine.export_policies()` + `import_policies()` — roundtrip preserves all data

#### CI
- `--cov-fail-under=59` added to `pytest` step in `.github/workflows/ci.yml`
  — Any PR that drops coverage below 59% now fails the test job, preventing silent regressions

### Changed
- Coverage thresholds are now enforced at the pipeline level (floor: 59%)

### Fixed
- `@guard()` decorator: policy denial was not being logged to the backend audit trail
- `@guard()` decorator: by default (`raise_on_deny=False`) now returns a human-readable string instead of raising `PermissionError` — prevents LangChain/CrewAI agents from crashing on governance blocks

### Coverage Summary

| Module | v0.1.0 | v0.2.0 | Δ |
|--------|--------|--------|---|
| `client.py` | ~30% | **100%** | +70 pp |
| `guard.py` | ~10% | **100%** | +90 pp |
| `identity_store.py` | 43% | **98%** | +55 pp |
| `templates.py` | 0% | **97%** | +97 pp |
| `identity.py` | 0% | **97%** | +97 pp |
| `http_client.py` | 24% | **95%** | +71 pp |
| `core.py` | 15% | **87%** | +72 pp |
| `ledger.py` | 60% | **84%** | +24 pp |
| **Total** | **17%** | **62%** | **+45 pp** |

---

## [0.1.0] — 2026-02-27

### 🎉 Initial Production Release

First production-ready release of Hashed SDK — AI Agent Governance Platform.

### Added

#### SDK (`src/hashed/`)
- `HashedCore` — main entry point for agent initialization and governance
- `@core.guard()` — decorator for policy-enforced tool execution
- `PolicyEngine` — local + remote policy evaluation
- `IdentityManager` — Ed25519 cryptographic identity per agent
- `AsyncLedger` — buffered audit log shipping to backend
- Auto policy push on first agent registration
- Policy diff-sync: local `.hashed_policies.json` → backend (upsert new, delete removed)
- 5 framework templates: plain, LangChain, CrewAI, Strands, AutoGen
- `hashed init <framework>` CLI command to scaffold agent code

#### CLI (`src/hashed/cli.py`)
- `hashed signup` — create account (email + org)
- `hashed login` — authenticate and store API key
- `hashed logout` — clear credentials
- `hashed whoami` — show current user info
- `hashed init [--framework]` — scaffold agent from template
- `hashed agent list` — list registered agents
- `hashed agent delete --id <id>` — remove agent from backend + clean local config
- `hashed policy add/list/remove` — manage local policy file
- `hashed policy push` — sync local policies to backend (diff-sync)
- `hashed policy pull` — download backend policies
- `hashed policy test --tool <name>` — test policy evaluation
- `hashed logs list` — query audit logs
- `hashed identity create/show/sign` — manage Ed25519 identities

#### Backend (`server/server.py`)
- FastAPI Control Plane with 19 REST endpoints
- Supabase integration (PostgreSQL + Row Level Security)
- Ed25519 signature verification for audit logs
- `POST /v1/auth/signup` — user registration with email confirmation
- `POST /v1/auth/login` — authentication with API key return
- `GET /v1/auth/check-confirmation` — email confirmation polling
- `GET /v1/auth/me` — current user info
- `POST /v1/agents/register` — agent registration
- `GET /v1/agents` — list agents
- `DELETE /v1/agents/{id}` — delete agent + cascade policies
- `GET /v1/policies` — list policies
- `POST /v1/policies` — create/update policy (upsert)
- `DELETE /v1/policies/{id}` — delete policy
- `GET /v1/policies/sync` — sync policies to SDK
- `POST /v1/logs/batch` — ingest audit logs
- `GET /v1/logs` — query logs with filters
- `GET /v1/analytics/summary` — agent activity summary
- `GET /v1/approvals/pending` — human-in-the-loop queue
- `POST /v1/approvals/{id}/decide` — approve/reject operations
- `GET /health` — health check endpoint

#### Infrastructure
- Dockerfile (Railway production, multi-stage build)
- `server/Dockerfile` (local docker-compose)
- `server/docker-compose.yml` (local dev with hot-reload)
- `railway.toml` — Railway deployment config with healthcheck
- `.github/workflows/ci.yml` — lint (ruff) + type check (mypy) + pytest + Docker build
- `.github/workflows/deploy.yml` — auto-deploy to Railway on push to main/staging

#### Dashboard (`hashed-dashboard` — private repo)
- Next.js 15 dashboard deployed on Vercel
- Agents management page
- Policies management page
- Audit logs viewer
- Login / signup with Supabase Auth

### Configuration
- SDK defaults to `https://iamandagent-production.up.railway.app` as backend URL
- Supports `BACKEND_URL` / `HASHED_BACKEND_URL` env var overrides
- Credentials stored in `~/.hashed/credentials.json`

---

## [0.0.1] — 2026-02-01

### Added
- Initial project scaffolding
- Basic `HashedCore` and `HashedConfig` classes
- Project structure: `src/hashed/`, `tests/`, `examples/`

---

[Unreleased]: https://github.com/Josoriop9/IAMandagent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Josoriop9/IAMandagent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.1.0
[0.0.1]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.0.1
