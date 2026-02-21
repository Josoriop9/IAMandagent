# Database Migration Guide
## Connecting Users to Organizations

Follow these steps to enable real data in your dashboard.

---

## 🎯 What These Migrations Do

1. **Add owner_id column** to `organizations` table
2. **Create trigger** to auto-create organization when user signs up
3. **Link existing users** to organizations (including YOU!)
4. **Update RLS policies** so users only see their own data

---

## 📝 Step-by-Step Instructions

### Step 1: Open Supabase SQL Editor

1. Go to https://supabase.com/dashboard
2. Select your project: `hashed-control-plane`
3. Click **SQL Editor** (</>) in the left sidebar
4. Click **New query**

---

### Step 2: Execute First Migration

Copy ALL the content from:
```
database/add_user_org_link.sql
```

Paste it into the SQL Editor and click **Run** (▶️)

**Expected result**: ✅ Success

This will:
- Add `owner_id` column to organizations
- Create auto-signup trigger
- Update Row Level Security policies

---

### Step 3: Execute Second Migration

Click **New query** again

Copy ALL the content from:
```
database/link_existing_users.sql
```

Paste it into the SQL Editor and click **Run** (▶️)

**Expected result**: 
```
NOTICE:  Created organization for user: your@email.com
```

You'll also see a table showing your email + organization + API key!

---

### Step 4: Verify in Table Editor

1. Click **Table Editor** in left sidebar
2. Click `organizations` table
3. You should see:
   - Your organization row
   - `owner_id` column with your user UUID
   - Your unique `api_key`

---

## ✅ After Migration

### Refresh Your Dashboard

Go back to http://localhost:3001/dashboard and refresh

You should now see:
- **Real numbers**: 0 agents, 0 policies, 0 logs (because you haven't used the SDK yet!)
- **Your API Key**: Displayed in a new section
- **Copy button**: To copy your API key

---

## 🧪 Test with SDK

Now you can use YOUR API key:

```python
from hashed import HashedCore
from hashed.config import HashedConfig

# Use YOUR api_key from the dashboard!
config = HashedConfig(
    backend_url="http://localhost:8000",
    api_key="hashed_your_key_here"  # ← Copy from dashboard
)

core = HashedCore(config=config, agent_name="My First Agent")
await core.initialize()

# This will:
# - Register YOUR agent
# - Sync policies to YOUR organization
# - Send logs to YOUR organization
```

Run the agent, then refresh the dashboard → You'll see:
- Agents: 1
- Policies: X (however many you configured)
- Logs: Y (however many operations)

---

## 🐛 Troubleshooting

### Error: "permission denied for table organizations"

The service_role key needs permission. In Supabase:
1. Go to Settings → API
2. Copy the `service_role` key (not anon!)
3. Make sure it's the secret key

### No organization created for my user

Check if the trigger is enabled:
```sql
SELECT * FROM pg_trigger WHERE tgname = 'on_auth_user_created';
```

### I see "Error fetching organization" in console

Your user might not have an organization yet. Run `link_existing_users.sql` again.

---

## ✨ What's Next

Once migration is complete:
1. ✅ Dashboard shows YOUR real data
2. ✅ You have YOUR unique API key
3. ✅ SDK connects to YOUR organization
4. ✅ All agents/policies/logs are scoped to YOU

Ready to build the rest of the dashboard pages! 🚀
