"""Messages backend — normalize SDK payloads and invoke ``messages.create``."""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import NOT_GIVEN

from nucleusiq_anthropic._shared.response_models import (
    AnthropicLLMResponse,
    AssistantMessage,
    ServerToolCall,
    ToolCall,
    ToolCallFunction,
    UsageInfo,
    _Choice,
)
from nucleusiq_anthropic._shared.retry import call_with_retry
from nucleusiq_anthropic._shared.wire import (
    anthropic_tool_choice,
    drop_unsupported_sampling,
    flatten_tools,
    system_with_cache,
    translate_messages,
)
from nucleusiq_anthropic.tools.anthropic_tool import (
    NATIVE_TOOL_TYPES,
    required_beta_headers,
)

logger = logging.getLogger(__name__)


def _drop_conflicting_sampling(kw: dict[str, Any]) -> None:
    """Claude rejects ``messages.create`` when both ``temperature`` and ``top_p`` are set."""

    temperature = kw.get("temperature")
    top_p = kw.get("top_p")
    has_temp = temperature is not NOT_GIVEN and temperature is not None
    has_top_p = top_p is not NOT_GIVEN and top_p is not None
    if has_temp and has_top_p:
        kw["top_p"] = NOT_GIVEN


def _is_server_tool_block(block: Any) -> bool:
    """Whether *block* is a ``tool_use`` for a Claude server-side tool."""
    if getattr(block, "type", None) != "tool_use":
        return False
    name = getattr(block, "name", "") or ""
    return name in NATIVE_TOOL_TYPES


def _coerce_tool_result_content(content: Any) -> Any:
    """Reduce a server tool-result block's ``content`` to a JSON-safe value.

    Anthropic's per-tool result blocks (``code_execution_tool_result``,
    ``web_search_tool_result``, …) wrap their payload in a typed
    Pydantic-like object (e.g. ``CodeExecutionResultBlock(stdout="4",
    return_code=0, …)``).  We try ``model_dump()`` first, fall back to
    a JSON round-trip, and finally to ``str()`` so the
    :class:`ServerToolCall.result` field always serialises cleanly when
    the tracer dumps an ``AgentResult``.
    """
    if content is None:
        return None
    if isinstance(content, (str, int, float, bool)):
        return content
    if isinstance(content, list):
        return [_coerce_tool_result_content(item) for item in content]
    if isinstance(content, dict):
        return content
    if hasattr(content, "model_dump"):
        try:
            return content.model_dump()
        except Exception:
            pass
    try:
        return json.loads(json.dumps(content, default=str))
    except (TypeError, ValueError):
        return str(content)


def normalize_message_response(raw: Any) -> AnthropicLLMResponse:
    """Map Claude ``Message`` → :class:`AnthropicLLMResponse` (Choices contract).

    Splits ``tool_use`` blocks into two buckets:

    * **Client tools** (model invokes a custom function) → emitted as
      :class:`ToolCall` entries on ``assistant.tool_calls`` so the
      agent loop dispatches them.
    * **Server-side tools** (``web_search`` / ``web_fetch`` /
      ``code_execution`` / …) → emitted as :class:`ServerToolCall`
      entries on ``response.server_tool_calls`` for observability
      (``BaseAnthropic`` reports them with
      ``ToolCallRecord(executed_by="provider")``).
    """

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    server_tool_calls: list[ServerToolCall] = []
    # Cache the server tool_use id → name so we can attach
    # ``tool_result`` payloads emitted in the same response.
    server_ids: dict[str, ServerToolCall] = {}

    for block in getattr(raw, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            t = getattr(block, "text", None)
            if t:
                text_parts.append(str(t))
            continue

        # Both ``tool_use`` (custom client tool) and ``server_tool_use``
        # (Anthropic-executed native tool — web_search, web_fetch,
        # code_execution) carry id / name / input on the same shape.
        if btype in ("tool_use", "server_tool_use"):
            bid = getattr(block, "id", "") or ""
            name = getattr(block, "name", "") or ""
            inp = getattr(block, "input", None)
            payload = inp if isinstance(inp, dict) else {"value": inp}

            if btype == "server_tool_use" or name in NATIVE_TOOL_TYPES:
                stc = ServerToolCall(id=bid, name=name, input=dict(payload))
                server_tool_calls.append(stc)
                server_ids[bid] = stc
                continue

            try:
                arguments = json.dumps(payload, default=str)
            except (TypeError, ValueError):
                arguments = "{}"
            tool_calls.append(
                ToolCall(
                    id=bid,
                    type="function",
                    function=ToolCallFunction(name=name, arguments=arguments),
                ),
            )
            continue

        # Server-side result blocks: legacy ``tool_result`` plus the
        # per-tool variants Anthropic emits in non-streaming responses
        # (``web_search_tool_result``, ``code_execution_tool_result``,
        # ``web_fetch_tool_result``, …).  All carry ``tool_use_id`` +
        # ``content``.  Extract the most useful summary onto the
        # matching :class:`ServerToolCall`.
        if btype == "tool_result" or (
            isinstance(btype, str) and btype.endswith("_tool_result")
        ):
            tool_use_id = getattr(block, "tool_use_id", None) or ""
            target = server_ids.get(tool_use_id)
            if target is None:
                continue
            content = getattr(block, "content", None)
            target.result = _coerce_tool_result_content(content)

    merged_text = "\n".join(text_parts).strip() or None
    assistant = AssistantMessage(
        content=merged_text,
        tool_calls=tool_calls if tool_calls else None,
    )

    usage_out: UsageInfo | None = None
    usage = getattr(raw, "usage", None)
    if usage is not None:
        inp = getattr(usage, "input_tokens", None) or 0
        out_t = getattr(usage, "output_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", None) or 0
        usage_out = UsageInfo(
            prompt_tokens=int(inp) + int(cache_create) + int(cache_read),
            completion_tokens=int(out_t),
            total_tokens=int(inp) + int(out_t) + int(cache_read) + int(cache_create),
            cached_tokens=int(cache_read),
            cache_read_input_tokens=int(cache_read),
            cache_creation_input_tokens=int(cache_create),
        )

    stop_reason = getattr(raw, "stop_reason", None)
    return AnthropicLLMResponse(
        choices=[_Choice(message=assistant)],
        usage=usage_out,
        model=str(getattr(raw, "model", None) or "") or None,
        response_id=getattr(raw, "id", None),
        stop_reason=str(stop_reason) if stop_reason is not None else None,
        organization_id=_extract_organization_id(raw),
        server_tool_calls=server_tool_calls,
    )


def _extract_organization_id(raw: Any) -> str | None:
    """Best-effort lookup of the Anthropic organisation id from a response.

    Anthropic surfaces ``anthropic-organization-id`` as an HTTP response
    header.  The SDK exposes raw headers via ``response.response.headers``
    (when wrapped with ``with_raw_response``); when missing, returns
    ``None`` rather than guessing.
    """
    # 1) Direct attribute (some SDK paths attach it post-deserialisation).
    direct = getattr(raw, "organization_id", None) or getattr(
        raw, "anthropic_organization_id", None
    )
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    # 2) When ``raw`` carries an HTTP ``response`` (e.g. _LegacyAPIResponse),
    # peek at the headers.
    response = getattr(raw, "response", None)
    headers = getattr(response, "headers", None) if response is not None else None
    if headers is not None:
        val = (
            headers.get("anthropic-organization-id")
            if hasattr(headers, "get")
            else None
        )
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def build_create_kwargs(
    *,
    model: str,
    framework_messages: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float | None,
    top_p: float | None,
    stop: list[str] | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    merged_extras: dict[str, Any],
    extra_headers: dict[str, str] | None,
    stream: bool = False,
) -> dict[str, Any]:
    """Assemble keyword arguments for ``Anthropic.messages.create``.

    Phase B (0.2.0) extensions interpreted here:

    * ``_cache_tools`` / ``_cache_system`` — attach ``cache_control``
      blocks to enable Anthropic prompt caching.
    * ``_strict_tools`` — flag every custom tool definition with
      ``strict: True``.
    * ``_disable_parallel_tool_use`` — augment ``tool_choice`` with
      ``disable_parallel_tool_use: true`` (per Anthropic docs).
    * Required beta headers for native tools (``web_fetch``,
      ``code_execution``) are auto-collected and merged into
      ``anthropic-beta`` so callers do not need to remember them.
    """

    # Phase B private markers — interpret before drop_unsupported_sampling
    # strips them.
    cache_tools = bool(merged_extras.get("_cache_tools"))
    cache_system = bool(merged_extras.get("_cache_system"))
    strict_tools = bool(merged_extras.get("_strict_tools"))
    disable_parallel = bool(merged_extras.get("_disable_parallel_tool_use"))

    system, msgs = translate_messages(framework_messages)
    system_payload = system_with_cache(system, cache_system=cache_system)
    claude_tools = flatten_tools(
        tools, cache_tools=cache_tools, strict_tools=strict_tools
    )
    mapped_choice = anthropic_tool_choice(tool_choice)
    if mapped_choice is not None and disable_parallel:
        mapped_choice = {**mapped_choice, "disable_parallel_tool_use": True}

    clean_extras = drop_unsupported_sampling(merged_extras)
    beta_str = clean_extras.pop("anthropic_beta", None)

    kw: dict[str, Any] = {
        "model": model,
        "max_tokens": max_output_tokens,
        "messages": msgs,
        "temperature": temperature if temperature is not None else NOT_GIVEN,
        "top_p": top_p if top_p is not None else NOT_GIVEN,
        "stop_sequences": stop or NOT_GIVEN,
        "tools": claude_tools or NOT_GIVEN,
        "tool_choice": mapped_choice if mapped_choice is not None else NOT_GIVEN,
        "stream": stream,
    }

    if system_payload is not None:
        kw["system"] = system_payload

    # Collect beta headers required by any native tools in the request.
    auto_betas = required_beta_headers(tools)

    headers: dict[str, str] | None = None
    if extra_headers:
        headers = dict(extra_headers)

    # Merge user-supplied + auto-collected beta header tokens.
    beta_tokens: list[str] = []
    if isinstance(beta_str, str) and beta_str.strip():
        beta_tokens.extend(t.strip() for t in beta_str.split(",") if t.strip())
    for tok in auto_betas:
        if tok not in beta_tokens:
            beta_tokens.append(tok)

    if beta_tokens:
        headers = dict(headers or {})
        headers["anthropic-beta"] = ",".join(beta_tokens)

    for key in ("model", "max_tokens", "messages", "stream"):
        clean_extras.pop(key, None)

    for key, val in clean_extras.items():
        if val is NOT_GIVEN or val is None:
            continue
        kw[key] = val

    _drop_conflicting_sampling(kw)

    if headers:
        kw["extra_headers"] = headers

    return kw


async def create_message_response(
    client: Any,
    *,
    async_mode: bool,
    max_retries: int,
    model: str,
    messages: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float | None,
    top_p: float | None,
    stop: list[str] | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: Any,
    merged_extras: dict[str, Any],
    extra_headers: dict[str, str] | None,
) -> AnthropicLLMResponse:
    """Non-stream call with retries."""

    kw = build_create_kwargs(
        model=model,
        framework_messages=messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        top_p=top_p,
        stop=stop,
        tools=tools,
        tool_choice=tool_choice,
        merged_extras=dict(merged_extras),
        extra_headers=extra_headers,
        stream=False,
    )

    async def api_call() -> Any:
        return await client.messages.create(**kw)

    def api_call_sync() -> Any:
        return client.messages.create(**kw)

    factory = api_call if async_mode else api_call_sync

    raw = await call_with_retry(
        factory,
        max_retries=max_retries,
        async_mode=async_mode,
        logger=logger,
    )
    return normalize_message_response(raw)
