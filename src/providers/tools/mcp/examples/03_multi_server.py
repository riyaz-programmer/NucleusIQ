"""Example 03: multiple MCP servers in a single agent.

Demonstrates:
  * Three MCP servers (one stdio + two HTTP) in the same agent
  * Parallel connection — agent.initialize() opens all three concurrently
  * Per-server tool prefix to keep names unambiguous
  * ``on_collision="auto_prefix"`` to absorb accidental name overlaps

Requirements:
    pip install nucleusiq-mcp
    export GITHUB_TOKEN=ghp_...
    export SLACK_TOKEN=xoxb-...
"""

from __future__ import annotations

import asyncio
import os

from nucleusiq.agents.agent import Agent
from nucleusiq.prompts.zero_shot import ZeroShotPrompt

from nucleusiq_mcp import EnvAuth, MCPTool


async def main() -> None:
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("SLACK_TOKEN"):
        print("Set GITHUB_TOKEN and SLACK_TOKEN to run this example.")
        return

    agent = Agent(
        name="multi-mcp",
        role="Multi-MCP integrator",
        objective="Wire several MCP servers into one agent",
        prompt=ZeroShotPrompt().configure(system="You are an integrator."),
        llm=None,
        tools=[
            # Local GitHub MCP (stdio) — token passed via subprocess env
            MCPTool(
                "npx -y @modelcontextprotocol/server-github",
                env={"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]},
                prefix="gh",
            ),
            # Remote Slack MCP (HTTP, auto-detected) — env-based bearer
            MCPTool(
                "https://mcp.slack.com/api",
                auth=EnvAuth("SLACK_TOKEN"),
                prefix="slack",
            ),
            # Internal filesystem MCP — extra HTTP header for tenant routing
            MCPTool(
                "https://files.internal.example.com/mcp",
                auth=EnvAuth("FILES_TOKEN", required=False),
                headers={"X-Tenant": "acme"},
                prefix="files",
                on_collision="auto_prefix",
            ),
        ],
    )

    try:
        await agent.initialize()
        # Group by prefix for readable output
        by_prefix: dict[str, list[str]] = {}
        for t in agent.tools:
            head = t.name.split("_", 1)[0]
            by_prefix.setdefault(head, []).append(t.name)

        print(
            f"\n✓ Initialized {len(agent.tools)} tools from {len(by_prefix)} server(s):\n"
        )
        for prefix, names in sorted(by_prefix.items()):
            print(f"  [{prefix}] {len(names)} tools")
            for n in names[:5]:
                print(f"      • {n}")
            if len(names) > 5:
                print(f"      ... +{len(names) - 5} more")
    finally:
        await agent._cleanup_expandable_tools()


if __name__ == "__main__":
    asyncio.run(main())
