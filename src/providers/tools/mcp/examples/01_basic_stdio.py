"""Example 01: connect a local MCP server over stdio.

Demonstrates the simplest path — point ``MCPTool`` at an MCP server you
run as a subprocess (Node, Python, native binary, ...).  ``transport``
is auto-detected as STDIO because the string is not a URL.

Requirements:
    pip install nucleusiq-mcp
    # Plus any stdio MCP server.  The official "everything" demo server
    # is great for kicking the tyres:
    #   npm install -g @modelcontextprotocol/server-everything
    # (or use ``npx -y`` and let it download on demand)
"""

from __future__ import annotations

import asyncio
import logging

from nucleusiq.agents.agent import Agent
from nucleusiq.prompts.zero_shot import ZeroShotPrompt

from nucleusiq_mcp import MCPTool


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    agent = Agent(
        name="explorer",
        role="Explorer",
        objective="Demonstrate MCP stdio tool discovery",
        prompt=ZeroShotPrompt().configure(
            system="You are a tool explorer.",
            user="List the tools you have access to.",
        ),
        llm=None,  # no LLM needed — we just enumerate tools
        tools=[
            MCPTool(
                "npx -y @modelcontextprotocol/server-everything",
                name="everything",
            ),
        ],
    )

    try:
        await agent.initialize()
        print(f"\n✓ Discovered {len(agent.tools)} tool(s):\n")
        for t in agent.tools:
            print(f"  • {t.name:30s} {t.description[:70]}")
    finally:
        # Always disconnect adapters so the subprocess is reaped cleanly.
        await agent._cleanup_expandable_tools()


if __name__ == "__main__":
    asyncio.run(main())
