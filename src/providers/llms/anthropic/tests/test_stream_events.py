"""Streaming adapter unit tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from nucleusiq_anthropic.nb_anthropic.stream_adapter import _process_raw_events


@pytest.mark.asyncio
async def test_process_raw_events_token_and_tool() -> None:

    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(id="mid", model="claude"),
        ),
        SimpleNamespace(
            type="content_block_start",
            index=0,
            content_block=SimpleNamespace(type="text"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="Hi"),
        ),
        SimpleNamespace(
            type="content_block_start",
            index=1,
            content_block=SimpleNamespace(type="tool_use", id="t1", name="fn"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=1,
            delta=SimpleNamespace(type="input_json_delta", partial_json='{"a":'),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=1,
            delta=SimpleNamespace(type="input_json_delta", partial_json="1}"),
        ),
        SimpleNamespace(
            type="message_delta",
            usage=SimpleNamespace(
                input_tokens=2,
                output_tokens=3,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        ),
    ]

    async def gen():

        for e in events:
            yield e

    out = []

    async for ev in _process_raw_events(gen()):
        out.append(ev)

    assert any(e.type == "token" for e in out)

    complete = out[-1]

    assert complete.type == "complete"

    assert complete.content == "Hi"

    assert complete.metadata["tool_calls"][0]["name"] == "fn"


@pytest.mark.asyncio
async def test_process_raw_events_separates_server_tools_and_surfaces_metadata() -> None:
    """0.2.0 — server-side tools land in ``server_tool_calls``; stop_reason +
    cache tokens + request_id are surfaced in the COMPLETE metadata."""

    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(id="msg_42", model="claude-opus-4", usage=None),
        ),
        SimpleNamespace(
            type="content_block_start",
            index=0,
            content_block=SimpleNamespace(type="text"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="searching"),
        ),
        # Server-side tool — should NOT be reported as a client tool call.
        SimpleNamespace(
            type="content_block_start",
            index=1,
            content_block=SimpleNamespace(
                type="tool_use", id="srv-1", name="web_search"
            ),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=1,
            delta=SimpleNamespace(
                type="input_json_delta", partial_json='{"q":"x"}'
            ),
        ),
        # Client-side tool — should remain in tool_calls.
        SimpleNamespace(
            type="content_block_start",
            index=2,
            content_block=SimpleNamespace(
                type="tool_use", id="cli-1", name="lookup_order"
            ),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=2,
            delta=SimpleNamespace(
                type="input_json_delta", partial_json='{"id":1}'
            ),
        ),
        SimpleNamespace(
            type="message_delta",
            delta=SimpleNamespace(stop_reason="tool_use"),
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=4,
                cache_read_input_tokens=3,
                cache_creation_input_tokens=2,
            ),
        ),
    ]

    async def gen():
        for e in events:
            yield e

    out = []
    async for ev in _process_raw_events(gen()):
        out.append(ev)

    complete = out[-1]
    md = complete.metadata

    # Tool routing.
    assert len(md["tool_calls"]) == 1
    assert md["tool_calls"][0]["name"] == "lookup_order"
    assert len(md["server_tool_calls"]) == 1
    assert md["server_tool_calls"][0]["name"] == "web_search"

    # Enriched observability.
    assert md["request_id"] == "msg_42"
    assert md["response_id"] == "msg_42"
    assert md["stop_reason"] == "tool_use"
    assert md["usage"]["cache_read_input_tokens"] == 3
    assert md["usage"]["cache_creation_input_tokens"] == 2


@pytest.mark.asyncio
async def test_process_raw_events_handles_message_start_usage() -> None:
    """Some SDK builds attach a partial ``usage`` on ``message_start``; ensure it survives until message_delta overwrites it."""

    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(
                id="m",
                model="claude",
                usage=SimpleNamespace(
                    input_tokens=1,
                    output_tokens=0,
                    cache_read_input_tokens=0,
                    cache_creation_input_tokens=0,
                ),
            ),
        ),
        SimpleNamespace(
            type="content_block_start",
            index=0,
            content_block=SimpleNamespace(type="text"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="ok"),
        ),
    ]

    async def gen():
        for e in events:
            yield e

    out = []
    async for ev in _process_raw_events(gen()):
        out.append(ev)

    md = out[-1].metadata
    assert md["usage"]["prompt_tokens"] == 1


@pytest.mark.asyncio
async def test_process_raw_events_thinking_delta_event() -> None:
    """Thinking deltas surface as THINKING stream events."""

    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(id="m", model="claude", usage=None),
        ),
        SimpleNamespace(
            type="content_block_start",
            index=0,
            content_block=SimpleNamespace(type="text"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="thinking_delta", thinking="reasoning..."),
        ),
        SimpleNamespace(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="answer"),
        ),
    ]

    async def gen():
        for e in events:
            yield e

    out = []
    async for ev in _process_raw_events(gen()):
        out.append(ev)

    types = [e.type for e in out]
    assert "thinking" in types
    assert "token" in types
    assert out[-1].type == "complete"
