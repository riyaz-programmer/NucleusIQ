"""Example 02: connect a remote MCP server over Streamable HTTP with auth.

Demonstrates:
  * Streamable HTTP transport (auto-detected from the URL)
  * ``EnvAuth`` — bearer token from an env var (rotation-friendly)
  * Filtering tools with a decorator-style predicate (``@mcp_tool_filter``)
  * Composing filters with ``MCPToolset.all_of(...)``
  * Renaming tools via ``prefix=`` for clear telemetry

Requirements:
    pip install nucleusiq-mcp
    export MY_MCP_URL=https://mcp.example.com/api
    export MY_MCP_TOKEN=...
"""

from __future__ import annotations

import asyncio
import os

from nucleusiq.agents.agent import Agent
from nucleusiq.prompts.zero_shot import ZeroShotPrompt
from nucleusiq_mcp import EnvAuth, MCPTool, MCPToolset, mcp_tool_filter


@mcp_tool_filter(name="read_only", description="Only read/list/get tools")
def read_only(spec):
    return spec.name.startswith(("get_", "list_", "search_", "read_"))


@mcp_tool_filter(name="not_admin", description="Block anything called *admin*")
def not_admin(spec):
    return "admin" not in spec.name.lower()


async def main() -> None:
    url = os.environ.get("MY_MCP_URL")
    if not url:
        print("Set MY_MCP_URL and MY_MCP_TOKEN to run this example.")
        return

    agent = Agent(
        name="researcher",
        role="Researcher",
        objective="Demonstrate MCP HTTP + auth + filtering",
        prompt=ZeroShotPrompt().configure(system="You are a researcher."),
        llm=None,
        tools=[
            MCPTool(
                url,
                auth=EnvAuth("MY_MCP_TOKEN"),
                tool_filter=MCPToolset.all_of(read_only, not_admin),
                prefix="mcp",  # → "mcp_search", "mcp_get_user", ...
                on_collision="auto_prefix",
                timeout_seconds=15.0,
            ),
        ],
    )

    try:
        await agent.initialize()
        print(f"\n✓ Connected. {len(agent.tools)} tool(s) registered:\n")
        for t in agent.tools[:10]:
            print(f"  • {t.name}")
    finally:
        await agent._cleanup_expandable_tools()


if __name__ == "__main__":
    asyncio.run(main())
