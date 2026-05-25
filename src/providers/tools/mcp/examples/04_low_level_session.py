"""Example 04: drive ``MCPSession`` directly (no Agent).

Demonstrates how to use ``nucleusiq-mcp`` outside the NucleusIQ Agent
loop — useful for:
  * Scripts that just want to inspect an MCP server
  * One-shot tool invocations
  * Integration tests

``MCPSession`` is the building block.  ``MCPTool`` wraps it for the
Agent contract; you can also call it yourself.
"""

from __future__ import annotations

import asyncio
import json

from nucleusiq_mcp import MCPServerConfig, MCPSession, MCPTransport


async def main() -> None:
    config = MCPServerConfig.build(
        server="npx -y @modelcontextprotocol/server-everything",
        transport=MCPTransport.STDIO,
        name="everything",
        timeout_seconds=20.0,
    )

    async with MCPSession(config) as session:
        # 1) Discovery
        tools = await session.list_tools()
        print(f"\n✓ Server advertises {len(tools)} tool(s):")
        for t in tools[:5]:
            print(f"  • {t.name:25s} — {t.description[:60]}")

        # 2) Invoke one of them.  ``echo`` is reliable in the demo server.
        echo = next((t for t in tools if t.name == "echo"), None)
        if echo:
            result = await session.call_tool("echo", {"message": "hello"})
            print("\n✓ echo() returned:")
            print(
                json.dumps(
                    {"text": result.join_text(), "is_error": result.is_error},
                    indent=2,
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
