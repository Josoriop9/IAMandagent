# Repository Structure & Configuration

This project is split across **two GitHub repositories** to separate the open-source SDK/backend from the private SaaS dashboard.

---

## 📦 Repositories

### 1. `IAMandagent` — Public (Open Source)
**URL:** https://github.com/Josoriop9/IAMandagent

**Contains:**
- `src/hashed/` — Python SDK (`pip install hashed-sdk`)
- `server/` — FastAPI backend (Control Plane API)
- `tests/` — Test suite
- `examples/` — Usage examples
- `database/` — Supabase schema & migrations
- Documentation (README, CLI_GUIDE, API_REFERENCE, etc.)

**Deployed to:** Railway → https://iamandagent-production.up.railway.app

**Git remote (local):**
```bash
# From /Desktop/Devs/hashed
git remote -v
# origin  https://github.com/Josoriop9/IAMandagent.git
```

---

### 2. `hashed-dashboard` — Private (SaaS Product)
**URL:** https://github.com/Josoriop9/hashed-dashboard *(private)*

**Contains:**
- `app/` — Next.js 15 pages (dashboard, login, agents, policies, logs)
- `components/` — Reusable UI components
- `lib/supabase.ts` — Supabase client
- Tailwind CSS config

**Deployed to:** Vercel → (your Vercel URL)

**Git remote (local):**
```bash
# From /Desktop/Devs/hashed/dashboard
git remote -v
# origin  https://github.com/Josoriop9/hashed-dashboard.git
```

---

## 🗂️ Local Folder Structure

The `dashboard/` folder lives **inside** the main `hashed/` workspace on your machine, but it has its **own `.git`** pointing to the private repo.

```
/Desktop/Devs/hashed/          ← git → IAMandagent (public)
├── src/hashed/
├── server/
├── tests/
├── dashboard/                  ← git → hashed-dashboard (private)
│   ├── app/
│   ├── components/
│   └── lib/
└── .gitignore                  ← dashboard/ is ignored in public repo
```

---

## 🔄 Git Workflow

### Working on the SDK / Backend (public repo):
```bash
cd /Desktop/Devs/hashed
git add .
git commit -m "feat: your message"
git push origin main            # → github.com/Josoriop9/IAMandagent
```

### Working on the Dashboard (private repo):
```bash
cd /Desktop/Devs/hashed/dashboard
git add .
git commit -m "feat: your message"
git push origin main            # → github.com/Josoriop9/hashed-dashboard
```

---

## 🚀 Deployments

| Component | Platform | Trigger | URL |
|---|---|---|---|
| FastAPI Backend | Railway | Push to `main` (IAMandagent) | https://iamandagent-production.up.railway.app |
| Next.js Dashboard | Vercel | Push to `main` (hashed-dashboard) | *(your Vercel URL)* |
| Python SDK | PyPI | Version bump in `pyproject.toml` | `pip install hashed-sdk` |

---

## 🔐 Required Environment Variables

### Railway (Backend)
| Variable | Description |
|---|---|
| `SUPABASE_URL` | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase service role key |
| `SECRET_KEY` | Random 64-char secret |
| `ALLOWED_ORIGINS` | Vercel dashboard URL |
| `PUBLIC_BACKEND_URL` | `https://iamandagent-production.up.railway.app` |

### Vercel (Dashboard)
| Variable | Description |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `NEXT_PUBLIC_BACKEND_URL` | `https://iamandagent-production.up.railway.app` |

---

## 📋 Branches

| Branch | Purpose | Auto-deploys to |
|---|---|---|
| `main` | Production | Railway (prod) + Vercel (prod) |
| `staging` | Pre-production testing | Railway (staging) |

---

## 🌿 Branching Strategy

### Branches

| Branch | Purpose | Auto-deploys to |
|---|---|---|
| `main` | Production — what users see | Railway prod + Vercel prod |
| `staging` | Pre-production testing | Railway staging |
| `feature/xxx` | Individual changes | Nowhere (local only) |

### The golden rule: **nothing goes directly to `main`**

```
feature/my-change  →  staging  →  main
    (develop)         (test)     (production)
```

### Daily workflow

```bash
# 1. Start new work — always branch from main
git checkout main && git pull
git checkout -b feature/rate-limiting

# 2. Develop and test locally

# 3. Push to staging to test in production-like environment
git checkout staging
git merge feature/rate-limiting
git push origin staging
# → Railway staging auto-deploys

# 4. Test on staging URL, verify everything works

# 5. Merge to main when ready
git checkout main
git merge staging
git push origin main
# → Railway prod + Vercel prod auto-deploy

# 6. Clean up feature branch
git branch -d feature/rate-limiting
```

### For dashboard changes (private repo)

```bash
cd /Desktop/Devs/hashed/dashboard

# Same pattern
git checkout -b feature/pagination
# ... develop ...
git checkout main
git merge feature/pagination
git push origin main   # → Vercel deploys
```

### What to test on staging

- ✅ Backend API responses
- ✅ CLI commands against staging backend
- ✅ SDK behavior end-to-end
- ✅ Dashboard UI flows

### Setting staging backend URL for testing

```bash
# Tell CLI to use staging backend instead of prod
export HASHED_BACKEND_URL=https://your-staging-url.up.railway.app
hashed login
hashed agent list
```

---

## ⚠️ Important Notes

1. **Never commit `.env` files** — use Railway/Vercel environment variables
2. **The `dashboard/` folder is gitignored** in the public repo — changes there only go to `hashed-dashboard`
3. **Supabase anon key** (public) goes in Vercel — **service role key** (private) goes in Railway only
4. After adding new env vars in Railway/Vercel, a **manual redeploy** may be needed
