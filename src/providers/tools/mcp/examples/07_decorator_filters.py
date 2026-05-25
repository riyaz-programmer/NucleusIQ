"""Example 07: decorator-style tool filters and ``MCPToolset`` composition.

Demonstrates the small DSL we offer for filtering MCP tools:

    @mcp_tool_filter         — annotate a predicate with metadata so
                               telemetry knows *why* a tool was kept
    MCPToolset.all_of(...)   — AND-compose filters
    MCPToolset.any_of(...)   — OR-compose filters

The same predicates can be reused across many ``MCPTool`` instances —
they're plain callables.
"""

from __future__ import annotations

from nucleusiq_mcp import MCPTool, MCPToolset, mcp_tool_filter

# --------------------------------------------------------------------- #
# A small library of named, reusable predicates                          #
# --------------------------------------------------------------------- #


@mcp_tool_filter(name="readonly", description="Read-only verbs only")
def readonly(spec):
    """Allow tools whose name starts with a read verb."""
    return spec.name.startswith(("get_", "list_", "search_", "read_", "find_"))


@mcp_tool_filter(name="public", description="No tools tagged 'internal'")
def public(spec):
    annotations = spec.annotations or {}
    return not annotations.get("internal", False)


@mcp_tool_filter(name="small_schema", description="Schema with <= 5 args")
def small_schema(spec):
    props = (spec.input_schema or {}).get("properties") or {}
    return len(props) <= 5


# --------------------------------------------------------------------- #
# Compose them in different ways                                         #
# --------------------------------------------------------------------- #


SAFE_BROWSE = MCPToolset.all_of(readonly, public)
"""Conservative — read-only AND not internal."""

EITHER_PUBLIC_OR_SMALL = MCPToolset.any_of(public, small_schema)
"""Permissive — public OR small enough to be cheap."""


def main() -> None:
    """We construct (but do not initialize) MCPTool instances to keep
    the example pure — no network, no subprocesses.  In a real agent
    you'd just pass these tools= entries and call ``agent.initialize``.
    """
    safe = MCPTool(
        "https://mcp.example.com/api",
        auth="dummy-token",
        tool_filter=SAFE_BROWSE,
    )
    permissive = MCPTool(
        "https://mcp.example.com/api",
        auth="dummy-token",
        tool_filter=EITHER_PUBLIC_OR_SMALL,
    )

    print("Defined two MCPTool instances:")
    print(f"  • {safe!r}  with filter = {SAFE_BROWSE!r}")
    print(f"  • {permissive!r}  with filter = {EITHER_PUBLIC_OR_SMALL!r}")
    print("\nReusable filters:")
    for f in (readonly, public, small_schema):
        print(f"  • @{f.filter_name}: {f.filter_description}")


if __name__ == "__main__":
    main()
