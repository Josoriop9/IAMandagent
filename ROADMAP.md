# Hashed SDK — Production Roadmap

> Last updated: 2026-02-27  
> Status: **v0.1.0 shipped** — backend live, dashboard live, SDK installable

---

## Current State

The core product is live end-to-end:

- ✅ SDK (`HashedCore`, `@core.guard()`, `PolicyEngine`)
- ✅ CLI (`hashed init / policy / agent / logs`)
- ✅ Backend FastAPI + Supabase → **https://iamandagent-production.up.railway.app**
- ✅ Dashboard (Next.js) → **https://hashed-dashboard.vercel.app** (private repo)
- ✅ 5 framework templates (plain, LangChain, CrewAI, Strands, AutoGen)
- ✅ Auto policy push on first agent run
- ✅ Policy diff-sync (push deletes extras from backend)
- ✅ Agent delete (backend + local JSON cleanup)
- ✅ Cryptographic audit trail (Ed25519)
- ✅ GitHub Actions CI/CD (ci.yml + deploy.yml)
- ✅ Railway production deploy (Docker multi-stage)
- ✅ Vercel dashboard deploy
- ✅ Separate private repo for dashboard (hashed-dashboard)
- ✅ SDK defaults to production backend URL

---

## Priority 1 — Security

| Item | Effort | Status |
|------|--------|--------|
| **Rate limiting on all API endpoints** | 2h | ❌ Pending |
| **Force HTTPS + HSTS** | 1h | ✅ Railway handles HTTPS automatically |
| **Verify agent signature on `/guard`** | 4h | ❌ Pending |
| **API key expiration + rotation endpoint** | 4h | ❌ Pending |
| **Move secrets to environment vault** | 2h | ✅ Done — Railway/Vercel env vars |
| **Add CORS allowlist** (not wildcard) | 1h | ✅ Done — ALLOWED_ORIGINS configured |

---

## Priority 2 — Reliability

| Item | Effort | Status |
|------|--------|--------|
| **Retry logic with exponential backoff** | 3h | ❌ Pending |
| **Ledger durability** (persist buffer to disk) | 4h | ❌ Pending |
| **Graceful degradation** (local policy fallback) | 4h | ❌ Pending |
| **Connection pooling** in FastAPI | 2h | ❌ Pending |

---

## Priority 3 — CI/CD & Testing

| Item | Effort | Status |
|------|--------|--------|
| **GitHub Actions CI** (test on every push) | 2h | ✅ Done — ci.yml |
| **Unit tests for `@core.guard()`** | 1 day | ❌ Pending |
| **Integration tests for CLI commands** | 1 day | ❌ Pending |
| **API tests for backend endpoints** | 1 day | ❌ Pending |
| **Code coverage badge in README** | 30min | ❌ Pending |

---

## Priority 4 — Deploy / Infrastructure

| Item | Effort | Status |
|------|--------|--------|
| **Dockerfile for backend server** | 2h | ✅ Done |
| **`docker-compose.yml`** | 2h | ✅ Done |
| **Deploy to Railway** | 2h | ✅ Done — live |
| **Supabase production project** | 1h | ⚠️ Using same project for now |
| **Health check endpoint** | 1h | ✅ Done — `/health` |

---

## Priority 5 — SDK Distribution

| Item | Effort | Status |
|------|--------|--------|
| **Publish to PyPI** as `hashed-sdk` | 2h | ❌ Pending |
| **Semantic versioning + CHANGELOG.md** | 1h | ✅ Done — v0.1.0 |
| **GitHub Releases** with release notes | 30min | ❌ Pending |
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

## Suggested Next Sprint

### Sprint 2 — Harden & Distribute (1 week)
1. **PyPI publish** → `pip install hashed-sdk`
2. **Rate limiting** → `slowapi` on FastAPI
3. **Unit tests** for `@core.guard()` 
4. **API key rotation** endpoint
5. **GitHub Release** for v0.1.0

### Sprint 3 — Dashboard (1 week)
- Pagination on all tables
- Real-time log feed
- Policy editor UI
- Activity charts

### Sprint 4 — Reliability (1 week)
- Ledger durability
- Retry logic
- Local policy fallback
- Supabase production project (separate from dev)

---

## Non-Goals (v1)

- Multi-region deployment
- Self-hosted Supabase
- Enterprise SSO (SAML)
- Webhook notifications
