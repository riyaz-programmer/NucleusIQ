"""Chat Completions backend — single responsibility: call API + normalize."""

from __future__ import annotations

import logging
from typing import Any

from nucleusiq_groq._shared.response_models import (
    AssistantMessage,
    GroqLLMResponse,
    ServerToolCall,
    ToolCall,
    ToolCallFunction,
    UsageInfo,
    _Choice,
)
from nucleusiq_groq._shared.retry import call_with_retry
from nucleusiq_groq._shared.wire import build_chat_completion_payload

logger = logging.getLogger(__name__)


def _extract_server_tool_calls(message: Any) -> list[ServerToolCall]:
    """Extract Groq hosted-tool invocations from a chat completion message.

    Groq exposes hosted/compound tools via ``message.executed_tools`` —
    a list of OpenAI-style ``{type, function, ...}`` blocks where the
    function metadata describes what ran server-side (compound search,
    code execution, MCP, browser automation, …).  Phase A keeps this
    extractor minimal-cost: when ``executed_tools`` is absent or empty
    we return ``[]``; when present we surface every entry so the core
    agent loop emits ``ToolCallRecord(executed_by="provider")``.
    """
    raw_executed = getattr(message, "executed_tools", None)
    if not raw_executed:
        return []
    out: list[ServerToolCall] = []
    for idx, et in enumerate(raw_executed):
        out.append(_one_executed_tool_to_record(et, idx))
    return out


def _read_executed_field(payload: dict[str, Any], item: Any, key: str) -> Any:
    """Read ``key`` from a dict payload, falling back to ``item`` attributes."""
    if isinstance(payload, dict) and payload.get(key) is not None:
        return payload[key]
    return getattr(item, key, None)


def _one_executed_tool_to_record(et: Any, idx: int) -> ServerToolCall:
    """Convert one Groq ``executed_tools`` entry to a :class:`ServerToolCall`."""
    if isinstance(et, dict):
        payload: dict[str, Any] = dict(et)
    elif hasattr(et, "model_dump"):
        try:
            dumped = et.model_dump()
            payload = dict(dumped) if isinstance(dumped, dict) else {}
        except Exception:
            payload = {}
    else:
        payload = {}

    fn_meta = _read_executed_field(payload, et, "function")
    if isinstance(fn_meta, dict):
        name = (
            fn_meta.get("name")
            or _read_executed_field(payload, et, "type")
            or "executed_tool"
        )
        input_payload: Any = fn_meta.get("arguments")
    elif fn_meta is not None:
        name = (
            getattr(fn_meta, "name", None)
            or _read_executed_field(payload, et, "type")
            or "executed_tool"
        )
        input_payload = getattr(fn_meta, "arguments", None)
    else:
        name = _read_executed_field(payload, et, "type") or "executed_tool"
        input_payload = None

    if isinstance(input_payload, str):
        try:
            import json as _json

            parsed_input = _json.loads(input_payload)
            input_payload = parsed_input if isinstance(parsed_input, dict) else {}
        except Exception:
            input_payload = {"arguments": input_payload}
    elif not isinstance(input_payload, dict):
        input_payload = {}

    return ServerToolCall(
        id=str(_read_executed_field(payload, et, "id") or f"groq_executed_{idx + 1}"),
        name=str(name or "executed_tool"),
        input=input_payload,
        result=_read_executed_field(payload, et, "output")
        or _read_executed_field(payload, et, "result"),
    )


def normalize_chat_response(raw: Any) -> GroqLLMResponse:
    """Map an OpenAI SDK chat completion object to :class:`GroqLLMResponse`."""
    choices_out: list[_Choice] = []
    server_tool_calls: list[ServerToolCall] = []
    choices_raw = getattr(raw, "choices", None) or []
    for ch in choices_raw:
        msg = getattr(ch, "message", None)
        if msg is None:
            continue
        content = getattr(msg, "content", None)
        tool_calls_out: list[ToolCall] | None = None
        raw_tc = getattr(msg, "tool_calls", None)
        if raw_tc:
            tool_calls_out = []
            for tc in raw_tc:
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                tool_calls_out.append(
                    ToolCall(
                        id=getattr(tc, "id", "") or "",
                        type=getattr(tc, "type", None) or "function",
                        function=ToolCallFunction(
                            name=getattr(fn, "name", "") or "",
                            arguments=getattr(fn, "arguments", "") or "",
                        ),
                    )
                )
        server_tool_calls.extend(_extract_server_tool_calls(msg))
        choices_out.append(
            _Choice(
                message=AssistantMessage(
                    content=content,
                    tool_calls=tool_calls_out,
                )
            )
        )

    usage_out: UsageInfo | None = None
    usage = getattr(raw, "usage", None)
    if usage:
        comp_details = getattr(usage, "completion_tokens_details", None)
        usage_out = UsageInfo(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            reasoning_tokens=(
                getattr(comp_details, "reasoning_tokens", 0) or 0 if comp_details else 0
            ),
        )

    return GroqLLMResponse(
        choices=choices_out,
        usage=usage_out,
        model=getattr(raw, "model", None),
        response_id=getattr(raw, "id", None),
        server_tool_calls=server_tool_calls,
    )


async def create_chat_completion(
    client: Any,
    *,
    async_mode: bool,
    max_retries: int,
    model: str,
    messages: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float | None,
    top_p: float,
    frequency_penalty: float,
    presence_penalty: float,
    stop: list[str] | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    response_format: dict[str, Any] | None,
    parallel_tool_calls: bool | None,
    seed: int | None,
    user: str | None,
    extra: dict[str, Any],
) -> GroqLLMResponse:
    """Run ``chat.completions.create`` with retries and return normalised result."""
    payload = build_chat_completion_payload(
        model=model,
        messages=messages,
        max_tokens=max_output_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        stop=stop,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        parallel_tool_calls=parallel_tool_calls,
        seed=seed,
        user=user,
        extra=extra,
    )

    async def api_call() -> Any:
        if async_mode:
            return await client.chat.completions.create(**payload)
        return client.chat.completions.create(**payload)

    raw = await call_with_retry(
        api_call,
        max_retries=max_retries,
        async_mode=async_mode,
        logger=logger,
    )
    return normalize_chat_response(raw)
