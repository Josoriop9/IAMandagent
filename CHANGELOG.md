# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Rate limiting on all API endpoints
- API key expiration + rotation endpoint
- Unit tests for `@core.guard()` (allow/deny/log paths)
- Integration tests for CLI commands
- Ledger durability (persist buffer to disk)
- Graceful degradation (local policy fallback when backend is down)

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

[Unreleased]: https://github.com/Josoriop9/IAMandagent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.1.0
[0.0.1]: https://github.com/Josoriop9/IAMandagent/releases/tag/v0.0.1
