"""Factory functions for building tracer records from raw execution data.

Each builder centralises the conversion from provider-specific response
shapes into framework-standard record types.  This keeps provider
coupling out of the tracer itself and out of the mode implementations.
"""

from __future__ import annotations

import json
from typing import Any

from nucleusiq.agents.agent_result import LLMCallRecord, ToolCallRecord
from nucleusiq.agents.chat_models import ToolCallRequest
from nucleusiq.agents.observability._response_parser import (
    extract_tool_calls,
    safe_int,
    usage_dict_from_response,
)


def build_tool_call_record(
    tc: ToolCallRequest,
    *,
    result: Any = None,
    success: bool = True,
    error: str | None = None,
    error_type: str | None = None,
    duration_ms: float = 0.0,
    round: int = 1,
    args: dict[str, Any] | None = None,
    source: str | None = None,
    executed_by: str = "local",
) -> ToolCallRecord:
    """Build a :class:`ToolCallRecord` for the tracer.

    Parameters
    ----------
    source:
        Optional opaque origin label (e.g. ``"mcp://server=github (path=A)"``)
        set by adapter packages such as ``nucleusiq-mcp``.  ``None`` for
        plain local tools — preserves backwards compatibility.
    executed_by:
        ``"local"`` (default) when the NucleusIQ agent loop ran the tool,
        ``"provider"`` when the LLM provider executed it server-side
        (Anthropic ``web_search``, OpenAI ``code_interpreter``, Groq
        compound tools, …).  Used by tracer consumers to split cost /
        latency reporting by execution surface.
    """
    parsed: dict[str, Any] = {}
    if args is not None:
        parsed = dict(args)
    elif tc.arguments:
        try:
            loaded = json.loads(tc.arguments)
            if isinstance(loaded, dict):
                parsed = loaded
        except (json.JSONDecodeError, TypeError):
            pass
    # ``executed_by`` is a Literal["local", "provider"] on the record;
    # coerce unknown values to ``"local"`` so an upstream typo cannot
    # raise a ValidationError inside the agent loop.
    safe_executed_by = "provider" if executed_by == "provider" else "local"
    return ToolCallRecord(
        tool_name=tc.name or "",
        tool_call_id=tc.id,
        args=parsed,
        result=result,
        success=success,
        error=error,
        error_type=error_type,
        duration_ms=duration_ms,
        round=round,
        source=source,
        executed_by=safe_executed_by,  # type: ignore[arg-type]
    )


def build_server_tool_call_records(
    server_tool_calls: Any,
    *,
    round: int = 1,
) -> list[ToolCallRecord]:
    """Build ``ToolCallRecord(executed_by="provider")`` entries from a provider's
    ``server_tool_calls`` list.

    Generic over the item shape — accepts mappings or any object exposing
    ``id`` / ``name`` / ``input`` / ``result`` attributes (e.g. Anthropic's
    ``ServerToolCall`` Pydantic model, OpenAI's hosted-tool blocks, Gemini's
    ``google_search`` blocks once those providers populate the list).  An empty
    or ``None`` input returns an empty list so callers can call this
    unconditionally after every LLM round.
    """
    records: list[ToolCallRecord] = []
    if not server_tool_calls:
        return records
    try:
        iterator = list(server_tool_calls)
    except TypeError:
        return records
    for item in iterator:
        if isinstance(item, dict):
            tool_id = item.get("id") or ""
            name = item.get("name") or ""
            args = item.get("input") if isinstance(item.get("input"), dict) else {}
            result = item.get("result")
        else:
            tool_id = getattr(item, "id", "") or ""
            name = getattr(item, "name", "") or ""
            raw_input = getattr(item, "input", None)
            args = raw_input if isinstance(raw_input, dict) else {}
            result = getattr(item, "result", None)
        records.append(
            ToolCallRecord(
                tool_name=str(name),
                tool_call_id=str(tool_id) if tool_id else None,
                args=dict(args) if isinstance(args, dict) else {},
                result=result,
                success=True,
                error=None,
                error_type=None,
                duration_ms=0.0,
                round=round,
                source=None,
                executed_by="provider",
            )
        )
    return records


def _extract_str(source: Any, *keys: str) -> str | None:
    """Return the first non-empty string-coercible value at ``keys`` in *source*.

    Supports both mapping-style and attribute-style access (Pydantic/SDK
    response objects often expose fields as attributes, dicts as keys).
    Empty strings collapse to ``None`` so callers can treat ``""`` as
    "field not supplied" without extra logic.
    """
    if source is None:
        return None
    for key in keys:
        value: Any = None
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_int(source: Any, *keys: str) -> int:
    """Return the first integer-coercible value at ``keys`` in *source*, or 0."""
    if source is None:
        return 0
    for key in keys:
        value: Any = None
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _usage_cache_tokens(usage: dict[str, Any]) -> tuple[int, int]:
    """Return ``(cache_read, cache_creation)`` token counts from a usage dict.

    Maps both Anthropic naming (``cache_read_input_tokens`` /
    ``cache_creation_input_tokens``) and OpenAI naming (``cached_tokens``
    nested under ``prompt_tokens_details``) into a single shape.
    """
    read = safe_int(usage, "cache_read_input_tokens")
    creation = safe_int(usage, "cache_creation_input_tokens")
    if read == 0:
        # OpenAI Responses / Chat surface caching via prompt_tokens_details.
        details = usage.get("prompt_tokens_details")
        if isinstance(details, dict):
            read = safe_int(details, "cached_tokens")
    return read, creation


def build_llm_call_record(
    response: Any,
    *,
    call_round: int,
    purpose: str,
    duration_ms: float = 0.0,
    model: str | None = None,
    prompt_technique: str | None = None,
    provider: str | None = None,
    request_id: str | None = None,
    organization_id: str | None = None,
    stop_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMCallRecord:
    """Build an :class:`LLMCallRecord` from a non-streaming provider response.

    Providers can pass observability hints explicitly via the keyword
    arguments; when omitted, the builder tries common attribute/dict
    keys on *response* so existing call-sites get the new fields for
    free where the underlying SDK already populates them.
    """
    usage = usage_dict_from_response(response) or {}
    prompt = safe_int(usage, "prompt_tokens")
    completion = safe_int(usage, "completion_tokens")
    total = safe_int(usage, "total_tokens") or (prompt + completion)
    reasoning = safe_int(usage, "reasoning_tokens")
    cache_read, cache_creation = _usage_cache_tokens(usage)

    tcs = extract_tool_calls(response)

    resolved_request_id = request_id or _extract_str(
        response, "request_id", "id", "_request_id"
    )
    resolved_org_id = organization_id or _extract_str(
        response, "organization_id", "anthropic_organization_id"
    )
    resolved_stop = stop_reason or _extract_str(
        response, "stop_reason", "finish_reason"
    )

    return LLMCallRecord(
        round=call_round,
        purpose=purpose,
        model=model
        or getattr(response, "model", None)
        or (response.get("model") if isinstance(response, dict) else None),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        reasoning_tokens=reasoning,
        has_tool_calls=bool(tcs),
        tool_call_count=len(tcs),
        duration_ms=duration_ms,
        prompt_technique=prompt_technique,
        provider=provider,
        request_id=resolved_request_id,
        organization_id=resolved_org_id,
        stop_reason=resolved_stop,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
        metadata=dict(metadata) if metadata else {},
    )


def build_llm_call_record_from_stream(
    metadata: dict[str, Any] | None,
    *,
    call_round: int,
    purpose: str,
    duration_ms: float = 0.0,
    model: str | None = None,
    prompt_technique: str | None = None,
    provider: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> LLMCallRecord:
    """Build an :class:`LLMCallRecord` from streaming COMPLETE metadata.

    *metadata* is the dict surfaced on the ``COMPLETE`` ``StreamEvent``
    by each provider's stream adapter.  Provider stream adapters are
    encouraged to include ``request_id``, ``organization_id`` (when
    available), ``stop_reason`` (or ``finish_reason``), and the usage
    block — those are picked up automatically here.
    """
    usage: dict[str, Any] = {}
    if metadata:
        u = metadata.get("usage")
        if isinstance(u, dict):
            usage = u
        elif u is not None and hasattr(u, "model_dump"):
            usage = u.model_dump()

    prompt = safe_int(usage, "prompt_tokens")
    completion = safe_int(usage, "completion_tokens")
    total = safe_int(usage, "total_tokens") or (prompt + completion)
    reasoning = safe_int(usage, "reasoning_tokens")
    cache_read, cache_creation = _usage_cache_tokens(usage)

    raw_tcs: list[Any] = []
    if metadata:
        raw_tcs = metadata.get("tool_calls") or []
    if not isinstance(raw_tcs, list):
        raw_tcs = []

    has_tools = bool(raw_tcs)
    request_id = _extract_str(metadata, "request_id", "id") if metadata else None
    organization_id = (
        _extract_str(metadata, "organization_id", "anthropic_organization_id")
        if metadata
        else None
    )
    stop_reason = (
        _extract_str(metadata, "stop_reason", "finish_reason") if metadata else None
    )

    merged_metadata: dict[str, Any] = {}
    if extra_metadata:
        merged_metadata.update(extra_metadata)

    return LLMCallRecord(
        round=call_round,
        purpose=purpose,
        model=model or (metadata.get("model") if metadata else None),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        reasoning_tokens=reasoning,
        has_tool_calls=has_tools,
        tool_call_count=len(raw_tcs),
        duration_ms=duration_ms,
        prompt_technique=prompt_technique,
        provider=provider,
        request_id=request_id,
        organization_id=organization_id,
        stop_reason=stop_reason,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
        metadata=merged_metadata,
    )
