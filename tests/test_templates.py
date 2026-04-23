"""
Tests for src/hashed/templates.py

Covers:
 - _build_tool_specs  : policy dict → tool-spec list
 - _default_spec      : fallback spec when no policies exist
 - render_plain       : plain Python agent template
 - render_langchain   : LangChain agent template
 - render_crewai      : CrewAI agent template
 - render_strands     : Amazon Strands agent template
 - render_autogen     : AutoGen agent template
 - render_agent_script: public dispatcher (all 5 frameworks + error case)
"""

import pytest

from hashed.templates import (
    _build_tool_specs,
    _default_spec,
    render_agent_script,
    render_autogen,
    render_crewai,
    render_langchain,
    render_plain,
    render_strands,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

AGENT_POLS: dict = {
    "process_payment": {
        "allowed": True,
        "max_amount": 500.0,
    },
    "send_sms": {
        "allowed": False,
        "max_amount": None,
    },
}

GLOBAL_POLS: dict = {
    "send_email": {
        "allowed": True,
        "max_amount": None,
    },
    "delete_record": {
        "allowed": False,
        "max_amount": None,
    },
}

_RENDER_KWARGS: dict = {
    "name": "TestAgent",
    "agent_type": "finance",
    "identity_file": ".hashed_identity.pem",
    "agent_pols": AGENT_POLS,
    "global_pols": GLOBAL_POLS,
    "interactive": False,
}


# ── _build_tool_specs ─────────────────────────────────────────────────────────


class TestBuildToolSpecs:

    def test_returns_list(self) -> None:
        """_build_tool_specs returns a list."""
        result = _build_tool_specs(AGENT_POLS, GLOBAL_POLS)
        assert isinstance(result, list)

    def test_length_matches_union(self) -> None:
        """All tools from both dicts appear exactly once."""
        result = _build_tool_specs(AGENT_POLS, GLOBAL_POLS)
        names = {s["name"] for s in result}
        expected = set(AGENT_POLS) | set(GLOBAL_POLS)
        assert names == expected

    def test_agent_policy_overrides_global(self) -> None:
        """When a tool appears in both dicts, agent policy takes precedence."""
        overlap_agent = {"shared_tool": {"allowed": False, "max_amount": None}}
        overlap_global = {"shared_tool": {"allowed": True, "max_amount": None}}
        result = _build_tool_specs(overlap_agent, overlap_global)
        spec = next(s for s in result if s["name"] == "shared_tool")
        assert spec["allowed"] is False

    def test_max_amount_sets_float_param_type(self) -> None:
        """A tool with max_amount uses 'float' as param_type."""
        specs = _build_tool_specs(AGENT_POLS, {})
        payment = next(s for s in specs if s["name"] == "process_payment")
        assert payment["param_type"] == "float"
        assert payment["param_name"] == "amount"

    def test_no_max_amount_uses_str_param_type(self) -> None:
        """A tool without max_amount uses 'str' as param_type."""
        specs = _build_tool_specs({}, GLOBAL_POLS)
        email = next(s for s in specs if s["name"] == "send_email")
        assert email["param_type"] == "str"
        assert email["param_name"] == "data"

    def test_empty_dicts_returns_empty_list(self) -> None:
        """No policies → empty list."""
        assert _build_tool_specs({}, {}) == []

    def test_denied_tool_status_label(self) -> None:
        """Denied tools have 'DENIED by policy' in their status."""
        specs = _build_tool_specs(
            {}, {"block_all": {"allowed": False, "max_amount": None}}
        )
        spec = specs[0]
        assert "DENIED" in spec["status"]

    def test_allowed_tool_status_label(self) -> None:
        """Allowed tools have 'allowed' in their status (case-sensitive)."""
        specs = _build_tool_specs(
            {}, {"allow_op": {"allowed": True, "max_amount": None}}
        )
        spec = specs[0]
        assert spec["status"] == "allowed"


# ── _default_spec ─────────────────────────────────────────────────────────────


class TestDefaultSpec:

    def test_returns_list_with_one_item(self) -> None:
        """_default_spec returns exactly one tool spec."""
        result = _default_spec()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_example_operation_name(self) -> None:
        """Default spec uses 'example_operation' as the tool name."""
        result = _default_spec()
        assert result[0]["name"] == "example_operation"

    def test_allowed_is_true(self) -> None:
        """Default spec is allowed (True)."""
        assert _default_spec()[0]["allowed"] is True

    def test_has_required_keys(self) -> None:
        """Default spec contains all required keys."""
        keys = _default_spec()[0].keys()
        for required in (
            "name",
            "allowed",
            "max_amount",
            "scope",
            "param_type",
            "param_name",
        ):
            assert required in keys


# ── render_plain ──────────────────────────────────────────────────────────────


class TestRenderPlain:

    def test_returns_string(self) -> None:
        """render_plain returns a non-empty string."""
        result = render_plain(**_RENDER_KWARGS)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_agent_name(self) -> None:
        """Rendered script embeds the agent name."""
        result = render_plain(**_RENDER_KWARGS)
        assert "TestAgent" in result

    def test_contains_import_hashed(self) -> None:
        """Rendered script imports hashed package."""
        result = render_plain(**_RENDER_KWARGS)
        assert "hashed" in result

    def test_contains_tool_names(self) -> None:
        """Rendered script includes at least one tool name from policies."""
        result = render_plain(**_RENDER_KWARGS)
        tool_names = list(AGENT_POLS.keys()) + list(GLOBAL_POLS.keys())
        assert any(t in result for t in tool_names)

    def test_empty_policies_uses_default_spec(self) -> None:
        """render_plain with empty policies falls back to example_operation."""
        result = render_plain(
            name="Bot",
            agent_type="test",
            identity_file="key.pem",
            agent_pols={},
            global_pols={},
            interactive=False,
        )
        assert "example_operation" in result

    def test_interactive_flag(self) -> None:
        """render_plain accepts interactive=True without raising."""
        result = render_plain(**{**_RENDER_KWARGS, "interactive": True})
        assert isinstance(result, str)
        assert len(result) > 100


# ── render_langchain ──────────────────────────────────────────────────────────


class TestRenderLangchain:

    def test_returns_string(self) -> None:
        result = render_langchain(**_RENDER_KWARGS)
        assert isinstance(result, str) and len(result) > 100

    def test_contains_langchain_imports(self) -> None:
        """LangChain template references langchain."""
        result = render_langchain(**_RENDER_KWARGS)
        assert "langchain" in result.lower()

    def test_contains_agent_name(self) -> None:
        result = render_langchain(**_RENDER_KWARGS)
        assert "TestAgent" in result


# ── render_crewai ─────────────────────────────────────────────────────────────


class TestRenderCrewai:

    def test_returns_string(self) -> None:
        result = render_crewai(**_RENDER_KWARGS)
        assert isinstance(result, str) and len(result) > 100

    def test_contains_crewai_imports(self) -> None:
        """CrewAI template references crewai."""
        result = render_crewai(**_RENDER_KWARGS)
        assert "crewai" in result.lower()

    def test_contains_agent_name(self) -> None:
        result = render_crewai(**_RENDER_KWARGS)
        assert "TestAgent" in result


# ── render_strands ────────────────────────────────────────────────────────────


class TestRenderStrands:

    def test_returns_string(self) -> None:
        result = render_strands(**_RENDER_KWARGS)
        assert isinstance(result, str) and len(result) > 100

    def test_contains_strands_keyword(self) -> None:
        """Strands template references strands."""
        result = render_strands(**_RENDER_KWARGS)
        assert "strands" in result.lower()

    def test_contains_agent_name(self) -> None:
        result = render_strands(**_RENDER_KWARGS)
        assert "TestAgent" in result


# ── render_autogen ────────────────────────────────────────────────────────────


class TestRenderAutogen:

    def test_returns_string(self) -> None:
        result = render_autogen(**_RENDER_KWARGS)
        assert isinstance(result, str) and len(result) > 100

    def test_contains_autogen_keyword(self) -> None:
        """AutoGen template references autogen."""
        result = render_autogen(**_RENDER_KWARGS)
        assert "autogen" in result.lower()

    def test_contains_agent_name(self) -> None:
        result = render_autogen(**_RENDER_KWARGS)
        assert "TestAgent" in result


# ── render_agent_script (dispatcher) ─────────────────────────────────────────


class TestRenderAgentScript:

    @pytest.mark.parametrize(
        "framework", ["plain", "langchain", "crewai", "strands", "autogen"]
    )
    def test_all_frameworks_return_string(self, framework: str) -> None:
        """render_agent_script dispatches correctly for each supported framework."""
        result = render_agent_script(
            framework=framework,
            **_RENDER_KWARGS,
        )
        assert isinstance(result, str)
        assert len(result) > 50

    def test_invalid_framework_raises_value_error(self) -> None:
        """Unsupported framework name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown framework"):
            render_agent_script(
                framework="tensorflow",
                **_RENDER_KWARGS,
            )

    def test_plain_output_matches_render_plain_directly(self) -> None:
        """render_agent_script('plain', ...) equals render_plain(...)."""
        via_dispatcher = render_agent_script(framework="plain", **_RENDER_KWARGS)
        directly = render_plain(**_RENDER_KWARGS)
        assert via_dispatcher == directly
