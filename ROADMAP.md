# Hashed SDK — Production Roadmap

> Last updated: 2026-02-26  
> Status: **MVP complete** — preparing for production

---

## Current State

The core product is functional end-to-end:

- ✅ SDK (`HashedCore`, `@core.guard()`, `PolicyEngine`)
- ✅ CLI (`hashed init / policy / agent / logs`)
- ✅ Backend FastAPI + Supabase
- ✅ Dashboard (Next.js)
- ✅ 5 framework templates (plain, LangChain, CrewAI, Strands, AutoGen)
- ✅ Auto policy push on first agent run
- ✅ Policy diff-sync (push deletes extras from backend)
- ✅ Agent delete (backend + local JSON cleanup)
- ✅ Cryptographic audit trail (Ed25519)

---

## Priority 1 — Security (Do before any external user)

| Item | Effort | Why |
|------|--------|-----|
| **Rate limiting on all API endpoints** | 2h | Prevent abuse / DDoS |
| **Force HTTPS + HSTS** | 1h | Data in transit protection |
| **Verify agent signature on `/guard`** | 4h | Backend currently trusts public key without signature check |
| **API key expiration + rotation endpoint** | 4h | Keys should have TTL |
| **Move secrets to environment vault** (Railway / Render env vars, not `.env` file in repo) | 2h | No secrets in filesystem |
| **Add CORS allowlist** (not wildcard) | 1h | Lock down who can call backend |

---

## Priority 2 — Reliability

| Item | Effort | Why |
|------|--------|-----|
| **Retry logic with exponential backoff** in HTTP client | 3h | Backend blips shouldn't crash agents |
| **Ledger durability**: persist buffer to disk before flush | 4h | Audit logs lost if process dies mid-run |
| **Graceful degradation**: if backend is down, agents should still run (local policy fallback) | 4h | Offline-first resilience |
| **Connection pooling** in FastAPI (Supabase client reuse) | 2h | Current: new client per request |

---

## Priority 3 — CI/CD & Testing

| Item | Effort | Why |
|------|--------|-----|
| **GitHub Actions workflow** (test on every push to main) | 2h | Catch regressions early |
| **Unit tests for `@core.guard()`** — allow/deny/log paths | 1 day | Core logic is untested |
| **Integration tests for CLI commands** | 1 day | `hashed policy push`, `agent delete`, etc. |
| **API tests for backend endpoints** | 1 day | FastAPI test client |
| **Code coverage badge in README** | 30min | Signal quality |

---

## Priority 4 — Deploy / Infrastructure

| Item | Effort | Why |
|------|--------|-----|
| **Dockerfile for backend server** | 2h | Reproducible deploys |
| **`docker-compose.yml`** (server + local Supabase) | 2h | One-command local dev |
| **Deploy to Railway / Render / Fly.io** | 2h | Public backend URL for SDK users |
| **Supabase production project** (separate from dev) | 1h | Isolate prod data |
| **Health check endpoint improvements** (DB ping) | 1h | Load balancer readiness probe |

---

## Priority 5 — SDK Distribution

| Item | Effort | Why |
|------|--------|-----|
| **Publish to PyPI** as `hashed-sdk` | 2h | `pip install hashed-sdk` instead of git URL |
| **Semantic versioning + CHANGELOG.md** | 1h | Track what changed between versions |
| **GitHub Releases** with release notes | 30min | Discoverability |
| **Optional extras in `pyproject.toml`** (`[langchain]`, `[crewai]`, etc.) | 1h | Users only install what they need |

---

## Priority 6 — Dashboard Improvements

| Item | Effort | Why |
|------|--------|-----|
| **Pagination** on logs and agents tables | 1 day | Current: loads all records |
| **Real-time updates** (Supabase realtime subscriptions) | 1 day | Live audit feed |
| **Activity charts** (tool calls over time per agent) | 1 day | Visual governance |
| **API key management UI** (create, rotate, revoke) | 1 day | Self-serve key rotation |
| **Policy editor UI** (CRUD without CLI) | 2 days | Non-technical operators |

---

## Priority 7 — Documentation (in progress)

| Item | Effort | Status |
|------|--------|--------|
| CLI Reference | 2h | ✅ `CLI_GUIDE.md` |
| API Reference | 2h | ✅ `API_REFERENCE.md` (needs update) |
| SDK Integration Guide | 2h | ✅ `INTEGRATION.md` |
| Quickstart / README | 2h | ✅ `README.md` |
| Framework-specific guides | 4h | 🔄 Partial |
| Video walkthrough | 1 day | ❌ Not started |

---

## Suggested Sprint Order

### Sprint 1 — Harden (1 week)
- Rate limiting
- HTTPS + CORS
- Dockerfile + deploy to Railway
- GitHub Actions CI

### Sprint 2 — Quality (1 week)
- Test suite (guard, CLI, API)
- Ledger durability
- Retry logic
- PyPI publish

### Sprint 3 — Dashboard (1 week)
- Pagination
- Real-time logs
- Policy editor UI

### Sprint 4 — Growth (ongoing)
- API key management
- Activity charts
- More framework templates
- Video docs

---

## Non-Goals (v1)

- Multi-region deployment
- Self-hosted Supabase
- Enterprise SSO (SAML)
- Webhook notifications

These are post-v1 features.
