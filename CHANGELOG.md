# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.4.0] — 2026-04-22

### New Features

- **Canonical signed payloads** with `nonce`, `timestamp_ns`, and `version` per SPEC §2.1 — every `@guard()` call now produces a full Ed25519-signed envelope; `sign_operation()` replaces the deprecated `sign_data()`.
- **Forward-linked hash chain in `AsyncLedger`** — every WAL entry stores `prev_hash` and `entry_hash` (SHA-256). Retroactive tampering detectable in O(n) via `verify_chain()` (SPEC §3.2).
- **Real LangChain integration (`HashedCallbackHandler`)** — `pip install hashed-sdk[langchain]`. Drop-in `BaseCallbackHandler` that enforces `PolicyEngine` on `on_tool_start`, logs signed envelopes on `on_tool_end` and `on_tool_error`. No langchain required in test environment.

### Improvements

- Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)` project-wide (ruff `UP` compliance).
- Updated module docstrings to reflect AI agent governance focus (`__init__.py`, `models.py`, `crypto/__init__.py`).
- `pyproject.toml`: version bumped to `0.4.0`; added `# NOTE` comment on `[crewai]`/`[autogen]`/`[strands]` extras not yet having integration modules.

### Backwards Compatibility

- `sign_data()` retained with `DeprecationWarning`; `sign_operation()` is the new canonical API.
- All public API signatures in `__all__` unchanged.
- `AsyncLedger` WAL databases from v0.3.x auto-migrate (existing rows stamped as `legacy` anchors; new rows extend the chain).

### Roadmap

- CrewAI integration (`wrap_tool` + `HashedBaseTool`): planned for v0.5.0
- AutoGen integration: planned for v0.5.0
- AWS Strands integration: planned for v0.6.0
- MCP Server (`hashed mcp`): planned for v0.5.0

---

## [0.3.1] — 2026-03-15

### Added
- **`SPEC.md`** — Hashed Identity Protocol (HIP) technical specification:
  Ed25519 key derivation, canonical signature payload structure,
  ledger immutability via forward-linked hash chain, circuit breaker FSM.
- **README "God Mode"** — restructured above-the-fold for PyPI visibility:
  Quick Install, The 3-Line Demo, Official Links table.

### Changed
- **README badges** updated: CI (dynamic GitHub Actions), Security Audit: Pending,
  License: MIT, Coverage: 76%, Tests: 422 passed.

## [0.3.0] — 2026-03-15

### Added
- **Circuit Breaker** (`_CircuitBreaker` class in `core.py`) — opens after 3 consecutive backend
  failures, 60-second cooldown, auto-resets on first success after cooldown.
  Configurable via `HASHED_FAIL_CLOSED=true` (deny on outage) or default fail-open (allow on outage).
- **Performance tracking** — every `@guard`-decorated call logs
  `[hashed] '<tool>' governance overhead: X.Xms` at DEBUG level.
- **Async/sync interop fix** — `sync_wrapper` now detects a running event loop and
  uses `ThreadPoolExecutor` to avoid `RuntimeError: This event loop is already running`
  (FastAPI, Jupyter, pytest-asyncio environments).
- **Exponential backoff in background policy sync** — on failure: 10 s → 20 s → 40 s → … → 300 s cap;
  resets to 0 after a successful sync.
- **`circuit_breaker` property** on `HashedCore` — exposes the `_CircuitBreaker` instance
  for external observability and testing.
- **28 new tests** in `tests/test_circuit_breaker.py` covering all new code paths.

### Changed
- `guard()` god-method decomposed into five focused helpers following SRP:
  `_validate_local_policy`, `_execute_remote_guard`, `_log_to_all_transports`,
  `_log_denial`, `_log_error`.
- `HashedConfig` is accessed via `with_overrides()` (frozen Pydantic model — never mutated directly).

### Fixed
- `ruff I001` lint — `import logging` moved to module level in test files.

### Metrics
- `core.py` branch coverage: **84% → 91%**
- Total test suite: **422 passed, 0 failed** (from 394)

### Planned
- Ledger durability (persist buffer to disk on crash)
- API key expiration (TTL-based auto-rotation)
- WebSocket support for `hashed logs tail --follow` (real-time streaming)
- OpenTelemetry spans export from `@core.guard()`
- `cli.py` tests → coverage target 80%
- Framework-specific guides: LangChain, CrewAI, Strands, AutoGen (complete)

---

## [0.2.1] — 2026-03-14

### 🚀 Sprint 6 — Distribution Prep

#### CLI Banner (`src/hashed/banner.py`) *(new module)*
- New `show_banner()` function — renders `#` logo + `HASHED` block art side by side
- `#` symbol is the brand mark: hash (product) + code comment + hashtag
- Only appears on `hashed` with no subcommand (`invoke_without_command=True`)
- All other commands (`hashed login`, `hashed policy list`, etc.) are silent
- Zero new dependencies — uses Rich only (already in core deps)

#### CLI Version (`src/hashed/cli.py`)
- `hashed version` now reads `__version__` dynamically from `src/hashed/__init__.py`
- Previously hardcoded to `"0.2.0"` — would drift silently on every release

#### Documentation (`README.md`)
- ASCII art banner centered at top (like professional open-source repos)
- PyPI badge added (will show live version once published)
- Coverage badge updated: 37% → 73% (brightgreen)
- Tests badge updated: 76 → 344 passed
- Quick Start now shows `pip install hashed-sdk` + all optional extras
- Recent Updates section: v0.2.1, v0.2.0, v0.1.0
- Core Concepts: 5 sections with working code examples
- Full LLM integration example (OpenAI + Hashed)
- Architecture diagram (ASCII boxes: SDK → Backend → DB → Dashboard)
- All repo links corrected to `github.com/Josoriop9/IAMandagent`

#### Project Cleanup
- `dev_test_agent.py` (auto-generated, was in root) → `examples/dev_test_agent.py`
- 5 historical one-time SQL scripts → `database/archive/`
  (`add_agent_appearance`, `add_user_org_link`, `add_user_organizations`,
   `fix_status_constraint`, `link_existing_users`)
- `.gitignore`: added `secrets/` (local key files / PEMs)
- `build/` + `src/hashed_sdk.egg-info/`: confirmed never tracked by git ✅

### 🐛 Bug Fixes

#### Server (`server/server.py`)
- **Agent "Unknown" in `hashed logs list`** — `GET /v1/logs` was returning raw
  `ledger_logs` rows with only `agent_id` (UUID). CLI was calling
  `log.get("agent_name", "Unknown")` but the field never existed in the API
  response. Fix: changed `.select("*")` to `.select("*, agents(name)")` using
  PostgREST FK expansion (inline JOIN), then flattens `agents.name →
  agent_name` in the response loop. Zero-downtime deploy — no schema migration
  required.

- **CORS empty string edge case** — `os.getenv("ALLOWED_ORIGINS",
  "").split(",")` returned `[""]` when the env var was unset. `CORSMiddleware`
  received an invalid empty-string origin, silently blocking all cross-origin
  requests. Fix: filter empty strings with
  `[o.strip() for o in ... if o.strip()]`. If `ALLOWED_ORIGINS` is unset,
  middleware is not added at all.

#### Tests (`tests/`)
- **`test_whoami_with_credentials`** — `CREDENTIALS_FILE` is a module-level
  constant computed at import time. Patching `Path.home` via `monkeypatch`
  after import had no effect. Fix: directly patch
  `hashed.cli.CREDENTIALS_FILE` and `hashed.cli.CREDENTIALS_DIR` in the
  `fake_credentials` fixture.

#### Templates (`src/hashed/templates.py`)
- **TODO removed from generated scripts** — the plain-Python interactive loop
  template emitted `# TODO: route user_input to the appropriate guarded
  function`, visible to end users via GitHub. Replaced with a clear
  implementation comment + `agent.execute(user_input)` call.

### Added

#### Tests (`tests/test_cli_commands.py`) *(new — 24 tests)*
Previously the CLI had 0% test coverage for most commands. This file covers:

- **`hashed logs list`** (7 tests): agent_name display (Bug A regression),
  tool_name column, status icons (✓/✗), `--limit` flag forwarded, empty
  result, Unknown-fallback for logs without `agent_name`.
- **`hashed agent list`** (3 tests): name display, empty list, graceful
  exit without credentials.
- **`hashed agent` subcommands** (3 tests): `--help` output, `delete` no-args,
  credential loading verified via mock GET call count.
- **`hashed init`** (2 tests): no-credentials graceful exit, mocked HTTP.
- **`hashed policy push`** (2 tests): success with mocked agents+policies+delete,
  missing policy file graceful exit.
- **`hashed whoami` + `version`** (2 tests): credentials loaded, semver output.
- **CLI structure smoke tests** (5 tests): root `--help`, logs/policy `--help`,
  login without network, logout idempotent.

Python 3.9 compatible (no `X | Y` union syntax, no parenthesized `with`).
All 24 pass in 0.20s with zero real network calls.

**Coverage delta:** `cli.py` 0% → 29%, total 73% → 75%

#### Examples (`examples/quickstart.py`) *(new)*
Self-contained 30-second quickstart demonstrating the full SDK flow:
`HashedConfig` → `load_or_create_identity` → `HashedCore.initialize()` →
`@core.guard()` on 3 operations → audit trail via `hashed logs list`.
Includes inline comments explaining every step. Requires only
`hashed login` + `hashed init` to run.

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

[Unreleased]: https://github.com/Josoriop9/IAMandagent/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Josoriop9/IAMandagent/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/Josoriop9/IAMandagent/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Josoriop9/IAMandagent/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Josoriop9/IAMandagent/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Josoriop9/IAMandagent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.1.0
[0.0.1]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.0.1
