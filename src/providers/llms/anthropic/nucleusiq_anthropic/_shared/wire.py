"""Translate NucleusIQ / OpenAI-style message lists → Anthropic Messages API params."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, cast

from nucleusiq_anthropic.tools.anthropic_tool import is_native_marker
from nucleusiq_anthropic.tools.converter import to_anthropic_tool_definition


def _parse_json_object(arguments: Any) -> dict[str, Any]:
    """Parse tool ``arguments`` into a mapping for ``tool_use`` ``input``."""
    if isinstance(arguments, dict):
        return cast(dict[str, Any], dict(arguments))
    if not isinstance(arguments, str) or not arguments.strip():
        return {}
    try:
        parsed = json.loads(arguments)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
        return {"value": parsed}
    except json.JSONDecodeError:
        return {}


def _split_data_url(url: str) -> tuple[str, str] | None:
    """Split a ``data:`` URL into *(media_type, base64_or_text_payload)*."""
    if not isinstance(url, str) or not url.startswith("data:"):
        return None
    comma = url.find(",", 5)
    if comma < 0:
        return None
    meta = url[5:comma].strip().lower()
    payload = url[comma + 1 :]
    if ";base64" in meta:
        mime = meta.split(";base64")[0].strip() or "application/octet-stream"
        return mime, payload
    mime_type = meta.split(";", 1)[0].strip() or "text/plain"
    return mime_type, urllib.parse.unquote(payload)


def _content_part_framework_to_anthropic(part: dict[str, Any]) -> list[dict[str, Any]]:
    """Map one multimodal part dict → Anthropic blocks."""
    pt = part.get("type")
    blocks: list[dict[str, Any]] = []

    if pt == "text":
        text_val = part.get("text") or ""
        if isinstance(text_val, str) and text_val.strip():
            blocks.append({"type": "text", "text": text_val})

    elif pt == "image_url":
        iu = part.get("image_url")
        url = iu.get("url", "") if isinstance(iu, dict) else str(iu or "")
        if not isinstance(url, str) or not url:
            pass
        else:
            decoded = _split_data_url(url)
            if decoded:
                mime, data = decoded
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime or "application/octet-stream",
                            "data": data,
                        },
                    }
                )
            elif url.startswith(("http://", "https://")):
                blocks.append(
                    {"type": "image", "source": {"type": "url", "url": url}},
                )

    elif pt == "image":
        blocks.append(dict(part))

    return blocks


def _user_content_blocks(msg: dict[str, Any]) -> list[dict[str, Any]]:
    content = msg.get("content")

    out: list[dict[str, Any]] = []

    if isinstance(content, str) and content.strip():
        out.append({"type": "text", "text": content})

    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                out.extend(_content_part_framework_to_anthropic(part))

    elif content is None:
        return []

    return out


def _assistant_content_blocks(msg: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    raw_content = msg.get("content")

    text_acc: list[str] = []
    if isinstance(raw_content, str) and raw_content.strip():
        text_acc.append(raw_content)
    elif isinstance(raw_content, list):
        for part in raw_content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text") or ""
                if isinstance(t, str) and t.strip():
                    text_acc.append(t)
            elif isinstance(part, dict) and part.get("type") == "thinking":
                # Claude request-side thinking blocks are gated by kwargs
                continue

    merged_text = "\n".join(text_acc).strip()
    if merged_text:
        blocks.append({"type": "text", "text": merged_text})

    for tc_raw in msg.get("tool_calls") or []:
        tc = tc_raw if isinstance(tc_raw, dict) else getattr(tc_raw, "__dict__", {})
        tc_id = str(tc.get("id") or "tool_fallback_id")
        name = ""
        args: Any = "{}"
        fn = tc.get("function")
        if isinstance(fn, dict):
            name = str(fn.get("name") or "")
            args = fn.get("arguments") or "{}"
        else:
            name = str(tc.get("name") or "")
            args = tc.get("arguments") or "{}"
        inp = _parse_json_object(args)
        blocks.append(
            {
                "type": "tool_use",
                "id": tc_id,
                "name": name,
                "input": inp or {},
            }
        )

    if not blocks:
        blocks.append({"type": "text", "text": ""})

    return blocks


def _batch_tool_messages(
    messages: list[dict[str, Any]],
    start_idx: int,
) -> tuple[list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    i = start_idx
    while i < len(messages):
        m = messages[i]
        if m.get("role") not in ("tool", "function"):
            break
        tool_use_id = str(m.get("tool_call_id") or "")
        content = m.get("content")
        if isinstance(content, list):
            text_payload = json.dumps(content)
        elif content is None:
            text_payload = ""
        else:
            text_payload = str(content)
        blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": text_payload,
            }
        )
        i += 1
    user_msg = {"role": "user", "content": blocks}
    return ([user_msg], i)


def split_system(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Strip ``system`` messages and concatenate their text."""
    remainder: list[dict[str, Any]] = []
    system_chunks: list[str] = []

    for msg in messages:
        if msg.get("role") != "system":
            remainder.append(msg)
            continue
        c = msg.get("content")
        if isinstance(c, str):
            if c.strip():
                system_chunks.append(c)
        elif isinstance(c, list):
            texts: list[str] = []
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    ts = p.get("text") or ""
                    if isinstance(ts, str) and ts.strip():
                        texts.append(ts)
            if texts:
                system_chunks.append("\n".join(texts))

    if not system_chunks:
        return None, remainder

    merged = "\n\n".join(system_chunks).strip()
    return (merged or None), remainder


def translate_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Full pipeline: extract system prompt + Anthropic-compatible ``messages``.

    Incoming messages follow the framework chat dict shape documented in
    :class:`~nucleusiq.agents.chat_models.ChatMessage`.
    """
    system, rest = split_system(messages)

    anthropic_turns: list[dict[str, Any]] = []

    idx = 0
    while idx < len(rest):
        msg = rest[idx]
        role = msg.get("role")

        if role == "assistant":
            anthropic_turns.append(
                {
                    "role": "assistant",
                    "content": _assistant_content_blocks(msg),
                }
            )
            idx += 1
            continue

        if role in ("tool", "function"):
            batch, next_idx = _batch_tool_messages(rest, idx)
            anthropic_turns.extend(batch)
            idx = next_idx
            continue

        user_blocks = _user_content_blocks(msg)
        if role == "user" or role is None:
            if not user_blocks:
                anthropic_turns.append(
                    {"role": "user", "content": [{"type": "text", "text": ""}]}
                )
            else:
                anthropic_turns.append({"role": "user", "content": user_blocks})
            idx += 1
            continue

        if role == "system":
            # Defensive — ``split_system`` should have removed these.
            c = msg.get("content")
            if isinstance(c, str) and system is None:
                system = c
            idx += 1
            continue

        fallback = _user_content_blocks(msg)
        if not fallback:
            fallback = [{"type": "text", "text": str(msg.get("content", ""))}]
        anthropic_turns.append({"role": "user", "content": fallback})
        idx += 1

    return system, anthropic_turns


def flatten_tools(
    tool_specs: list[dict[str, Any]] | None,
    *,
    cache_tools: bool = False,
    strict_tools: bool = False,
) -> list[dict[str, Any]] | None:
    """Normalize tool definitions for ``client.messages.create``.

    Parameters
    ----------
    cache_tools:
        When ``True`` and at least one tool definition will be emitted,
        attach an Anthropic ``cache_control`` block to the **last**
        definition.  Anthropic treats the prefix up to that point
        (system + tool definitions before the breakpoint) as cacheable
        for subsequent requests with the same prefix.
    strict_tools:
        When ``True``, set ``strict: True`` on each **custom** tool
        definition.  Server-side / native tools are left untouched
        (Anthropic does not currently accept ``strict`` on those).
    """
    if not tool_specs:
        return None

    defs: list[dict[str, Any]] = []

    for spec in tool_specs:
        if isinstance(spec, dict):
            converted = to_anthropic_tool_definition(spec)
            if strict_tools and not _is_native_wire(spec, converted):
                converted = {**converted, "strict": True}
            defs.append(converted)
        else:
            defs.append(spec)  # pragma: no cover — defensive path

    if cache_tools and defs:
        defs[-1] = _with_cache_control(defs[-1])

    return defs if defs else None


def _is_native_wire(orig: dict[str, Any], converted: dict[str, Any]) -> bool:
    """Whether *converted* is a Claude server-side (native) tool definition.

    Considered "native" when (a) the original spec was an ``AnthropicTool``
    marker, or (b) the converted ``type`` is a dated identifier (anything
    other than the absence of ``type`` — custom tools omit it).
    """
    if is_native_marker(orig):
        return True
    ct = converted.get("type")
    return isinstance(ct, str) and ct != "function" and ct.startswith(
        ("web_search", "web_fetch", "code_execution")
    )


def _with_cache_control(tool_def: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *tool_def* with an Anthropic ``cache_control`` block."""
    return {**tool_def, "cache_control": {"type": "ephemeral"}}


def system_with_cache(system: str | None, *, cache_system: bool) -> Any:
    """Return the system parameter shape Anthropic expects.

    Anthropic accepts either a plain string (legacy) or a list of
    content blocks (required when ``cache_control`` is attached).
    """
    if not system:
        return system
    if not cache_system:
        return system
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def anthropic_tool_choice(openai_tc: Any) -> dict[str, Any] | None:
    """Map optional OpenAI-ish ``tool_choice`` to Claude's shape."""
    if openai_tc is None:
        return None
    if isinstance(openai_tc, str):
        s = openai_tc.lower()
        if s in ("none", "off"):
            return {"type": "none"}
        if s == "required" or s == "any":
            return {"type": "any"}
        # default / auto strings
        return {"type": "auto"}
    if isinstance(openai_tc, dict):
        if openai_tc.get("type") == "function":
            fname = ""
            fn = openai_tc.get("function")
            if isinstance(fn, dict):
                fname = str(fn.get("name") or "")
            if fname:
                return {"type": "tool", "name": fname}
            return {"type": "auto"}
        return cast(dict[str, Any], dict(openai_tc))

    return None


def drop_unsupported_sampling(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Claude Messages does not honour OpenAI penalties — strip them from passthrough kwargs.

    Also strips the **private NucleusIQ Phase B markers** (``_cache_*``,
    ``_strict_tools``, ``_disable_parallel_tool_use``).  Those are
    interpreted by :func:`build_create_kwargs` before this function
    runs; they must not reach ``messages.create``.
    """
    out = dict(kwargs)
    for k in (
        "frequency_penalty",
        "presence_penalty",
        "n",
        "parallel_tool_calls",
        "seed",
        "user",
    ):
        out.pop(k, None)

    # Common Core merge keys that Claude doesn't map 1:1 on the root call.
    for k in (
        "max_output_tokens",
        "response_format",
    ):
        out.pop(k, None)

    # Phase B private markers (interpreted by build_create_kwargs upstream).
    for k in (
        "_cache_tools",
        "_cache_system",
        "_strict_tools",
        "_disable_parallel_tool_use",
    ):
        out.pop(k, None)

    return out
