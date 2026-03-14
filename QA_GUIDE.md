# 🧪 QA Guide — Post-PyPI Validation

> **When to use this guide:** After `twine upload` succeeds and the package is live on PyPI.  
> Run every step in a **completely fresh directory** (not inside the `hashed` repo).

---

## 📋 Pre-flight Checklist

- [ ] `pip install hashed-sdk` (or `pip install hashed-sdk==0.2.1`)
- [ ] Fresh virtual environment (no editable installs)
- [ ] Backend Railway is running: `https://iamandagent-production.up.railway.app/health`

---

## Step 1 — Install from PyPI

```bash
# Create a clean test environment
mkdir /tmp/hashed-qa-test && cd /tmp/hashed-qa-test
python3 -m venv venv && source venv/bin/activate

# Install from PyPI (not from local)
pip install hashed-sdk

# Verify version
hashed version
# Expected: Hashed SDK version 0.2.1

pip show hashed-sdk
# Expected: Version: 0.2.1, Location: .../site-packages
```

**✅ Pass if:** version shows `0.2.1` and no import errors.

---

## Step 2 — CLI Commands

```bash
# Show banner and help
hashed
# Expected: ASCII art + command list

hashed --help
# Expected: Commands listed: signup, login, init, policy, agent, logs, etc.

hashed version
# Expected: Hashed SDK version 0.2.1
```

**✅ Pass if:** no errors, banner shows correctly.

---

## Step 3 — Signup (create account via CLI)

```bash
hashed signup
# Prompts:
#   Email: your-test@email.com
#   Password: ••••••••
#   Confirm password: ••••••••
#   Organization name: QA Test Org
#
# Expected flow:
#   ✓ Account created!
#   📧 Confirmation email sent to ...
#   ⏳ Waiting for email confirmation...
#
# → Check email → click confirmation link
#   ✓ Email confirmed!
#   ✓ Account Ready! (table with API Key)
#   ✓ Credentials saved to ~/.hashed/credentials.json
```

**✅ Pass if:** credentials file created, API key shown.

---

## Step 4 — Whoami

```bash
hashed whoami
# Expected:
# ┌──────────────────┬────────────────────────────┐
# │ Email            │ your-test@email.com         │
# │ Organization     │ QA Test Org                 │
# │ API Key          │ hsk_xxxxxxxxxxxxxxxxxxxx... │
# │ Backend          │ https://iamandagent-...     │
```

**✅ Pass if:** shows your credentials correctly.

---

## Step 5 — Init Agent (auto-generates HASHED_IDENTITY_PASSWORD)

```bash
hashed init --name "QA Agent" --type assistant

# Expected:
#   ✓ Created directory: ./secrets
#   ✓ Created .gitignore: ./secrets/.gitignore
#   ✓ Identity ready: ./secrets/qa_agent_key.pem       ← NO password prompt!
#   Table with Public Key, Agent Name, etc.
#   ✓ Created configuration: .env
#
# Verify auto-generated password was saved:
cat ~/.hashed/identity_password    # Should show 64-char hex string
ls -la ~/.hashed/identity_password # Should show -rw------- (0600)
#
# Verify .pem is encrypted:
file ./secrets/qa_agent_key.pem    # Should say "PEM certificate"
ls -la ./secrets/qa_agent_key.pem  # Should show -rw------- (0600)
```

**✅ Pass if:** No password prompt shown, `~/.hashed/identity_password` exists with 0600 perms.

---

## Step 6 — Policy Commands

```bash
# Add policies
hashed policy add send_email --allow
hashed policy add delete_database --deny
hashed policy add process_payment --allow --max-amount 500

# List policies
hashed policy list
# Expected: table showing 3 policies

# Test policy evaluation
hashed policy test process_payment --amount 200
# Expected: ✓ ALLOWED - $200 ≤ $500

hashed policy test process_payment --amount 600
# Expected: ✗ DENIED - Amount $600 exceeds max $500

hashed policy test delete_database
# Expected: ✗ DENIED
```

**✅ Pass if:** policies created, list and test work correctly.

---

## Step 7 — Python SDK Import

```python
# Create test_import.py
cat > test_import.py << 'EOF'
from hashed import HashedCore, HashedConfig, __version__
from hashed.identity_store import (
    load_or_create_identity,
    get_or_create_identity_password,
    generate_secure_password,
)

print(f"✓ hashed-sdk {__version__} imported successfully")

# Test auto-password (should NOT prompt)
pwd = get_or_create_identity_password()
assert len(pwd) == 64, f"Expected 64-char hex, got {len(pwd)}"
print(f"✓ get_or_create_identity_password() returned {len(pwd)}-char password")

# Test identity creation
identity = load_or_create_identity("./secrets/qa_agent_key.pem", pwd)
assert len(identity.public_key_hex) == 64, "Public key should be 64 hex chars"
print(f"✓ Identity loaded. Public key: {identity.public_key_hex[:16]}...")

# Test signing
sig = identity.sign_message("test-message")
assert len(sig) > 0
print(f"✓ Signing works. Signature: {sig.hex()[:16]}...")

print("\n🎉 All SDK checks PASSED")
EOF

python3 test_import.py
```

**✅ Pass if:** all assertions pass, no errors.

---

## Step 8 — HASHED_IDENTITY_PASSWORD Override

```bash
# Test that env var override works
HASHED_IDENTITY_PASSWORD="my-custom-password-abc123" python3 -c "
from hashed.identity_store import get_or_create_identity_password
pwd = get_or_create_identity_password()
assert pwd == 'my-custom-password-abc123', f'Got: {pwd}'
print('✓ Env var override works correctly')
"
```

**✅ Pass if:** prints the override message without error.

---

## Step 9 — Dashboard Coming Soon (Vercel)

```bash
# Check that the coming-soon redirect works in production
curl -I https://hashed-dashboard.vercel.app/
# Expected (when MAINTENANCE_MODE=true in Vercel):
#   HTTP/2 307 (or 308) → Location: .../coming-soon
#   OR HTTP/2 200 with body containing "Early Access"

# Direct coming-soon page
curl -s https://hashed-dashboard.vercel.app/coming-soon | grep -o "Early Access"
# Expected: Early Access
```

**✅ Pass if:** public visitors see the coming-soon page.

---

## Step 10 — Logout & Clean

```bash
hashed logout
# Expected: ✓ Logged out. Credentials removed.

hashed whoami
# Expected: ✗ Not logged in. Run: hashed login

# Clean up test dir
cd /tmp && rm -rf hashed-qa-test
```

**✅ Pass if:** credentials cleared cleanly.

---

## 🏁 QA Sign-off Checklist

```
[ ] Step 1: pip install + version check        ✅
[ ] Step 2: CLI commands work                  ✅
[ ] Step 3: hashed signup works end-to-end     ✅
[ ] Step 4: hashed whoami shows credentials    ✅
[ ] Step 5: hashed init (no password prompt)   ✅
[ ] Step 6: policy add/list/test work          ✅
[ ] Step 7: Python SDK import + assertions     ✅
[ ] Step 8: HASHED_IDENTITY_PASSWORD override  ✅
[ ] Step 9: Dashboard shows coming-soon        ✅
[ ] Step 10: logout & cleanup                  ✅
```

All ✅ → **Ready for GitHub Release + announcement** 🚀

---

## 🐛 Known Acceptable Behaviors

- `hashed init` writes `HASHED_IDENTITY_PASSWORD=<64-char-hex>` to `.env` — this is intentional for transparency
- First time `get_or_create_identity_password()` is called, it logs an INFO message about auto-generation
- If `~/.hashed/identity_password` already exists (from previous test), it reuses it — correct behavior

---

## 🚨 If Something Fails

1. Check backend health: `curl https://iamandagent-production.up.railway.app/health`
2. Check PyPI has latest version: `pip index versions hashed-sdk`
3. Force reinstall: `pip install --force-reinstall hashed-sdk==0.2.1`
4. Check GitHub Actions: `https://github.com/Josoriop9/IAMandagent/actions`
