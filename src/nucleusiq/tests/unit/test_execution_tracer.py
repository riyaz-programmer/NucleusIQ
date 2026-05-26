"""Unit tests for execution_tracer helpers and tracer implementations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from nucleusiq.agents.agent_result import (  # noqa: E402
    LLMCallRecord,
    PluginEvent,
    ValidationRecord,
)
from nucleusiq.agents.chat_models import ToolCallRequest  # noqa: E402
from nucleusiq.agents.observability import (  # noqa: E402
    DefaultExecutionTracer,
    NoOpTracer,
    build_llm_call_record,
    build_llm_call_record_from_stream,
    build_server_tool_call_records,
    build_tool_call_record,
)
from nucleusiq.agents.observability._response_parser import (  # noqa: E402
    extract_tool_calls,
)


class _Msg:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _Choice:
    def __init__(self, message):
        self.message = message


class _Resp:
    def __init__(self, choices, usage=None, model=None):
        self.choices = choices
        self.usage = usage
        self.model = model


def test_safe_int_via_build_llm_call_record():
    usage = {"prompt_tokens": "10", "completion_tokens": None, "total_tokens": "bad"}
    r = _Resp([_Choice(_Msg(content="hi"))], usage=usage, model="m1")
    rec = build_llm_call_record(
        r, call_round=1, purpose="main", duration_ms=5.0, model="override"
    )
    assert rec.model == "override"
    assert rec.prompt_tokens == 10
    assert rec.completion_tokens == 0
    assert rec.total_tokens == 10


def test_extract_tool_calls_openai_style():
    tc = {
        "id": "1",
        "type": "function",
        "function": {"name": "add", "arguments": '{"a": 1}'},
    }
    r = _Resp([_Choice(_Msg(content=None, tool_calls=[tc]))])
    raw = extract_tool_calls(r)
    assert len(raw) == 1
    assert raw[0]["function"]["name"] == "add"


def test_extract_tool_calls_function_call_legacy():
    r = _Resp(
        [
            _Choice(
                _Msg(
                    content=None,
                    function_call={"name": "legacy", "arguments": "{}"},
                )
            )
        ]
    )
    raw = extract_tool_calls(r)
    assert len(raw) == 1
    assert raw[0]["function"]["name"] == "legacy"


def test_extract_tool_calls_gemini_parts():
    r = _Resp(
        [
            _Choice(
                _Msg(
                    content=[
                        {
                            "function_call": {
                                "name": "fn",
                                "args": {"x": 1},
                                "id": "g1",
                            }
                        }
                    ]
                )
            )
        ]
    )
    raw = extract_tool_calls(r)
    assert len(raw) == 1
    assert raw[0]["function"]["name"] == "fn"
    assert json.loads(raw[0]["function"]["arguments"]) == {"x": 1}


def test_build_llm_call_record_from_stream():
    meta = {
        "tool_calls": [{"id": "a"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    rec = build_llm_call_record_from_stream(
        meta, call_round=2, purpose="tool_loop", duration_ms=9.0, model="stream-m"
    )
    assert rec.round == 2
    assert rec.purpose == "tool_loop"
    assert rec.tool_call_count == 1
    assert rec.has_tool_calls is True
    assert rec.duration_ms == 9.0
    assert rec.model == "stream-m"


def test_build_tool_call_record_parses_args():
    tc = ToolCallRequest(id="x", name="t", arguments='{"k": "v"}')
    rec = build_tool_call_record(tc, success=True, duration_ms=1.0, round=3)
    assert rec.args == {"k": "v"}
    assert rec.round == 3
    assert rec.source is None  # backwards-compatible default


def test_build_tool_call_record_accepts_source():
    tc = ToolCallRequest(id="x", name="t", arguments="{}")
    rec = build_tool_call_record(
        tc,
        success=True,
        duration_ms=1.0,
        source="mcp://server=github (path=A)",
    )
    assert rec.source == "mcp://server=github (path=A)"


def test_default_tracer_and_reset():
    t = DefaultExecutionTracer()
    tc = ToolCallRequest(name="n", arguments="{}")
    t.record_tool_call(build_tool_call_record(tc, success=True, duration_ms=1.0))
    t.record_llm_call(
        LLMCallRecord(
            round=1,
            purpose="main",
            duration_ms=2.0,
        )
    )
    t.record_warning("w")
    t.record_plugin_event(
        PluginEvent(plugin_name="p", hook="h", action="executed", duration_ms=0.0)
    )
    t.record_validation(
        ValidationRecord(attempt=1, valid=True, layer="critic", reason="ok")
    )
    t.set_autonomous_detail(foo=1)
    assert len(t.tool_calls) == 1
    assert len(t.llm_calls) == 1
    assert t.warnings == ("w",)
    assert len(t.plugin_events) == 1
    assert len(t.validations) == 1
    assert t.autonomous_detail == {"foo": 1}
    t.reset()
    assert t.tool_calls == ()
    assert t.autonomous_detail is None


def test_noop_tracer():
    n = NoOpTracer()
    tc = ToolCallRequest(name="n", arguments="{}")
    n.record_tool_call(build_tool_call_record(tc, success=True, duration_ms=1.0))
    assert n.tool_calls == ()
    assert n.llm_calls == ()


# ------------------------------------------------------------------ #
# v0.7.12 enrichment — executed_by, request_id, cache tokens, ...     #
# ------------------------------------------------------------------ #


def test_tool_call_record_executed_by_default_local():
    tc = ToolCallRequest(id="x", name="local_tool", arguments="{}")
    rec = build_tool_call_record(tc, success=True, duration_ms=1.0)
    assert rec.executed_by == "local"


def test_tool_call_record_executed_by_provider():
    tc = ToolCallRequest(id="x", name="web_search", arguments="{}")
    rec = build_tool_call_record(
        tc, success=True, duration_ms=2.0, executed_by="provider"
    )
    assert rec.executed_by == "provider"


def test_tool_call_record_executed_by_unknown_coerced_to_local():
    """Unknown values must not raise (defensive cast at the builder)."""
    tc = ToolCallRequest(id="x", name="t", arguments="{}")
    rec = build_tool_call_record(
        tc, success=True, duration_ms=1.0, executed_by="hosted"
    )
    assert rec.executed_by == "local"


def test_llm_call_record_defaults_for_new_fields():
    rec = LLMCallRecord(round=1, purpose="main")
    assert rec.provider is None
    assert rec.request_id is None
    assert rec.organization_id is None
    assert rec.stop_reason is None
    assert rec.cache_read_input_tokens == 0
    assert rec.cache_creation_input_tokens == 0
    assert rec.metadata == {}


def test_build_llm_call_record_picks_up_anthropic_cache_tokens():
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cache_read_input_tokens": 7,
        "cache_creation_input_tokens": 3,
    }
    r = _Resp(
        [_Choice(_Msg(content="hi"))],
        usage=usage,
        model="claude-test",
    )
    rec = build_llm_call_record(
        r,
        call_round=1,
        purpose="main",
        provider="anthropic",
        request_id="req_123",
        organization_id="org_abc",
        stop_reason="end_turn",
    )
    assert rec.provider == "anthropic"
    assert rec.request_id == "req_123"
    assert rec.organization_id == "org_abc"
    assert rec.stop_reason == "end_turn"
    assert rec.cache_read_input_tokens == 7
    assert rec.cache_creation_input_tokens == 3


def test_build_llm_call_record_extracts_openai_cached_tokens():
    """OpenAI surfaces caching via ``prompt_tokens_details.cached_tokens``."""
    usage = {
        "prompt_tokens": 20,
        "completion_tokens": 8,
        "prompt_tokens_details": {"cached_tokens": 12},
    }
    r = _Resp([_Choice(_Msg(content="hi"))], usage=usage, model="gpt-test")
    rec = build_llm_call_record(r, call_round=1, purpose="main")
    assert rec.cache_read_input_tokens == 12
    assert rec.cache_creation_input_tokens == 0


def test_build_llm_call_record_auto_extracts_request_id_from_response():
    """When ``request_id`` is not passed explicitly the builder discovers it."""
    r = _Resp([_Choice(_Msg(content="hi"))], usage={}, model="m1")
    r.request_id = "req_auto"
    r.stop_reason = "tool_use"
    rec = build_llm_call_record(r, call_round=1, purpose="main")
    assert rec.request_id == "req_auto"
    assert rec.stop_reason == "tool_use"


def test_build_llm_call_record_from_stream_propagates_observability():
    meta = {
        "tool_calls": [],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "cache_read_input_tokens": 1,
        },
        "request_id": "req_stream",
        "organization_id": "org_xyz",
        "stop_reason": "end_turn",
        "model": "claude-sonnet",
    }
    rec = build_llm_call_record_from_stream(
        meta,
        call_round=3,
        purpose="tool_loop",
        provider="anthropic",
        extra_metadata={"beta_headers": ["prompt-caching-2025"]},
    )
    assert rec.provider == "anthropic"
    assert rec.request_id == "req_stream"
    assert rec.organization_id == "org_xyz"
    assert rec.stop_reason == "end_turn"
    assert rec.cache_read_input_tokens == 1
    assert rec.metadata["beta_headers"] == ["prompt-caching-2025"]


def test_build_llm_call_record_from_stream_handles_none_metadata():
    rec = build_llm_call_record_from_stream(
        None, call_round=1, purpose="main", provider="anthropic"
    )
    assert rec.provider == "anthropic"
    assert rec.request_id is None
    assert rec.metadata == {}


def test_build_server_tool_call_records_empty_inputs():
    assert build_server_tool_call_records(None) == []
    assert build_server_tool_call_records([]) == []


def test_build_server_tool_call_records_from_pydantic_like_objects():
    class _ServerToolCall:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    items = [
        _ServerToolCall(
            id="srv_1",
            name="web_search",
            input={"query": "anthropic"},
            result={"hits": 3},
        ),
        _ServerToolCall(
            id="srv_2", name="code_execution", input={"code": "1+1"}, result=2
        ),
    ]
    records = build_server_tool_call_records(items, round=4)
    assert len(records) == 2
    first, second = records
    assert first.tool_name == "web_search"
    assert first.tool_call_id == "srv_1"
    assert first.args == {"query": "anthropic"}
    assert first.result == {"hits": 3}
    assert first.executed_by == "provider"
    assert first.success is True
    assert first.round == 4
    assert second.tool_name == "code_execution"
    assert second.args == {"code": "1+1"}
    assert second.result == 2
    assert second.executed_by == "provider"


def test_build_server_tool_call_records_from_dicts_and_missing_input():
    items = [
        {"id": "a", "name": "google_search", "input": {"q": "x"}, "result": "ok"},
        {"id": "b", "name": "code_execution"},
    ]
    records = build_server_tool_call_records(items, round=2)
    assert [r.tool_name for r in records] == ["google_search", "code_execution"]
    assert all(r.executed_by == "provider" for r in records)
    assert records[1].args == {}
    assert records[1].result is None
