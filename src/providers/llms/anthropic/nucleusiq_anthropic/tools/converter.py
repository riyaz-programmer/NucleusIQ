"""Convert framework tool specs → Anthropic Messages API ``tools`` definitions."""

from __future__ import annotations

from typing import Any, cast

from nucleusiq_anthropic.tools.anthropic_tool import (
    NATIVE_TOOL_TYPES,
    is_native_marker,
    marker_to_wire,
)


def to_anthropic_tool_definition(spec: dict[str, Any]) -> dict[str, Any]:
    """Map a generic ``BaseTool.get_spec()`` dict to Anthropic tool shape.

    Handled cases (in priority order):

    1. **NucleusIQ ``AnthropicTool.*()`` markers** — unwrapped via
       :func:`marker_to_wire` into the dated ``{"type": "...20250305", ...}``
       payload Anthropic expects.
    2. **Native-style specs** already containing ``input_schema`` and ``name``
       — returned with only Anthropic-supported keys preserved.
    3. **OpenAI-style envelopes** ``type: function`` + nested ``function`` —
       unwrapped into ``name`` / ``description`` / ``input_schema``.
    4. **Raw server-tool dicts** with a non-``function`` ``type`` field —
       passed through verbatim (advanced users opting out of the factory).
    """

    # 1) NucleusIQ marker for built-in tools (preferred public path).
    if is_native_marker(spec):
        return marker_to_wire(spec)

    tool_type = spec.get("type")

    # 4) Pass through raw server / native tool payloads (advanced usage).
    if tool_type is not None and tool_type != "function":
        return dict(spec)

    # 2) Native-style — already in (name, input_schema) form.
    if "input_schema" in spec:
        block: dict[str, Any] = {
            "name": spec["name"],
            "input_schema": spec["input_schema"],
        }
        if spec.get("description"):
            block["description"] = spec["description"]
        return block

    # 3) OpenAI-style ``{"type": "function", "function": {...}}`` envelope.
    fn = spec.get("function") if isinstance(spec.get("function"), dict) else None
    name = (fn.get("name") if fn else None) or spec.get("name", "")
    description = (fn.get("description") if fn else None) or spec.get(
        "description",
        "",
    )

    raw_params = (fn.get("parameters") if fn else None) or spec.get("parameters")

    parameters: dict[str, Any]
    if isinstance(raw_params, dict):
        parameters = cast(dict[str, Any], dict(raw_params))
        if raw_params.get("type") != "object":
            parameters = {
                "type": "object",
                "properties": {"value": dict(raw_params)},
            }
        if "additionalProperties" not in parameters:
            parameters = {**parameters, "additionalProperties": False}
    else:
        parameters = {"type": "object", "properties": {}, "additionalProperties": False}

    return {
        "name": name,
        "description": description or "",
        "input_schema": parameters,
    }


def spec_looks_native(spec: dict[str, Any]) -> bool:
    """Whether *spec* is a server-side Claude tool marker (non-function).

    Returns ``True`` for both **AnthropicTool markers** (``type ==
    "anthropic_builtin"``) and **raw native specs** (``type`` matches one
    of Anthropic's dated wire identifiers, e.g. ``web_search_20250305``).
    """
    if is_native_marker(spec):
        return True
    t = spec.get("type")
    if t is None or t == "function":
        return False
    # Raw native specs (advanced users) — ``type`` field carries the
    # dated identifier; resolve to logical name via the suffix-strip
    # pattern Anthropic uses for these tools.
    if not isinstance(t, str):
        return False
    base = t.split("_2", 1)[0]
    return base in NATIVE_TOOL_TYPES or spec.get("name") in NATIVE_TOOL_TYPES


__all__ = ["NATIVE_TOOL_TYPES", "spec_looks_native", "to_anthropic_tool_definition"]
