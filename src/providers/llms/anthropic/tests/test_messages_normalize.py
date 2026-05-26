"""Response normalisation."""

from __future__ import annotations

from types import SimpleNamespace

from anthropic import NOT_GIVEN

from nucleusiq_anthropic.nb_anthropic.messages import (
    build_create_kwargs,
    normalize_message_response,
)


def test_normalize_text_and_tools() -> None:
    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    resp = tb(
        content=[
            tb(type="text", text="Hey"),
            tb(type="tool_use", id="tid", name="sum", input={"a": 1}),
        ],
        usage=tb(
            input_tokens=3,
            output_tokens=5,
            cache_read_input_tokens=1,
            cache_creation_input_tokens=0,
        ),
        model="claude-haiku",
        id="mid",
    )

    normed = normalize_message_response(resp)

    md = normed.choices[0].message

    assert md.content.strip() == "Hey"

    assert md.tool_calls and md.tool_calls[0].function.name == "sum"

    assert normed.usage

    assert normed.usage.prompt_tokens == 4

    assert normed.response_id == "mid"


def test_normalize_handles_non_mapping_tool_payload() -> None:
    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    blob = tb(type="tool_use", id="", name="n", input=[1, 2])

    resp = tb(
        content=[blob],
        usage=tb(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="m",
        id="i",
    )

    normed = normalize_message_response(resp)
    args = normed.choices[0].message.tool_calls[0].function.arguments
    assert "1" in args


def test_normalize_json_dump_failure(monkeypatch) -> None:
    import nucleusiq_anthropic.nb_anthropic.messages as m

    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    resp = tb(
        content=[tb(type="tool_use", id="z", name="z", input={"p": 1})],
        usage=tb(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="m",
        id="i",
    )

    def _boom(*_a: object, **_kw: object) -> None:
        raise TypeError("forced")

    monkeypatch.setattr(m.json, "dumps", _boom)

    normed = normalize_message_response(resp)

    assert normed.choices[0].message.tool_calls[0].function.arguments == "{}"


def test_normalize_server_tool_use_and_per_tool_result_block() -> None:
    """``server_tool_use`` + ``code_execution_tool_result`` flow surfaces a
    populated :class:`ServerToolCall` with id, name, input and result."""
    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    # Real SDK delivers a Pydantic object with model_dump(); emulate that.
    class _ExecResult:
        def model_dump(self) -> dict:
            return {
                "type": "code_execution_result",
                "stdout": "4\n",
                "stderr": "",
                "return_code": 0,
            }

    result_payload = _ExecResult()

    resp = tb(
        content=[
            tb(
                type="server_tool_use",
                id="srvtoolu_1",
                name="code_execution",
                input={"code": "print(2+2)"},
            ),
            tb(
                type="code_execution_tool_result",
                tool_use_id="srvtoolu_1",
                content=result_payload,
            ),
            tb(type="text", text="The answer is 4."),
        ],
        usage=tb(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="claude-sonnet-4-5",
        id="msg_1",
        stop_reason="end_turn",
    )

    normed = normalize_message_response(resp)
    assert len(normed.server_tool_calls) == 1
    stc = normed.server_tool_calls[0]
    assert stc.id == "srvtoolu_1"
    assert stc.name == "code_execution"
    assert stc.input == {"code": "print(2+2)"}
    assert isinstance(stc.result, dict)
    assert stc.result.get("stdout") == "4\n"
    assert normed.choices[0].message.tool_calls is None
    assert normed.stop_reason == "end_turn"


def test_normalize_web_search_tool_result_with_list_content() -> None:
    """``web_search_tool_result`` carries a list of result-item dicts —
    ``_coerce_tool_result_content`` should preserve list shape."""

    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    items = [
        {"type": "web_search_result", "title": "NucleusIQ", "url": "https://x"},
        {"type": "web_search_result", "title": "Docs", "url": "https://y"},
    ]
    resp = tb(
        content=[
            tb(
                type="server_tool_use",
                id="srvtoolu_2",
                name="web_search",
                input={"query": "NucleusIQ"},
            ),
            tb(
                type="web_search_tool_result",
                tool_use_id="srvtoolu_2",
                content=items,
            ),
        ],
        usage=tb(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="m",
        id="i",
    )

    normed = normalize_message_response(resp)
    assert len(normed.server_tool_calls) == 1
    stc = normed.server_tool_calls[0]
    assert stc.name == "web_search"
    assert isinstance(stc.result, list)
    assert len(stc.result) == 2
    assert stc.result[0]["title"] == "NucleusIQ"


def test_normalize_per_tool_result_with_unknown_tool_use_id_is_ignored() -> None:
    """A ``*_tool_result`` block whose ``tool_use_id`` does not match any
    server tool-use stays silent (no crash, no spurious ServerToolCall)."""

    def tb(**kw: object) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    resp = tb(
        content=[
            tb(
                type="web_search_tool_result",
                tool_use_id="ghost",
                content=[{"type": "x"}],
            ),
            tb(type="text", text="hi"),
        ],
        usage=tb(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="m",
        id="i",
    )

    normed = normalize_message_response(resp)
    assert normed.server_tool_calls == []
    assert normed.choices[0].message.content == "hi"


def test_coerce_tool_result_content_pydantic_like_and_fallbacks() -> None:
    """``_coerce_tool_result_content`` dumps Pydantic-like objects, JSON
    round-trips plain objects, and falls back to ``str()`` on TypeError."""
    from nucleusiq_anthropic.nb_anthropic.messages import (
        _coerce_tool_result_content,
    )

    class _Dumpable:
        def model_dump(self) -> dict:
            return {"ok": True}

    class _Raises:
        def model_dump(self) -> dict:
            raise RuntimeError("nope")

        def __repr__(self) -> str:
            return "<_Raises>"

    assert _coerce_tool_result_content(None) is None
    assert _coerce_tool_result_content(42) == 42
    assert _coerce_tool_result_content("x") == "x"
    assert _coerce_tool_result_content({"a": 1}) == {"a": 1}
    assert _coerce_tool_result_content(_Dumpable()) == {"ok": True}
    # _Raises has no JSON-safe shape; default=str produces a string,
    # so the JSON round-trip path is what is exercised here.
    out = _coerce_tool_result_content(_Raises())
    assert isinstance(out, str)
    assert "_Raises" in out


def test_build_create_kwargs_skips_not_given_and_merges_metadata() -> None:
    kw = build_create_kwargs(
        model="m",
        framework_messages=[{"role": "user", "content": "hi"}],
        max_output_tokens=10,
        temperature=0.0,
        top_p=0.9,
        stop=None,
        tools=None,
        tool_choice=None,
        merged_extras={"metadata": {"trace": "1"}, "ghost": NOT_GIVEN, "empty": None},
        extra_headers=None,
        stream=False,
    )

    assert kw["metadata"] == {"trace": "1"}
    assert "ghost" not in kw
    assert "empty" not in kw
    assert kw["temperature"] == 0.0
    assert kw["top_p"] is NOT_GIVEN
