# Hashed SDK - Setup Guide
## Quick Start: Supabase + Backend Configuration

---

## ✅ Checklist

- [ ] Supabase account created
- [ ] Supabase project created
- [ ] Schema SQL executed
- [ ] Credentials copied
- [ ] Server .env configured
- [ ] Dependencies installed
- [ ] Server started
- [ ] Backend tested
- [ ] SDK integration tested

---

## 🔵 STEP 1: Create Supabase Account

1. Go to: **https://supabase.com**
2. Click **"Start your project"**
3. Sign up with GitHub, Google, or Email

---

## 🔵 STEP 2: Create New Project

1. Click **"New Project"**
2. Fill in:
   - **Name**: `hashed-control-plane`
   - **Database Password**: Create a strong password (SAVE IT!)
   - **Region**: Choose closest to you
   - **Plan**: Free (perfect for starting)
3. Click **"Create new project"**
4. Wait 1-2 minutes ⏱️

---

## 🔑 STEP 3: Get Your Credentials

### Get Project URL:
1. Click **"Settings"** (⚙️) in left panel
2. Click **"API"**
3. Copy **Project URL**:
   ```
   https://xxxxxxxxxxxxx.supabase.co
   ```
   ✍️ Save this as your `SUPABASE_URL`

### Get Service Role Key:
1. Same page (Settings → API)
2. Scroll to **"Project API keys"**
3. Find **`service_role`** `secret`
4. Click **"Reveal"**
5. Copy the key (starts with `eyJhbGc...`)
   ✍️ Save this as your `SUPABASE_SERVICE_KEY`

⚠️ **NEVER share the service_role key!**

---

## 💾 STEP 4: Run Schema SQL

1. Click **"SQL Editor"** (</>) in left panel
2. Click **"New query"**
3. Copy ALL content from `database/schema.sql`
4. Paste into Supabase SQL Editor
5. Click **"Run"** (▶️)
6. Wait a few seconds...
7. Should see: ✅ **"Success. No rows returned"**

---

## ✔️ STEP 5: Verify Database

1. Click **"Table Editor"** (table icon) in left panel
2. Should see 6 tables:
   - ✅ `organizations`
   - ✅ `agents`
   - ✅ `policies`
   - ✅ `ledger_logs`
   - ✅ `approval_queue`
   - ✅ `rate_limit_tracker`

3. Click `organizations` → Should see 1 test row

---

## 📝 STEP 6: Configure Server

Your credentials from Step 3:
```
SUPABASE_URL: https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Create `server/.env` file with these values (see next step for command).

---

## 🚀 STEP 7: Install & Start

```bash
# Go to server directory
cd server

# Create .env file from template
cp .env.example .env

# IMPORTANT: Now edit server/.env with your credentials!
# Replace SUPABASE_URL and SUPABASE_SERVICE_KEY with your values

# Install dependencies
pip3 install -r requirements.txt

# Start server
python3 server.py
```

Should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 🧪 STEP 8: Test Backend

Open NEW terminal (keep server running):

```bash
# Test health endpoint
curl http://localhost:8000/health

# Should return:
# {"status": "healthy", "timestamp": "...", "service": "hashed-control-plane"}
```

---

## 🎯 STEP 9: Test SDK Integration

```bash
python3 examples/quickstart.py
```

Should see:
- ✅ Agent registered
- ✅ Policies synced
- ✅ Operations executed
- ✅ Logs sent to backend

---

## 📊 STEP 10: Check Supabase Data

Go back to Supabase dashboard:

1. **Table Editor** → **`agents`**
   - Should see newly registered agent

2. **Table Editor** → **`ledger_logs`**
   - Should see operation logs

✅ **Everything working!**

---

## 🔧 Troubleshooting

### "SUPABASE_URL not set"
→ Check `server/.env` file exists and has correct values

### "Connection refused"
→ Make sure server is running: `python3 server.py`

### "Invalid API key"
→ Check `organizations` table has test data with correct api_key

### No logs in Supabase
→ Wait 5 seconds (batched sending) or check server logs

---

## 📞 Need Help?

1. Check server logs for errors
2. Verify Supabase credentials are correct
3. Make sure no firewalls blocking port 8000
4. Try restarting the server

---

## ✨ What's Next?

Once everything works:
- Create your own agents
- Define custom policies
- Build a dashboard
- Deploy to production
- Publish SDK to PyPI

**You're all set! 🎉**
