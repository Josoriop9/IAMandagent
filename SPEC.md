# Hashed Identity Protocol — Technical Specification

**Version:** 1.0  
**Status:** Stable  
**Authors:** Hashed Core Team  

---

## Abstract

This document specifies the Hashed Identity Protocol (HIP), the cryptographic foundation underlying the Hashed SDK. HIP defines how agent identities are derived, how operation payloads are constructed and signed, and how the audit ledger achieves tamper-evidence through a chain of cryptographic signatures.

HIP is designed for **AI agent governance** — environments where the executing entity may be autonomous, long-running, and operating across trust boundaries. The protocol prioritizes: deterministic identity, non-repudiable audit trails, and offline-capable policy enforcement.

---

## 1. Key Derivation and Identity Establishment

### 1.1 Keypair Generation

Each Hashed agent possesses a unique **Ed25519** keypair. Ed25519 was chosen over ECDSA (secp256k1/P-256) for four reasons:

1. **Small key size**: 32-byte private key, 32-byte public key, 64-byte signature
2. **Deterministic signatures**: No random nonce required at signing time — eliminates k-reuse vulnerabilities present in ECDSA
3. **Batch verification**: The backend can verify multiple agent signatures in parallel
4. **RFC 8037 compliance**: Compatible with JOSE/JWK standards for future interoperability

```
Entropy (OS CSPRNG)
       │
       ▼
  Ed25519 keygen  ──────────────────────────────────────────────
       │                                                        │
       ▼                                                        ▼
  private_key (32 bytes)                         public_key (32 bytes)
  └── stored encrypted on disk                  └── registered with backend
      (see §1.2)                                    as agent identity
```

**Implementation:**
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

private_key = Ed25519PrivateKey.generate()
public_key  = private_key.public_key()

# 32-byte raw representation
public_key_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)
agent_id = public_key_bytes.hex()  # 64-char hex string
```

### 1.2 Key Serialization and Encrypted Storage

Private keys are serialized using **PEM + PKCS#8** with symmetric encryption:

```
password  ──── PBKDF2-HMAC-SHA256 ────►  derived_key (32 bytes)
               │ iterations: 480,000     │
               │ salt: 16 bytes CSPRNG   ▼
               │                   AES-256-CBC
               │                        │
               ▼                        ▼
         key_material              ciphertext
                                        │
                                        ▼
                              PEM-encoded PKCS#8 blob
                              ─────────────────────
                              -----BEGIN ENCRYPTED PRIVATE KEY-----
                              MIHjME4GCSqGSIb3DQEFDTBBMCgGCSqGSIb3DQ...
                              -----END ENCRYPTED PRIVATE KEY-----
```

The file is written with `mode=0o600` (owner read/write only). The `secrets/` directory is excluded from version control via `.gitignore`.

**Derivation parameters are intentionally hardcoded** (not configurable) to prevent misconfiguration leading to weak key protection. The 480,000-iteration count targets ~300ms on a 2024 laptop — fast enough for UX, slow enough to resist offline dictionary attacks.

### 1.3 Agent Identity Binding

The agent's **public key hex** (`agent_id`) is the immutable primary identifier:

- Registered with the backend via `POST /v1/agents/register`
- Stored in `~/.hashed/config.json` alongside backend-assigned `agent_uuid`
- Included in every signed payload (see §2)
- Used as the join key in the audit ledger (see §3)

A private key change means a new identity. There is no key rotation at this time — key continuity equals identity continuity.

---

## 2. Operation Signature Payload

### 2.1 Canonical Payload Structure

Every guarded operation produces a **deterministic, canonical JSON payload** before signing. Canonical form eliminates ambiguity in serialization that would produce different byte sequences (and thus different signatures) for semantically identical data.

```json
{
  "version":    1,
  "agent_id":   "<64-char hex public key>",
  "operation":  "<tool_name>",
  "amount":     <float | null>,
  "timestamp":  <unix_timestamp_nanoseconds>,
  "nonce":      "<16-byte hex CSPRNG>",
  "status":     "pending | allowed | denied | error",
  "context":    {
    "public_key": "<agent_id>",
    "args":       [],
    "kwargs":     {}
  }
}
```

**Field semantics:**

| Field | Type | Purpose |
|-------|------|---------|
| `version` | `int` | Protocol version for forward compatibility |
| `agent_id` | `str` | Agent's 64-char hex public key — immutable identity anchor |
| `operation` | `str` | Tool name as registered in the PolicyEngine |
| `amount` | `float\|null` | Numeric amount for rate-limited operations (e.g. financial, email count) |
| `timestamp` | `int` | Unix nanoseconds — nanosecond precision prevents timestamp collision under high-frequency operation |
| `nonce` | `str` | 16-byte random hex — ensures two identical operations at the same nanosecond produce distinct payloads, defeating replay attacks |
| `status` | `str` | Operation outcome; `pending` for pre-execution guard checks |
| `context` | `object` | Sanitized execution context (no secrets, no PII) |

### 2.2 Canonicalization Algorithm

Before signing, the payload is serialized with:

```python
import json

canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
canonical_bytes = canonical.encode("utf-8")
```

`sort_keys=True` guarantees key-alphabetical ordering regardless of insertion order. `separators=(",", ":")` removes all optional whitespace. `ensure_ascii=True` ensures cross-platform byte identity.

### 2.3 Signature Production

```python
signature_bytes = private_key.sign(canonical_bytes)
signature_hex   = signature_bytes.hex()  # 128-char hex string (64 bytes)
```

Ed25519 `sign()` is deterministic: the same `private_key` + `canonical_bytes` always produces the same `signature_hex`. This allows idempotent retry of failed log submissions.

### 2.4 Signature Verification (Backend)

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(agent_id))

try:
    public_key.verify(
        bytes.fromhex(signature_hex),
        canonical_bytes
    )
    # Signature valid — operation authentically originated from agent
except InvalidSignature:
    # Payload was tampered with or signature is forged
    pass
```

The backend verifies every `POST /v1/logs/batch` submission. Log entries failing verification are **rejected, not silently accepted** — integrity over availability for audit data.

---

## 3. Ledger Immutability Architecture

### 3.1 Threat Model

The audit ledger must resist:

1. **Retroactive insertion** — adding a fake log entry for an operation that never happened
2. **Retroactive deletion** — removing evidence of a denied or failed operation
3. **Retroactive modification** — changing amounts, timestamps, or operation names
4. **Replay attacks** — submitting the same valid log entry twice to inflate counts

### 3.2 Entry Structure and Chaining

Each log entry is an independent signed tuple:

```
LogEntry {
  id:            UUID (backend-assigned)
  agent_id:      hex(public_key)
  operation:     string
  status:        "allowed" | "denied" | "error"
  amount:        float | null
  timestamp_ns:  int64
  nonce:         hex(16 bytes)
  payload_hash:  hex(SHA-256(canonical_payload))
  signature:     hex(Ed25519Sign(canonical_payload))
  prev_hash:     hex(SHA-256(prev_entry.signature)) | "genesis"
}
```

The `prev_hash` field implements a **forward-linked hash chain**:

```
[Entry 0]           [Entry 1]             [Entry 2]
signature_0  ──►  prev_hash="h(sig_0)"   prev_hash="h(sig_1)"
                  signature_1        ──► signature_2
                  payload_hash_1         payload_hash_2
```

**Tampering detection:** If entry N is modified, `SHA-256(entry_N.signature)` changes, invalidating `entry_{N+1}.prev_hash`, which cascades forward. An auditor can verify the chain in `O(n)` by recomputing hashes from genesis.

### 3.3 Replay Protection

The `nonce` (16-byte CSPRNG) in each payload is stored alongside the log entry. The backend maintains a **nonce index** per `(agent_id, nonce)`. A duplicate `(agent_id, nonce)` submission returns `HTTP 409 Conflict` — the entry is rejected without creating a duplicate.

Nonces are never reused because they are generated at operation time from `/dev/urandom` (via Python's `os.urandom(16)`), not from a counter.

### 3.4 Buffered Ledger and Durability

The `AsyncLedger` batches entries in an in-memory buffer and flushes via `POST /v1/logs/batch`:

```
Agent process
  │
  ├── operation() called
  │     └── LogEntry appended to buffer (in-memory)
  │
  ├── (buffer reaches MAX_BUFFER or FLUSH_INTERVAL elapses)
  │     └── HTTP POST /v1/logs/batch  ──►  Backend
  │                                         └── DB INSERT (atomic)
  │
  └── shutdown()
        └── Final flush before process exit
```

**Current durability guarantee:** Best-effort. If the process is killed between operation and flush, buffered entries are lost. The `payload_hash` and `nonce` design ensures that if the same operation is safely retried (idempotent tools), the duplicate log entry will be rejected by nonce-uniqueness constraints.

**Planned (v0.4):** WAL (Write-Ahead Log) on local disk — entries are persisted to disk before returning from `guard()`, then marked as flushed after successful backend ACK.

---

## 4. Circuit Breaker Protocol

### 4.1 State Machine

The `_CircuitBreaker` class implements a three-state FSM protecting the backend governance channel:

```
          record_failure()               record_success()
CLOSED ─────────────────────► OPEN ◄───────────────────── HALF-OPEN
  ▲         (≥ threshold)       │                               ▲
  │                             │   cooldown elapsed            │
  └─────────────────────────────┘ ──────────────────────────────┘
       record_success()                  (auto-transition)
```

| State | Description | Backend calls |
|-------|-------------|---------------|
| `CLOSED` | Normal operation | Allowed |
| `OPEN` | Backend is failing; block calls | Blocked |
| `HALF-OPEN` | Cooldown elapsed; probe allowed | One probe allowed |

### 4.2 Failure Counting

```python
_failure_threshold: int   = 3      # consecutive failures to open
_cooldown_s:        float = 60.0   # seconds before HALF-OPEN probe
```

Only **consecutive** failures count. A single success resets the counter to 0 and transitions `OPEN → CLOSED`.

### 4.3 Fail-Open vs Fail-Closed

When the circuit is OPEN, the SDK's behavior depends on `HashedConfig.fail_closed`:

| `fail_closed` | Circuit OPEN behavior |
|--------------|----------------------|
| `False` (default) | Guard passes silently — agent continues operating |
| `True` | `PermissionError` raised — agent operation is denied |

`fail_closed=True` is the correct setting for financial agents, healthcare systems, or any context where **security > availability**. Set via `HASHED_FAIL_CLOSED=true` in the environment.

---

## 5. Protocol Versioning and Forward Compatibility

The `version: 1` field in the payload enables future protocol evolution without breaking existing agents. The backend accepts payloads with `version <= current_max_version`.

Planned version increments:

| Version | Change |
|---------|--------|
| `1` (current) | Ed25519 + canonical JSON + nonce chain |
| `2` (planned) | Add `session_id` for multi-turn agent conversations |
| `3` (planned) | WebAuthn/FIDO2 hardware key support |

---

## Appendix A — Reference Implementation

All protocol components are implemented in:

| Module | Responsibility |
|--------|---------------|
| `src/hashed/identity.py` | Key generation, signing, verification |
| `src/hashed/identity_store.py` | Encrypted PEM serialization/deserialization |
| `src/hashed/core.py` | Payload construction, circuit breaker, ledger dispatch |
| `src/hashed/ledger.py` | AsyncLedger buffer and batch flush |
| `src/hashed/guard.py` | PolicyEngine, `@guard` decorator |

## Appendix B — Security Contact

Report vulnerabilities to: [SECURITY.md](SECURITY.md)

PGP key and responsible disclosure timeline are documented there.

---

*This specification is maintained alongside the SDK source code. PRs that change protocol behavior must update this document.*
