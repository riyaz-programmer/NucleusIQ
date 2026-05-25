"""End-to-end test: NucleusIQ Agent + Anthropic Claude + MCP tools.

Proves the **canonical** user story:

    Agent(llm=BaseAnthropic(...), tools=[MCPTool(...)]).execute()

works the same as if the MCP tools were hand-written ``BaseTool``
subclasses.  Confirms:

* MCP tools are picked up by ``Agent.initialize`` (Phase 0 hook)
* They appear in Claude's tool list (Path A — client-side adapter)
* The tracer records each call with the ``source`` label we set on
  ``MCPBoundTool`` (``mcp://server=... (path=A)``)

Run with::

    pytest -m integration tests/integration/test_with_anthropic.py

The test is silently skipped when ``ANTHROPIC_API_KEY`` is missing.
We deliberately do not log the key.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

# Load the project's .env so the key is available before any provider
# module reads ``os.environ``.  This means subsequent imports must
# follow — silence E402 for the rest of the file.
load_dotenv()

# ruff: noqa: E402

from nucleusiq.agents.agent import Agent
from nucleusiq.agents.config.agent_config import AgentConfig
from nucleusiq.agents.task import Task
from nucleusiq.prompts.zero_shot import ZeroShotPrompt
from nucleusiq_mcp import MCPTool

from tests.integration.conftest import requires_node

pytestmark = [pytest.mark.integration, requires_node, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def anthropic_llm():
    """Build a small, fast Claude model — skip if no key."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set; skipping Anthropic integration tests")

    from nucleusiq_anthropic import BaseAnthropic

    # Claude Haiku 4.5 — fastest, cheapest, supports tools.
    # Override with ``ANTHROPIC_TEST_MODEL`` if your account
    # provisioned only other model snapshots.
    model = os.environ.get("ANTHROPIC_TEST_MODEL", "claude-haiku-4-5")
    return BaseAnthropic(model_name=model, temperature=0.0)


class TestAnthropicWithMCP:
    async def test_agent_lists_mcp_tools_via_claude(self, anthropic_llm, stdio_command):
        """Agent boots, MCP server is connected, tools show up in
        ``agent.tools`` and Claude can see them (we don't run the LLM
        here — that's the next test — only confirm wiring)."""

        agent = Agent(
            name="mcp-explorer",
            role="Explorer",
            objective="Discover available MCP tools",
            prompt=ZeroShotPrompt().configure(system="You discover tools."),
            llm=anthropic_llm,
            tools=[MCPTool(stdio_command, name="everything")],
        )
        try:
            await agent.initialize()
            # Expanded list should be non-empty and contain at least the
            # well-known reference tools.
            assert len(agent.tools) > 0
            names = {t.name for t in agent.tools}
            assert "echo" in names or any("echo" in n for n in names), names

            # Every MCP-backed tool carries the source label.
            mcp_sources = [
                getattr(t, "source", None)
                for t in agent.tools
                if getattr(t, "source", None)
            ]
            assert all("mcp://" in s for s in mcp_sources)
            assert all("(path=A)" in s for s in mcp_sources)
        finally:
            await agent._cleanup_expandable_tools()

    async def test_bound_mcp_tool_carries_source_label(
        self, anthropic_llm, stdio_command
    ):
        """Lower-level: confirm the MCP-backed BaseTool placed on the
        agent carries the ``source`` label the tracer uses for
        attribution.  This does NOT need the LLM to actually pick the
        tool, which is non-deterministic across Claude versions.
        """
        agent = Agent(
            name="echo-bot",
            role="Tool-calling assistant",
            objective="Use the echo tool",
            prompt=ZeroShotPrompt().configure(system="Use tools when asked."),
            llm=anthropic_llm,
            tools=[
                MCPTool(stdio_command, name="everything", include_tools=["echo"]),
            ],
        )
        try:
            await agent.initialize()
            echo_tools = [t for t in agent.tools if t.name == "echo"]
            assert echo_tools, [t.name for t in agent.tools]
            src = getattr(echo_tools[0], "source", None)
            assert src and src.startswith("mcp://"), src
            assert "(path=A)" in src, src
        finally:
            await agent._cleanup_expandable_tools()

    async def test_claude_invokes_mcp_echo_tool(self, anthropic_llm, stdio_command):
        """Full loop: Claude is asked to use the ``echo`` MCP tool and
        we verify the trace records a tool call with the MCP source.

        Note:  Claude's decision to actually invoke a tool depends on
        prompt clarity AND model behavior.  We use a very explicit
        "math via tool" framing because mathematical tasks are tools
        the model reliably delegates to.
        """
        # The reference server names its sum tool ``get-sum``.  Many
        # tool-call schemas don't allow dashes in identifiers, so we
        # rename it as we expose it to Claude.
        agent = Agent(
            name="adder",
            role="Tool-calling math assistant",
            objective="Compute a sum using the add tool",
            prompt=ZeroShotPrompt().configure(
                system=(
                    "You are a calculator assistant. "
                    "You MUST use the available 'add' tool to compute "
                    "sums.  Do not do mental arithmetic.  After "
                    "receiving the tool result, report the answer in "
                    "plain text."
                ),
            ),
            llm=anthropic_llm,
            tools=[
                MCPTool(
                    stdio_command,
                    name="everything",
                    include_tools=["get-sum"],
                    rename={"get-sum": "add"},
                ),
            ],
            config=AgentConfig(enable_tracing=True),
        )
        try:
            await agent.initialize()
            assert any(t.name == "add" for t in agent.tools), [
                t.name for t in agent.tools
            ]

            task = Task(
                id="add-1",
                objective="What is 6789 plus 2345? Use the add tool.",
            )
            result = await agent.execute(task)
            assert result is not None

            output_str = str(result.output or "")
            tool_calls = tuple(result.tool_calls or ())
            print("\n--- agent result ---")
            print(f"status         : {result.status}")
            print(f"output (head)  : {output_str[:200]!r}")
            print(f"tool_call count: {len(tool_calls)}")
            for tc in tool_calls:
                print(
                    f"  - {tc.tool_name}({tc.args}) => "
                    f"success={tc.success} source={tc.source!r}"
                )
            print("--- end ---\n")

            # 6789 + 2345 = 9134 — must appear somewhere in the answer.
            assert "9134" in output_str, output_str

            # The tracer should record the MCP call labelled with our source.
            assert any(
                tc.tool_name == "add"
                and (tc.source or "").startswith("mcp://")
                and "(path=A)" in (tc.source or "")
                for tc in tool_calls
            ), [(tc.tool_name, tc.source) for tc in tool_calls]
        finally:
            await agent._cleanup_expandable_tools()
