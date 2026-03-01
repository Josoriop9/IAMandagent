# Hashed SDK — Production Roadmap

> Last updated: 2026-02-28  
> Status: **Sprint 2 complete** — all security & reliability items done, ready for distribution

---

## Current State

The core product is live end-to-end and actively hardened:

- ✅ SDK (`HashedCore`, `@core.guard()`, `PolicyEngine`)
- ✅ CLI (`hashed init / policy / agent / logs`)
- ✅ Backend FastAPI + Supabase → **https://iamandagent-production.up.railway.app**
- ✅ Dashboard (Next.js) → **https://hashed-dashboard.vercel.app** (private repo)
- ✅ 5 framework templates (plain, LangChain, CrewAI, Strands, AutoGen)
- ✅ Auto policy push on first agent run
- ✅ Policy diff-sync (push deletes extras from backend)
- ✅ Agent delete (backend + local JSON cleanup)
- ✅ Cryptographic audit trail (Ed25519)
- ✅ GitHub Actions CI/CD (smoke tests post-Railway deploy)
- ✅ Railway production deploy (Docker multi-stage)
- ✅ Vercel dashboard deploy
- ✅ Separate private repo for dashboard (hashed-dashboard)
- ✅ SDK defaults to production backend URL
- ✅ **guard() denial logged to backend** — audit trail now records denied ops
- ✅ **guard() graceful return** — LangChain/CrewAI agents don't crash on policy denial
- ✅ **Rate limiting** — signup 5/min, login 10/min, default 300/min (slowapi)
- ✅ **Retry logic with jitter** — exponential backoff, respects Retry-After, 30s cap
- ✅ **14 unit tests for @core.guard()** — all passing
- ✅ **Ed25519 signature on `/guard`** — SDK signs + backend verifies (prevents impersonation)
- ✅ **Ledger durability** — SQLite WAL, logs survive crashes, replayed on restart
- ✅ **FastAPI lifespan** — proper startup/shutdown, connection pool foundation

---

## Priority 1 — Security

| Item | Effort | Status |
|------|--------|--------|
| **Rate limiting on all API endpoints** | 2h | ✅ Done — slowapi, 300 req/min default |
| **Force HTTPS + HSTS** | 1h | ✅ Railway handles HTTPS automatically |
| **Verify agent signature on `/guard`** | 4h | ✅ Done — SDK signs + backend verifies (Ed25519) |
| **API key expiration + rotation endpoint** | 4h | ❌ Pending |
| **Move secrets to environment vault** | 2h | ✅ Done — Railway/Vercel env vars |
| **Add CORS allowlist** (not wildcard) | 1h | ✅ Done — ALLOWED_ORIGINS configured |

---

## Priority 2 — Reliability

| Item | Effort | Status |
|------|--------|--------|
| **Retry logic with exponential backoff** | 3h | ✅ Done — jitter + Retry-After + 30s cap |
| **Graceful degradation** (guard returns string on deny) | 4h | ✅ Done — raise_on_deny=False default |
| **Ledger durability** (persist buffer to disk) | 4h | ✅ Done — SQLite WAL, crash-safe, auto-replay |
| **Connection pooling** in FastAPI | 2h | ✅ Done — FastAPI lifespan, httpx connection limits |

---

## Priority 3 — CI/CD & Testing

| Item | Effort | Status |
|------|--------|--------|
| **GitHub Actions CI** (test on every push) | 2h | ✅ Done — ci.yml |
| **GitHub Actions smoke tests** (post-deploy) | 2h | ✅ Done — deploy.yml simplified |
| **Unit tests for `@core.guard()`** | 1 day | ✅ Done — 14 tests, 0 failures |
| **Integration tests for CLI commands** | 1 day | ✅ Done — 11 CLI tests (Typer CliRunner, local commands) |
| **API tests for backend endpoints** | 1 day | ✅ Done — 9 FastAPI tests (TestClient, Supabase mocked) |
| **Code coverage badge in README** | 30min | ✅ Done — shields.io badge, 37% coverage, XML report |

---

## Priority 4 — Deploy / Infrastructure

| Item | Effort | Status |
|------|--------|--------|
| **Dockerfile for backend server** | 2h | ✅ Done |
| **`docker-compose.yml`** | 2h | ✅ Done |
| **Deploy to Railway** | 2h | ✅ Done — live |
| **Supabase production project** | 1h | ⚠️ Using same project for now |
| **Health check endpoint** | 1h | ✅ Done — `/health` returns 200 |

---

## Priority 5 — SDK Distribution

| Item | Effort | Status |
|------|--------|--------|
| **Publish to PyPI** as `hashed-sdk` | 2h | ❌ Pending — next |
| **Semantic versioning + CHANGELOG.md** | 1h | ✅ Done — v0.1.0 |
| **GitHub Releases** with release notes | 30min | ❌ Pending — next |
| **Optional extras in `pyproject.toml`** | 1h | ❌ Pending |

---

## Priority 6 — Dashboard Improvements

| Item | Effort | Status |
|------|--------|--------|
| **Pagination** on logs and agents | 1 day | ❌ Pending |
| **Real-time updates** (Supabase realtime) | 1 day | ❌ Pending |
| **Activity charts** | 1 day | ❌ Pending |
| **API key management UI** | 1 day | ❌ Pending |
| **Policy editor UI** | 2 days | ❌ Pending |

---

## Priority 7 — Documentation

| Item | Effort | Status |
|------|--------|--------|
| CLI Reference | 2h | ✅ `CLI_GUIDE.md` |
| API Reference | 2h | ✅ `API_REFERENCE.md` |
| SDK Integration Guide | 2h | ✅ `INTEGRATION.md` |
| Quickstart / README | 2h | ✅ `README.md` |
| Repository structure guide | 1h | ✅ `REPOS.md` |
| Framework-specific guides | 4h | 🔄 Partial |
| Video walkthrough | 1 day | ❌ Not started |

---

## Sprint Status

### ✅ Sprint 1 — MVP (complete)
All core features live: SDK, CLI, backend, dashboard, CI/CD.

### ✅ Sprint 2 — Harden & Distribute (complete)
- ✅ Rate limiting (slowapi)
- ✅ Retry logic with jitter
- ✅ Guard denial logging + graceful return
- ✅ Unit tests for guard (14/14)
- ✅ Ed25519 signature on /guard (impersonation prevention)
- ✅ Ledger durability (SQLite WAL)
- ✅ FastAPI lifespan + connection pooling

### 🚀 Sprint 3 — Distribute + Dashboard (next)
- ❌ PyPI publish → `pip install hashed-sdk`
- ❌ GitHub Release v0.1.0
- ❌ API key rotation endpoint
- ❌ Pagination on logs and agents tables
- ❌ Real-time log feed (Supabase realtime)
- ❌ Policy editor UI

### Sprint 4 — Reliability & Scale (planned)
- Local policy fallback (offline mode, no backend needed)
- Supabase production project (separate from dev/staging)
- Increase test coverage from 37% → 60%+
- Network-mocked CLI tests (policy push, agent list)

---

## Non-Goals (v1)

- Multi-region deployment
- Self-hosted Supabase
- Enterprise SSO (SAML)
- Webhook notifications
