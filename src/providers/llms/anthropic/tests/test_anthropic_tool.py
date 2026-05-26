"""Tests for ``AnthropicTool`` factory + native-tool wire integration (Phase B / 0.2.0)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nucleusiq_anthropic.llm_params import AnthropicLLMParams
from nucleusiq_anthropic.nb_anthropic.base import BaseAnthropic
from nucleusiq_anthropic.nb_anthropic.messages import (
    build_create_kwargs,
    normalize_message_response,
)
from nucleusiq_anthropic.tools import (
    NATIVE_TOOL_BETA_HEADERS,
    NATIVE_TOOL_TYPES,
    NATIVE_TOOL_WIRE_TYPES,
    AnthropicTool,
    is_native_marker,
    marker_to_wire,
    native_name,
    required_beta_headers,
)

# ------------------------------------------------------------------ #
# Factory                                                              #
# ------------------------------------------------------------------ #


class TestAnthropicToolFactory:
    def test_native_registry_membership(self) -> None:
        assert (
            frozenset({"web_search", "web_fetch", "code_execution"})
            == NATIVE_TOOL_TYPES
        )
        assert AnthropicTool.NATIVE_TOOL_TYPES == NATIVE_TOOL_TYPES

    def test_wire_types_map_covers_every_native_tool(self) -> None:
        assert set(NATIVE_TOOL_WIRE_TYPES) == NATIVE_TOOL_TYPES

    def test_beta_headers_only_for_beta_tools(self) -> None:
        # web_search is GA → no beta header; web_fetch + code_execution → beta required.
        assert NATIVE_TOOL_BETA_HEADERS["web_search"] is None
        assert NATIVE_TOOL_BETA_HEADERS["web_fetch"] == "web-fetch-2025-09-10"
        assert NATIVE_TOOL_BETA_HEADERS["code_execution"] == "code-execution-2025-05-22"

    def test_web_search_no_args(self) -> None:
        spec = AnthropicTool.web_search()
        assert is_native_marker(spec)
        assert native_name(spec) == "web_search"
        assert spec["params"] == {}

    def test_web_search_with_filters_and_location(self) -> None:
        spec = AnthropicTool.web_search(
            max_uses=3,
            allowed_domains=["example.com"],
            user_location={"country": "US"},
        )
        assert spec["params"]["max_uses"] == 3
        assert spec["params"]["allowed_domains"] == ["example.com"]
        assert spec["params"]["user_location"] == {"country": "US"}

    def test_web_search_mutually_exclusive_filters(self) -> None:
        with pytest.raises(ValueError):
            AnthropicTool.web_search(
                allowed_domains=["a.com"], blocked_domains=["b.com"]
            )

    def test_web_fetch_citations_bool_normalised(self) -> None:
        spec = AnthropicTool.web_fetch(citations=True, max_content_tokens=4000)
        assert spec["params"]["citations"] == {"enabled": True}
        assert spec["params"]["max_content_tokens"] == 4000

    def test_web_fetch_citations_dict_passthrough(self) -> None:
        spec = AnthropicTool.web_fetch(citations={"enabled": False, "extra": 1})
        assert spec["params"]["citations"] == {"enabled": False, "extra": 1}

    def test_web_fetch_mutually_exclusive_filters(self) -> None:
        with pytest.raises(ValueError):
            AnthropicTool.web_fetch(
                allowed_domains=["a.com"], blocked_domains=["b.com"]
            )

    def test_code_execution_simple_marker(self) -> None:
        spec = AnthropicTool.code_execution()
        assert is_native_marker(spec)
        assert spec["name"] == "code_execution"
        assert spec["params"] == {}


# ------------------------------------------------------------------ #
# Marker → wire conversion                                             #
# ------------------------------------------------------------------ #


class TestMarkerToWire:
    def test_marker_unwraps_to_dated_type(self) -> None:
        wire = marker_to_wire(AnthropicTool.web_search(max_uses=2))
        assert wire["type"] == NATIVE_TOOL_WIRE_TYPES["web_search"]
        assert wire["name"] == "web_search"
        assert wire["max_uses"] == 2

    def test_non_marker_returned_as_copy(self) -> None:
        original = {"type": "function", "name": "x"}
        copy = marker_to_wire(original)
        assert copy == original
        assert copy is not original  # defensive copy

    def test_marker_with_unknown_name_returned_unchanged(self) -> None:
        """Unknown ``name`` on a builtin marker → ``is_native_marker`` rejects it,
        and ``marker_to_wire`` returns the raw dict so Anthropic surfaces the
        error to the caller (rather than NucleusIQ silently mutating it)."""
        spec = {"type": "anthropic_builtin", "name": "made_up", "params": {"k": "v"}}
        out = marker_to_wire(spec)
        assert out == spec
        assert out is not spec  # defensive copy

    def test_native_name_only_for_known_markers(self) -> None:
        assert native_name(AnthropicTool.web_fetch()) == "web_fetch"
        assert native_name({"type": "function"}) is None


# ------------------------------------------------------------------ #
# Beta-header collection                                               #
# ------------------------------------------------------------------ #


class TestRequiredBetaHeaders:
    def test_empty_list(self) -> None:
        assert required_beta_headers(None) == []
        assert required_beta_headers([]) == []

    def test_skips_non_dict_entries(self) -> None:
        assert required_beta_headers(["not_a_dict"]) == []  # type: ignore[list-item]

    def test_web_search_alone_has_no_beta(self) -> None:
        assert required_beta_headers([AnthropicTool.web_search()]) == []

    def test_web_fetch_emits_its_beta(self) -> None:
        assert required_beta_headers([AnthropicTool.web_fetch()]) == [
            "web-fetch-2025-09-10"
        ]

    def test_multiple_native_tools_de_duplicate(self) -> None:
        out = required_beta_headers(
            [
                AnthropicTool.web_fetch(),
                AnthropicTool.code_execution(),
                AnthropicTool.web_search(),
            ]
        )
        # Order preserved (insertion order), no duplicates.
        assert out == ["web-fetch-2025-09-10", "code-execution-2025-05-22"]


# ------------------------------------------------------------------ #
# build_create_kwargs — wire integration                               #
# ------------------------------------------------------------------ #


def _minimal_messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "hi"}]


class TestBuildCreateKwargs:
    def test_native_tool_emits_dated_type_and_beta_header(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=[AnthropicTool.web_fetch()],
            tool_choice=None,
            merged_extras={},
            extra_headers=None,
        )
        tools = kw["tools"]
        assert len(tools) == 1
        assert tools[0]["type"] == NATIVE_TOOL_WIRE_TYPES["web_fetch"]
        # Auto-collected beta header surfaced on extra_headers.
        assert kw["extra_headers"]["anthropic-beta"] == "web-fetch-2025-09-10"

    def test_native_tool_beta_merges_with_user_beta(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=[AnthropicTool.code_execution()],
            tool_choice=None,
            merged_extras={"anthropic_beta": "user-beta-2025-01"},
            extra_headers=None,
        )
        beta = kw["extra_headers"]["anthropic-beta"].split(",")
        assert "user-beta-2025-01" in beta
        assert "code-execution-2025-05-22" in beta

    def test_cache_tools_attaches_cache_control(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "calc",
                        "description": "Compute",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            tool_choice=None,
            merged_extras={"_cache_tools": True},
            extra_headers=None,
        )
        # Last tool gets the cache_control breakpoint.
        assert kw["tools"][-1]["cache_control"] == {"type": "ephemeral"}

    def test_cache_system_emits_block_list(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=[
                {"role": "system", "content": "You are precise."},
                {"role": "user", "content": "hi"},
            ],
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=None,
            tool_choice=None,
            merged_extras={"_cache_system": True},
            extra_headers=None,
        )
        # When cache_system is on, ``system`` is upgraded from string → block list.
        assert isinstance(kw["system"], list)
        assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_strict_tools_marks_custom_only(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "calc",
                        "description": "Compute",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                AnthropicTool.web_search(),
            ],
            tool_choice=None,
            merged_extras={"_strict_tools": True},
            extra_headers=None,
        )
        # Custom tool flagged with strict=True; native tool unchanged.
        custom = next(t for t in kw["tools"] if t.get("name") == "calc")
        native = next(t for t in kw["tools"] if t.get("name") == "web_search")
        assert custom.get("strict") is True
        assert "strict" not in native

    def test_disable_parallel_tool_use_decorates_tool_choice(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=None,
            tool_choice="auto",
            merged_extras={"_disable_parallel_tool_use": True},
            extra_headers=None,
        )
        assert kw["tool_choice"]["disable_parallel_tool_use"] is True

    def test_phase_b_markers_not_passed_through_to_create(self) -> None:
        kw = build_create_kwargs(
            model="claude-test",
            framework_messages=_minimal_messages(),
            max_output_tokens=100,
            temperature=None,
            top_p=None,
            stop=None,
            tools=None,
            tool_choice=None,
            merged_extras={
                "_cache_tools": True,
                "_cache_system": True,
                "_strict_tools": True,
                "_disable_parallel_tool_use": True,
            },
            extra_headers=None,
        )
        # None of the private markers leak into the SDK call.
        for marker in (
            "_cache_tools",
            "_cache_system",
            "_strict_tools",
            "_disable_parallel_tool_use",
        ):
            assert marker not in kw


# ------------------------------------------------------------------ #
# normalize_message_response — server tool splitting                   #
# ------------------------------------------------------------------ #


class TestNormalizeServerTools:
    def _block(self, **kw):
        return SimpleNamespace(**kw)

    def test_server_tool_use_lands_on_server_tool_calls(self) -> None:
        raw = SimpleNamespace(
            content=[
                self._block(type="text", text="searching..."),
                self._block(
                    type="tool_use",
                    id="srv-1",
                    name="web_search",
                    input={"query": "python"},
                ),
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=3,
                cache_creation_input_tokens=1,
            ),
            model="claude-test",
            id="msg_abc",
            stop_reason="tool_use",
        )
        resp = normalize_message_response(raw)
        # Client tool list is empty …
        assert resp.choices[0].message.tool_calls is None
        # … but the server tool was captured for observability.
        assert len(resp.server_tool_calls) == 1
        assert resp.server_tool_calls[0].name == "web_search"
        assert resp.server_tool_calls[0].input == {"query": "python"}

    def test_client_tool_use_still_on_message_tool_calls(self) -> None:
        raw = SimpleNamespace(
            content=[
                self._block(
                    type="tool_use",
                    id="cli-1",
                    name="lookup_order",
                    input={"order_id": "X"},
                ),
            ],
            usage=None,
            model="claude-test",
            id="msg_xyz",
            stop_reason="tool_use",
        )
        resp = normalize_message_response(raw)
        assert resp.choices[0].message.tool_calls is not None
        assert resp.choices[0].message.tool_calls[0].function.name == "lookup_order"
        assert resp.server_tool_calls == []

    def test_usage_breakdown_surfaced(self) -> None:
        raw = SimpleNamespace(
            content=[self._block(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=2,
                cache_creation_input_tokens=4,
            ),
            model="claude-test",
            id="m1",
            stop_reason="end_turn",
        )
        resp = normalize_message_response(raw)
        assert resp.usage is not None
        assert resp.usage.cache_read_input_tokens == 2
        assert resp.usage.cache_creation_input_tokens == 4
        # Aggregate kept for backwards-compat consumers.
        assert resp.usage.cached_tokens == 2
        assert resp.stop_reason == "end_turn"
        assert resp.request_id == "m1"

    def test_server_tool_result_attached_to_matching_call(self) -> None:
        raw = SimpleNamespace(
            content=[
                self._block(
                    type="tool_use",
                    id="srv-1",
                    name="web_fetch",
                    input={"url": "https://example.com"},
                ),
                self._block(
                    type="tool_result",
                    tool_use_id="srv-1",
                    content="fetched body",
                ),
            ],
            usage=None,
            model="claude-test",
            id="m2",
            stop_reason="end_turn",
        )
        resp = normalize_message_response(raw)
        assert len(resp.server_tool_calls) == 1
        assert resp.server_tool_calls[0].result == "fetched body"

    def test_orphan_tool_result_silently_ignored(self) -> None:
        raw = SimpleNamespace(
            content=[
                self._block(
                    type="tool_result", tool_use_id="missing", content="orphan"
                ),
            ],
            usage=None,
            model="claude-test",
            id="m3",
            stop_reason="end_turn",
        )
        resp = normalize_message_response(raw)
        assert resp.server_tool_calls == []
        assert resp.choices[0].message.tool_calls is None


# ------------------------------------------------------------------ #
# AnthropicLLMParams Phase B fields                                    #
# ------------------------------------------------------------------ #


class TestAnthropicLLMParamsPhaseB:
    def test_thinking_effort_low(self) -> None:
        p = AnthropicLLMParams(thinking="low")
        kw = p.to_call_kwargs()
        assert kw["thinking"]["type"] == "enabled"
        assert kw["thinking"]["budget_tokens"] == 2_000

    def test_thinking_dict_passthrough(self) -> None:
        p = AnthropicLLMParams(thinking={"budget_tokens": 12_345})
        kw = p.to_call_kwargs()
        # Dict path preserves user keys + adds default ``type`` when missing.
        assert kw["thinking"]["budget_tokens"] == 12_345
        assert kw["thinking"]["type"] == "enabled"

    def test_thinking_true_alias_medium(self) -> None:
        p = AnthropicLLMParams(thinking=True)
        kw = p.to_call_kwargs()
        assert kw["thinking"]["budget_tokens"] == 8_000

    def test_thinking_false_omitted(self) -> None:
        p = AnthropicLLMParams(thinking=False)
        kw = p.to_call_kwargs()
        assert "thinking" not in kw

    def test_thinking_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            AnthropicLLMParams(thinking="ultra")._resolved_thinking()

    def test_thinking_invalid_type_raises(self) -> None:
        with pytest.raises(TypeError):
            AnthropicLLMParams(thinking=42)._resolved_thinking()  # type: ignore[arg-type]

    def test_cache_and_strict_markers_emitted_as_private_keys(self) -> None:
        p = AnthropicLLMParams(
            cache_tools=True,
            cache_system=True,
            strict_tools=True,
            disable_parallel_tool_use=True,
        )
        kw = p.to_call_kwargs()
        assert kw["_cache_tools"] is True
        assert kw["_cache_system"] is True
        assert kw["_strict_tools"] is True
        assert kw["_disable_parallel_tool_use"] is True


# ------------------------------------------------------------------ #
# End-to-end: BaseAnthropic.call routes through new wire               #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_base_anthropic_call_with_native_tool_emits_beta_header(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    llm = BaseAnthropic(model_name="claude-test", async_mode=True)

    captured: dict = {}

    async def _spy(**kw):
        captured.update(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="done")],
            usage=SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
            model="claude-test",
            id="msg_xx",
            stop_reason="end_turn",
        )

    llm._client.messages.create = AsyncMock(side_effect=_spy)

    out = await llm.call(
        model="claude-test",
        messages=[{"role": "user", "content": "search"}],
        tools=[AnthropicTool.web_fetch(), AnthropicTool.code_execution()],
        max_output_tokens=100,
    )

    assert out.choices[0].message.content == "done"
    # Auto-collected beta header reached the SDK with both tokens.
    beta = captured["extra_headers"]["anthropic-beta"].split(",")
    assert "web-fetch-2025-09-10" in beta
    assert "code-execution-2025-05-22" in beta


@pytest.mark.asyncio
async def test_base_anthropic_phase_b_params_threaded_through(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    llm = BaseAnthropic(
        model_name="claude-test",
        async_mode=True,
        llm_params=AnthropicLLMParams(
            cache_tools=True,
            strict_tools=True,
            thinking="low",
            disable_parallel_tool_use=True,
        ),
    )

    captured: dict = {}

    async def _spy(**kw):
        captured.update(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
            model="claude-test",
            id="msg_yy",
            stop_reason="end_turn",
        )

    llm._client.messages.create = AsyncMock(side_effect=_spy)

    await llm.call(
        model="claude-test",
        messages=[{"role": "user", "content": "x"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "calc",
                    "description": "Compute",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        tool_choice="auto",
        max_output_tokens=100,
    )

    # Cache control on the (only) tool.
    assert captured["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    # Strict-tools flag on the custom function.
    assert captured["tools"][0]["strict"] is True
    # Thinking block.
    assert captured["thinking"]["type"] == "enabled"
    assert captured["thinking"]["budget_tokens"] == 2_000
    # disable_parallel_tool_use threaded into tool_choice.
    assert captured["tool_choice"]["disable_parallel_tool_use"] is True
