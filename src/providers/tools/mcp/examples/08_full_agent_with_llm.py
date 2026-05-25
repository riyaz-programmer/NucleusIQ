"""Example 08: full end-to-end agent — LLM + MCP tools.

This example is the **canonical** usage pattern: a NucleusIQ Agent
with an OpenAI LLM that calls tools fetched from an MCP server.

Demonstrates:
  * MCP tools are indistinguishable from local tools to the LLM
  * The Agent's tool-loop selects, calls, observes, and synthesizes
  * Telemetry sees ``source="mcp://..."`` on each MCP tool call

Requirements:
    pip install nucleusiq nucleusiq-openai nucleusiq-mcp
    export OPENAI_API_KEY=sk-...
    # plus any stdio MCP server, e.g.:
    #   npm install -g @modelcontextprotocol/server-everything
"""

from __future__ import annotations

import asyncio
import os


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run this example.")
        return

    # Imports kept lazy so the file is importable without the LLM dep.
    from nucleusiq.agents.agent import Agent
    from nucleusiq.prompts.zero_shot import ZeroShotPrompt

    try:
        from nucleusiq_openai import OpenAITool  # type: ignore[import-not-found]
    except ImportError:
        # Fall back to whatever LLM wrapper the user has.
        from nucleusiq.llms.openai import OpenAIChatLLM as OpenAITool  # type: ignore

    from nucleusiq_mcp import MCPTool

    agent = Agent(
        name="assistant",
        role="Helpful assistant",
        objective="Answer the user's question using available tools",
        prompt=ZeroShotPrompt().configure(
            system=(
                "You are a helpful assistant. "
                "Use the tools available to you whenever they help."
            ),
            user="Please echo back the message 'hello from MCP' using the echo tool.",
        ),
        llm=OpenAITool(model="gpt-4o-mini"),
        tools=[
            MCPTool(
                "npx -y @modelcontextprotocol/server-everything",
                name="everything",
            ),
        ],
    )

    try:
        await agent.initialize()
        result = await agent.execute()
        print("\n=== Final answer ===")
        print(result.final_output)

        print("\n=== Tool calls ===")
        for tc in result.tool_calls:
            print(
                f"  {tc.tool_name}({tc.args}) -> {str(tc.result)[:60]}  "
                f"[source={tc.source}]"
            )
    finally:
        await agent._cleanup_expandable_tools()


if __name__ == "__main__":
    asyncio.run(main())
