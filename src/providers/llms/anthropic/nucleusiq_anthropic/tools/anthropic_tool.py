"""Factory helpers for **server-side (native) Claude tools**.

Anthropic ships a set of built-in tools (``web_search``, ``web_fetch``,
``code_execution``, …) that the model runs on Anthropic infrastructure.
Each one has:

* a dated ``type`` identifier (e.g. ``web_search_20250305``),
* an optional **beta header** required to enable the feature, and
* a small set of configuration keys.

User-facing code should never need to remember any of those details.
``AnthropicTool.web_search()`` returns a small marker dict that
``BaseAnthropic`` recognises, converts to the correct Anthropic shape,
and collects required beta headers for.

The marker dict shape::

    {
        "type": "anthropic_builtin",   # NucleusIQ marker (NOT Anthropic's wire shape)
        "name": "web_search",           # one of NATIVE_TOOL_TYPES
        "params": {...},                # tool-specific configuration
    }

``to_anthropic_tool_definition`` (in :mod:`nucleusiq_anthropic.tools.converter`)
unwraps the marker into the real Anthropic wire shape. The wire layer
also emits the appropriate beta header.

See:
* Web search — https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
* Web fetch  — https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
* Code exec  — https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
"""

from __future__ import annotations

from typing import Any

# ------------------------------------------------------------------ #
# Public registry                                                      #
# ------------------------------------------------------------------ #

#: Identifiers of every Claude server-side tool ``nucleusiq-anthropic``
#: knows how to wire today. Membership is checked by the agent loop
#: (``Executor`` skips ``execute()`` on tools whose ``name`` is here —
#: those are executed by Anthropic, not by NucleusIQ).
NATIVE_TOOL_TYPES: frozenset[str] = frozenset(
    {"web_search", "web_fetch", "code_execution"}
)

#: Wire identifiers Anthropic accepts on the ``tools[].type`` field today.
#: Pinned to specific dated revisions so behaviour does not drift when
#: Anthropic rolls a new identifier — bump this when validating a new
#: revision against Claude's docs.
NATIVE_TOOL_WIRE_TYPES: dict[str, str] = {
    "web_search": "web_search_20250305",
    "web_fetch": "web_fetch_20250910",
    "code_execution": "code_execution_20250522",
}

#: Beta headers each native tool requires (when any). ``None`` means the
#: tool is GA and needs no beta opt-in.
NATIVE_TOOL_BETA_HEADERS: dict[str, str | None] = {
    "web_search": None,
    "web_fetch": "web-fetch-2025-09-10",
    "code_execution": "code-execution-2025-05-22",
}

#: Marker used on the NucleusIQ-side tool spec dict. Detected by the
#: converter & wire to swap in the real Anthropic wire shape.
_MARKER_TYPE = "anthropic_builtin"


# ------------------------------------------------------------------ #
# Factory class                                                        #
# ------------------------------------------------------------------ #


class AnthropicTool:
    """Static factories for Claude server-side tools.

    Each method returns a small marker dict that ``BaseAnthropic``
    forwards to the Anthropic API after converting it to the correct
    wire shape and attaching any required beta header.

    Examples
    --------
    >>> from nucleusiq_anthropic.tools import AnthropicTool
    >>> agent = Agent(
    ...     llm=BaseAnthropic(model_name="claude-opus-4-20250514"),
    ...     tools=[
    ...         AnthropicTool.web_search(max_uses=3),
    ...         AnthropicTool.code_execution(),
    ...         lookup_order,  # your custom @tool
    ...     ],
    ... )
    """

    # Re-export so users can `from nucleusiq_anthropic.tools import AnthropicTool`
    # and read the registry without a second import.
    NATIVE_TOOL_TYPES: frozenset[str] = NATIVE_TOOL_TYPES

    @staticmethod
    def web_search(
        *,
        max_uses: int | None = None,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        user_location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Anthropic-hosted **web search** tool.

        Parameters
        ----------
        max_uses:
            Cap on how many web-search invocations Claude may make per
            request.  ``None`` keeps Anthropic's default.
        allowed_domains / blocked_domains:
            Domain filters per Anthropic's web-search docs. Mutually
            exclusive — pass at most one.
        user_location:
            Optional location hint forwarded to Anthropic (``timezone``,
            ``country``, ``city`` keys).
        """
        if allowed_domains and blocked_domains:
            raise ValueError(
                "AnthropicTool.web_search: allowed_domains and blocked_domains "
                "are mutually exclusive."
            )

        params: dict[str, Any] = {}
        if max_uses is not None:
            params["max_uses"] = int(max_uses)
        if allowed_domains:
            params["allowed_domains"] = list(allowed_domains)
        if blocked_domains:
            params["blocked_domains"] = list(blocked_domains)
        if user_location:
            params["user_location"] = dict(user_location)

        return _marker("web_search", params)

    @staticmethod
    def web_fetch(
        *,
        max_uses: int | None = None,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        citations: dict[str, Any] | bool | None = None,
        max_content_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Anthropic-hosted **web fetch** tool (beta).

        Automatically opts the request into the ``web-fetch-*`` beta
        header — callers do not need to set it manually.
        """
        if allowed_domains and blocked_domains:
            raise ValueError(
                "AnthropicTool.web_fetch: allowed_domains and blocked_domains "
                "are mutually exclusive."
            )

        params: dict[str, Any] = {}
        if max_uses is not None:
            params["max_uses"] = int(max_uses)
        if allowed_domains:
            params["allowed_domains"] = list(allowed_domains)
        if blocked_domains:
            params["blocked_domains"] = list(blocked_domains)
        if max_content_tokens is not None:
            params["max_content_tokens"] = int(max_content_tokens)
        if citations is not None:
            if isinstance(citations, bool):
                params["citations"] = {"enabled": citations}
            else:
                params["citations"] = dict(citations)

        return _marker("web_fetch", params)

    @staticmethod
    def code_execution() -> dict[str, Any]:
        """Anthropic-hosted Python **code execution** tool (beta).

        Automatically opts the request into the ``code-execution-*``
        beta header.
        """
        return _marker("code_execution", {})


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _marker(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a NucleusIQ-side marker dict the converter understands."""
    return {"type": _MARKER_TYPE, "name": name, "params": params}


def is_native_marker(spec: dict[str, Any]) -> bool:
    """Return True when *spec* is an ``AnthropicTool.*()`` marker."""
    if not isinstance(spec, dict):
        return False
    if spec.get("type") != _MARKER_TYPE:
        return False
    return spec.get("name") in NATIVE_TOOL_TYPES


def native_name(spec: dict[str, Any]) -> str | None:
    """Return the native tool name (``web_search`` / …) for a marker, else None."""
    if is_native_marker(spec):
        return str(spec.get("name") or "") or None
    return None


def required_beta_headers(tool_specs: list[dict[str, Any]] | None) -> list[str]:
    """Collect all beta headers required by the native tools in *tool_specs*."""
    if not tool_specs:
        return []
    needed: list[str] = []
    for spec in tool_specs:
        if not isinstance(spec, dict):
            continue
        name = native_name(spec)
        if name is None:
            continue
        header = NATIVE_TOOL_BETA_HEADERS.get(name)
        if header and header not in needed:
            needed.append(header)
    return needed


def marker_to_wire(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert an :class:`AnthropicTool` marker to Anthropic's wire shape.

    Returns the input unchanged when *spec* is not a marker (so the
    converter can keep its current pass-through behaviour for
    user-supplied raw native specs).
    """
    if not is_native_marker(spec):
        return dict(spec)
    name = str(spec.get("name") or "")
    wire_type = NATIVE_TOOL_WIRE_TYPES.get(name)
    if wire_type is None:
        # Unknown name on a marker dict — drop the marker shape but keep
        # what the user provided so Anthropic returns a useful error.
        return {"name": name, **dict(spec.get("params") or {})}
    out: dict[str, Any] = {"type": wire_type, "name": name}
    params = spec.get("params")
    if isinstance(params, dict):
        for k, v in params.items():
            if v is None:
                continue
            out[k] = v
    return out


__all__ = [
    "AnthropicTool",
    "NATIVE_TOOL_TYPES",
    "NATIVE_TOOL_WIRE_TYPES",
    "NATIVE_TOOL_BETA_HEADERS",
    "is_native_marker",
    "native_name",
    "required_beta_headers",
    "marker_to_wire",
]
