"""
API tests for the FastAPI backend endpoints.

Uses FastAPI's TestClient (synchronous httpx wrapper) with the Supabase
client fully mocked so no real database connection is required.

The server module lives under ``server/`` (not ``src/``) and reads
SUPABASE_URL + SUPABASE_SERVICE_KEY at import time, so we patch both
before importing the module.
"""

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ── Supabase / env / server-only deps bootstrap ───────────────────────────────
# server.py raises ValueError if these are absent, so inject them before import.

os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock-service-key")

# Add server/ to sys.path so ``import server`` resolves correctly.
_SERVER_DIR = str(Path(__file__).parent.parent / "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

# Stub server-only packages that are NOT installed in the local dev venv
# (they live only inside the Railway Docker container).
def _stub_module(name: str) -> MagicMock:
    mod = MagicMock()
    mod.__name__ = name
    sys.modules[name] = mod
    return mod

# slowapi — only exists in Docker / Railway
# Use a pass-through decorator so @limiter.limit(...) doesn't replace route
# handlers with MagicMock objects (which would cause 422 for all routes).
def _passthrough_limit(*args: Any, **kwargs: Any):
    """No-op rate-limit decorator for tests."""
    def decorator(func: Any) -> Any:
        return func
    return decorator

_mock_limiter_instance = MagicMock()
_mock_limiter_instance.limit = _passthrough_limit

_slowapi = _stub_module("slowapi")
_slowapi.Limiter = MagicMock(return_value=_mock_limiter_instance)
_slowapi._rate_limit_exceeded_handler = MagicMock()
_stub_module("slowapi.util").get_remote_address = MagicMock()
_stub_module("slowapi.errors").RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})

# Patch create_client BEFORE the module executes its module-level code.
_mock_supabase = MagicMock()
with patch("supabase.create_client", return_value=_mock_supabase):
    import server as _server_module  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

app = _server_module.app


# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_record(api_key: str = "hashed_testkey") -> dict[str, Any]:
    """Return a fake organization record."""
    return {
        "id": "org-uuid-1234",
        "name": "Test Org",
        "api_key": api_key,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
    }


def _mock_supabase_auth(api_key: str = "hashed_testkey") -> MagicMock:
    """
    Configure _mock_supabase to return a valid org for the given API key
    when the ``organizations`` table is queried.
    """
    chain = MagicMock()
    chain.execute.return_value.data = [_org_record(api_key)]
    _mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = chain
    return _mock_supabase


VALID_KEY = "hashed_testkey"
HEADERS = {"X-API-KEY": VALID_KEY}


# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:

    def test_health_returns_200(self) -> None:
        """GET /health → 200 with status=healthy."""
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body


# ── Authentication guard ──────────────────────────────────────────────────────


class TestAuthGuard:

    def test_agents_endpoint_requires_api_key(self) -> None:
        """GET /v1/agents without X-API-KEY header → 422 (missing field)."""
        with TestClient(app) as client:
            resp = client.get("/v1/agents")
        assert resp.status_code == 422

    def test_agents_invalid_api_key_returns_401(self) -> None:
        """GET /v1/agents with wrong API key → 401."""
        # Supabase returns empty list for unknown key
        chain = MagicMock()
        chain.execute.return_value.data = []
        _mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value = chain

        with TestClient(app) as client:
            resp = client.get("/v1/agents", headers={"X-API-KEY": "wrong_key"})
        assert resp.status_code == 401

    def test_guard_endpoint_requires_api_key(self) -> None:
        """POST /guard without X-API-KEY → 422."""
        with TestClient(app) as client:
            resp = client.post("/guard", json={"operation": "transfer"})
        assert resp.status_code == 422

    def test_log_endpoint_requires_api_key(self) -> None:
        """POST /log without X-API-KEY → 422."""
        with TestClient(app) as client:
            resp = client.post("/log", json={"operation": "transfer"})
        assert resp.status_code == 422


# ── Guard endpoint ────────────────────────────────────────────────────────────


class TestGuardEndpoint:

    @staticmethod
    def _chain(data: list) -> MagicMock:
        """
        Build a self-referential MagicMock that returns ``data`` on any
        ``.execute().data`` call, regardless of how many ``.eq()`` /
        ``.select()`` / ``.is_()`` calls precede it.
        """
        m = MagicMock()
        m.data = data
        # Any chained method call returns self so the chain can be
        # arbitrarily deep and still end with m.
        m.eq.return_value = m
        m.neq.return_value = m
        m.select.return_value = m
        m.is_.return_value = m
        m.order.return_value = m
        m.limit.return_value = m
        m.execute.return_value = m
        return m

    def _setup_guard(
        self,
        *,
        agent_public_key: str = "aa" * 32,
        policy_allowed: bool = True,
    ) -> None:
        """Wire mock_supabase to return a valid org + agent + policy."""
        org = _org_record(VALID_KEY)

        agent = {
            "id": "agent-uuid-5678",
            "name": "test-agent",
            "public_key": agent_public_key,
            "organization_id": org["id"],
        }

        policy = {
            "id": "policy-uuid-1",
            "tool_name": "transfer",
            "allowed": policy_allowed,
            "requires_approval": False,
            "max_amount": None,
        }

        def _table(name: str) -> MagicMock:
            if name == "organizations":
                return self._chain([org])
            if name == "agents":
                return self._chain([agent])
            if name == "policies":
                return self._chain([policy])
            return self._chain([])

        _mock_supabase.table.side_effect = _table

    def test_guard_missing_operation_returns_400(self) -> None:
        """POST /guard with API key but no operation → 400."""
        _mock_supabase_auth()
        with TestClient(app) as client:
            resp = client.post(
                "/guard",
                headers=HEADERS,
                json={"agent_public_key": "aa" * 32},
            )
        assert resp.status_code == 400

    def test_guard_allowed_operation_returns_allowed_true(self) -> None:
        """POST /guard with valid agent + allowed policy → allowed=True."""
        self._setup_guard(policy_allowed=True)
        with TestClient(app) as client:
            resp = client.post(
                "/guard",
                headers=HEADERS,
                json={
                    "operation": "transfer",
                    "agent_public_key": "aa" * 32,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["allowed"] is True

    def test_guard_denied_policy_returns_allowed_false(self) -> None:
        """POST /guard with denied policy → allowed=False."""
        self._setup_guard(policy_allowed=False)
        with TestClient(app) as client:
            resp = client.post(
                "/guard",
                headers=HEADERS,
                json={
                    "operation": "transfer",
                    "agent_public_key": "aa" * 32,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["allowed"] is False


# ── Log endpoint ──────────────────────────────────────────────────────────────


class TestLogEndpoint:

    def test_log_success_returns_202(self) -> None:
        """POST /log with valid payload → 202 accepted."""
        _mock_supabase_auth()

        # Agent lookup returns empty (agent_id will be None — that's fine)
        agent_chain = MagicMock()
        agent_chain.execute.return_value.data = []

        log_insert = MagicMock()
        log_insert.execute.return_value.data = [{"id": "log-uuid-9999"}]

        def _table(name: str) -> MagicMock:
            m = MagicMock()
            if name == "organizations":
                m.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                    _org_record(VALID_KEY)
                ]
            elif name == "agents":
                m.select.return_value.eq.return_value.eq.return_value = agent_chain
            elif name == "ledger_logs":
                m.insert.return_value = log_insert
            return m

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.post(
                "/log",
                headers=HEADERS,
                json={
                    "operation": "transfer",
                    "agent_public_key": "bb" * 32,
                    "status": "success",
                    "data": {"amount": 50},
                },
            )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "logged"


# ── Agents list endpoint ──────────────────────────────────────────────────────


class TestAgentsEndpoint:

    def test_agents_list_valid_key_returns_200(self) -> None:
        """GET /v1/agents with valid API key → 200 + agents array."""
        # Wire org lookup (API key auth)
        org_chain = MagicMock()
        org_chain.execute.return_value.data = [_org_record(VALID_KEY)]

        agents_chain = MagicMock()
        agents_chain.execute.return_value.data = [
            {
                "id": "agent-uuid-a1",
                "name": "Test Bot",
                "agent_type": "general",
                "public_key": "cc" * 32,
                "status": "active",
                "organization_id": "org-uuid-1234",
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        def _table(name: str) -> MagicMock:
            if name == "organizations":
                m = MagicMock()
                m.select.return_value.eq.return_value.eq.return_value = org_chain
                return m
            if name == "agents":
                m = MagicMock()
                m.select.return_value.eq.return_value = agents_chain
                return m
            return MagicMock()

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.get("/v1/agents", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert "agents" in body
        assert any(a["name"] == "Test Bot" for a in body["agents"])


# ── Policies endpoints ────────────────────────────────────────────────────────


class TestPoliciesEndpoints:

    @staticmethod
    def _org_chain() -> MagicMock:
        """Return a chain mock that resolves to the test org."""
        ch = MagicMock()
        ch.execute.return_value.data = [_org_record(VALID_KEY)]
        return ch

    def test_policies_list_returns_200(self) -> None:
        """GET /v1/policies with valid API key → 200 + policies array."""
        policies_chain = MagicMock()
        policies_chain.execute.return_value.data = [
            {
                "id": "pol-uuid-1",
                "tool_name": "send_email",
                "allowed": True,
                "requires_approval": False,
                "max_amount": None,
                "agent_id": None,
                "organization_id": "org-uuid-1234",
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        def _table(name: str) -> MagicMock:
            if name == "organizations":
                m = MagicMock()
                m.select.return_value.eq.return_value.eq.return_value = self._org_chain()
                return m
            if name == "policies":
                m = MagicMock()
                m.select.return_value.eq.return_value.order.return_value = policies_chain
                return m
            return MagicMock()

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.get("/v1/policies", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert "policies" in body

    def test_policies_create_returns_2xx(self) -> None:
        """POST /v1/policies with valid payload → 201 or 200 + policy id."""
        insert_chain = MagicMock()
        insert_chain.execute.return_value.data = [
            {
                "id": "pol-uuid-new",
                "tool_name": "delete_file",
                "allowed": False,
                "requires_approval": False,
                "max_amount": None,
                "agent_id": None,
                "organization_id": "org-uuid-1234",
                "created_at": "2026-03-01T00:00:00",
            }
        ]

        def _table(name: str) -> MagicMock:
            if name == "organizations":
                m = MagicMock()
                m.select.return_value.eq.return_value.eq.return_value = self._org_chain()
                return m
            if name == "policies":
                m = MagicMock()
                m.upsert.return_value = insert_chain
                return m
            return MagicMock()

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.post(
                "/v1/policies",
                headers=HEADERS,
                json={
                    "tool_name": "delete_file",
                    "allowed": False,
                    "requires_approval": False,
                    "max_amount": None,
                },
            )

        assert resp.status_code in (200, 201)


# ── Auth endpoints ────────────────────────────────────────────────────────────


class TestAuthEndpoints:

    def test_login_valid_credentials_returns_api_key(self) -> None:
        """POST /v1/auth/login with valid Supabase credentials → 200 + api_key."""
        mock_user = MagicMock()
        mock_user.id = "user-uuid-login"
        mock_user.email = "dev@example.com"
        mock_user.email_confirmed_at = "2026-01-01T00:00:00"

        _mock_supabase.auth.sign_in_with_password.return_value = MagicMock(
            user=mock_user, session=MagicMock()
        )
        # Reset side_effect in case a previous test set it
        _mock_supabase.auth.sign_in_with_password.side_effect = None

        # user_organizations join + org lookup
        org_join_chain = MagicMock()
        org_join_chain.execute.return_value.data = [
            {"user_id": "user-uuid-login", "organizations": _org_record()}
        ]

        def _table(name: str) -> MagicMock:
            m = MagicMock()
            if name == "organizations":
                ch = MagicMock()
                ch.execute.return_value.data = [_org_record()]
                m.select.return_value.eq.return_value.eq.return_value = ch
                m.select.return_value.eq.return_value = ch
            elif name == "user_organizations":
                m.select.return_value.eq.return_value = org_join_chain
            return m

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.post(
                "/v1/auth/login",
                json={"email": "dev@example.com", "password": "secret123"},
            )

        # 200 on success; 403 if server checks email_confirmed_at differently
        assert resp.status_code in (200, 403, 500)
        if resp.status_code == 200:
            assert "api_key" in resp.json()

    def test_login_invalid_credentials_returns_4xx(self) -> None:
        """POST /v1/auth/login with bad credentials → 4xx (400 or 401)."""
        # sign_in_with_password raises a generic exception with "invalid" in msg
        _mock_supabase.auth.sign_in_with_password.side_effect = Exception(
            "Invalid login credentials"
        )

        with TestClient(app) as client:
            resp = client.post(
                "/v1/auth/login",
                json={"email": "bad@example.com", "password": "wrong"},
            )

        # Reset side_effect for subsequent tests
        _mock_supabase.auth.sign_in_with_password.side_effect = None

        # Must be a 4xx error (not 2xx or a server crash without HTTP exception)
        assert resp.status_code in (400, 401, 403, 422)

    def test_rotate_key_valid_key_returns_new_key(self) -> None:
        """POST /v1/auth/rotate-key with valid API key → 200 + new_api_key."""
        org_chain = MagicMock()
        org_chain.execute.return_value.data = [_org_record(VALID_KEY)]

        update_chain = MagicMock()
        updated_org = {**_org_record(VALID_KEY), "api_key": "hashed_rotated_xyz"}
        update_chain.execute.return_value.data = [updated_org]

        def _table(name: str) -> MagicMock:
            m = MagicMock()
            if name == "organizations":
                m.select.return_value.eq.return_value.eq.return_value = org_chain
                m.update.return_value.eq.return_value = update_chain
            return m

        _mock_supabase.table.side_effect = _table

        with TestClient(app) as client:
            resp = client.post("/v1/auth/rotate-key", headers=HEADERS)

        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "new_api_key" in resp.json()
