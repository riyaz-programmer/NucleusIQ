"""Tests for the ExpandableTool protocol and Agent integration.

These tests use mock adapters and DO NOT depend on any external MCP / A2A
package.  They guarantee the core contract works for any adapter package.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from nucleusiq.tools import BaseTool, ExpandableTool

# ============================================================
# Fixtures / Helpers — pure-Python mock adapters
# ============================================================


class _MockBoundTool(BaseTool):
    """Minimal BaseTool used by the mock adapter."""

    def __init__(self, name: str, description: str = "mock") -> None:
        super().__init__(name=name, description=description)

    async def initialize(self) -> None:
        return None

    async def execute(self, **kwargs: Any) -> Any:
        return {"called": self.name, "kwargs": kwargs}

    def get_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }


class _MockAdapter:
    """Mock ExpandableTool — duck-typed to satisfy the protocol."""

    def __init__(
        self,
        tool_names: list[str],
        *,
        prefix: str | None = None,
        on_collision: str = "auto_prefix",
        connect_should_fail: bool = False,
        disconnect_should_fail: bool = False,
    ) -> None:
        self.tool_names = tool_names
        self.prefix = prefix
        self.on_collision = on_collision
        self.connect_should_fail = connect_should_fail
        self.disconnect_should_fail = disconnect_should_fail
        self.connect_calls = 0
        self.expand_calls = 0
        self.disconnect_calls = 0
        self.last_existing_names: set[str] | None = None

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.connect_should_fail:
            raise RuntimeError(f"connect failed for adapter prefix={self.prefix!r}")

    async def expand(
        self, existing_names: set[str] | None = None
    ) -> list[BaseTool]:
        self.expand_calls += 1
        self.last_existing_names = (
            set(existing_names) if existing_names is not None else None
        )
        names = list(self.tool_names)
        if self.prefix:
            names = [f"{self.prefix}_{n}" for n in names]
        elif existing_names and self.on_collision == "auto_prefix":
            renamed = []
            for n in names:
                renamed.append(f"{self.prefix or 'mock'}_{n}" if n in existing_names else n)
            names = renamed
        return [_MockBoundTool(name=n) for n in names]

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.disconnect_should_fail:
            raise RuntimeError(f"disconnect failed for adapter prefix={self.prefix!r}")


# ============================================================
# Protocol tests — pure contract
# ============================================================


class TestExpandableToolProtocol:
    def test_protocol_is_runtime_checkable(self):
        adapter = _MockAdapter(tool_names=["a", "b"])
        assert isinstance(adapter, ExpandableTool)

    def test_protocol_rejects_objects_missing_methods(self):
        class Incomplete:
            async def connect(self) -> None:
                return None

        # Missing expand / disconnect — not an ExpandableTool.
        assert not isinstance(Incomplete(), ExpandableTool)

    def test_basetool_is_not_an_expandable_tool(self):
        # Sanity: a regular BaseTool must NOT satisfy the protocol, otherwise
        # Agent.initialize would try to call connect() on every tool.
        t = _MockBoundTool(name="x")
        assert not isinstance(t, ExpandableTool)

    @pytest.mark.asyncio
    async def test_mock_adapter_lifecycle(self):
        adapter = _MockAdapter(tool_names=["t1", "t2"])
        await adapter.connect()
        tools = await adapter.expand()
        assert [t.name for t in tools] == ["t1", "t2"]
        assert all(isinstance(t, BaseTool) for t in tools)
        await adapter.disconnect()
        assert adapter.connect_calls == adapter.disconnect_calls == 1


# ============================================================
# Agent.initialize() integration tests
# ============================================================


def _make_agent_with_tools(tools: list[Any]):
    """Build a minimal Agent for initialize() tests.

    We import here so this module imports cleanly even when the Agent
    machinery has heavy transitive deps; failures show up as test errors
    rather than collection errors.
    """
    from nucleusiq.agents.agent import Agent
    from nucleusiq.prompts.zero_shot import ZeroShotPrompt

    prompt = ZeroShotPrompt().configure(system="sys", user="user")
    return Agent(
        name="t",
        role="x",
        objective="y",
        prompt=prompt,
        llm=None,  # no LLM needed; we only test initialize
        tools=tools,
    )


@pytest.mark.asyncio
class TestAgentInitializeWithExpandableTools:
    async def test_initialize_with_single_adapter_expands_tools(self):
        adapter = _MockAdapter(tool_names=["alpha", "beta"])
        agent = _make_agent_with_tools([adapter])
        await agent.initialize()
        names = [t.name for t in agent.tools]
        assert sorted(names) == ["alpha", "beta"]
        assert adapter.connect_calls == 1
        assert adapter.expand_calls == 1

    async def test_initialize_with_mixed_adapters_and_direct_tools(self):
        adapter = _MockAdapter(tool_names=["mcp_x"])
        direct = _MockBoundTool(name="local")
        agent = _make_agent_with_tools([direct, adapter])
        await agent.initialize()
        names = sorted(t.name for t in agent.tools)
        assert names == ["local", "mcp_x"]

    async def test_initialize_passes_existing_names_to_expand(self):
        adapter = _MockAdapter(tool_names=["search"])
        direct = _MockBoundTool(name="local")
        agent = _make_agent_with_tools([direct, adapter])
        await agent.initialize()
        assert adapter.last_existing_names == {"local"}

    async def test_initialize_collision_auto_prefix(self):
        """When a direct tool already exists with the same name, the adapter's
        auto_prefix policy should rename its colliding tool."""
        adapter = _MockAdapter(
            tool_names=["search"], prefix=None, on_collision="auto_prefix"
        )
        direct = _MockBoundTool(name="search")
        agent = _make_agent_with_tools([direct, adapter])
        await agent.initialize()
        names = sorted(t.name for t in agent.tools)
        # original direct + auto-prefixed adapter result
        assert "search" in names
        assert "mock_search" in names

    async def test_initialize_parallel_connect(self):
        """Two adapters connect concurrently; total ordering is irrelevant
        but both must have been awaited before expand."""
        a1 = _MockAdapter(tool_names=["t_a"])
        a2 = _MockAdapter(tool_names=["t_b"])
        agent = _make_agent_with_tools([a1, a2])
        await agent.initialize()
        assert a1.connect_calls == 1
        assert a2.connect_calls == 1
        assert a1.expand_calls == 1
        assert a2.expand_calls == 1

    async def test_initialize_connect_failure_triggers_cleanup(self):
        good = _MockAdapter(tool_names=["g"])
        bad = _MockAdapter(tool_names=["b"], connect_should_fail=True)
        agent = _make_agent_with_tools([good, bad])
        with pytest.raises(RuntimeError, match="connect failed"):
            await agent.initialize()
        # The good adapter was disconnected during cleanup.
        assert good.disconnect_calls == 1

    async def test_initialize_parallel_failure_no_orphans(self):
        """With return_exceptions=True, slow successful connects still
        complete before we raise, so cleanup can disconnect them.

        Regression test for a bug where asyncio.gather propagated the
        first failure immediately, leaving sibling connects running as
        orphaned tasks until the process exited."""

        class SlowAdapter:
            def __init__(self, tool_names, *, delay=0.0, fail=False):
                self.tool_names = tool_names
                self.delay = delay
                self.fail = fail
                self.connect_calls = 0
                self.disconnect_calls = 0
                self.expand_calls = 0

            async def connect(self):
                await asyncio.sleep(self.delay)
                self.connect_calls += 1
                if self.fail:
                    raise RuntimeError("slow fail")

            async def expand(self, existing_names=None):
                self.expand_calls += 1
                return []  # never reached

            async def disconnect(self):
                self.disconnect_calls += 1

        slow = SlowAdapter(["s"], delay=0.05)
        bad = SlowAdapter(["b"], delay=0.0, fail=True)
        agent = _make_agent_with_tools([slow, bad])
        with pytest.raises(RuntimeError, match="slow fail"):
            await agent.initialize()
        # Critical: the slow adapter must have *finished* connecting
        # before we raised, and its disconnect must have been called.
        assert slow.connect_calls == 1, (
            "Slow adapter must have completed connect (else it is orphaned)"
        )
        assert slow.disconnect_calls == 1
        assert bad.disconnect_calls == 1  # idempotent no-op since never connected

    async def test_initialize_no_adapters_no_change(self):
        direct = _MockBoundTool(name="x")
        agent = _make_agent_with_tools([direct])
        await agent.initialize()
        assert agent.tools == [direct]

    async def test_initialize_empty_tools(self):
        agent = _make_agent_with_tools([])
        await agent.initialize()
        assert agent.tools == []


@pytest.mark.asyncio
class TestAgentCleanupExpandableTools:
    async def test_cleanup_calls_disconnect(self):
        adapter = _MockAdapter(tool_names=["x"])
        agent = _make_agent_with_tools([adapter])
        await agent.initialize()
        await agent._cleanup_expandable_tools()
        assert adapter.disconnect_calls == 1

    async def test_cleanup_is_idempotent(self):
        adapter = _MockAdapter(tool_names=["x"])
        agent = _make_agent_with_tools([adapter])
        await agent.initialize()
        await agent._cleanup_expandable_tools()
        await agent._cleanup_expandable_tools()  # safe second call
        # Adapter is removed after first cleanup, so second call is a no-op.
        assert adapter.disconnect_calls == 1

    async def test_cleanup_continues_after_failing_adapter(self):
        good = _MockAdapter(tool_names=["g"])
        bad = _MockAdapter(tool_names=["b"], disconnect_should_fail=True)
        agent = _make_agent_with_tools([good, bad])
        await agent.initialize()
        # Should NOT raise; the failing disconnect is logged and other
        # adapters still get cleaned up.
        await agent._cleanup_expandable_tools()
        assert good.disconnect_calls == 1
        assert bad.disconnect_calls == 1

    async def test_cleanup_with_no_adapters_is_noop(self):
        direct = _MockBoundTool(name="x")
        agent = _make_agent_with_tools([direct])
        await agent.initialize()
        await agent._cleanup_expandable_tools()  # no-op


# ============================================================
# ToolCallRecord.source field — backwards compatibility
# ============================================================


class TestToolCallRecordSourceField:
    def test_source_defaults_to_none(self):
        from nucleusiq.agents.agent_result import ToolCallRecord

        record = ToolCallRecord(tool_name="t")
        assert record.source is None

    def test_source_can_be_set(self):
        from nucleusiq.agents.agent_result import ToolCallRecord

        record = ToolCallRecord(
            tool_name="github_search_repos",
            source="mcp://github (path=A)",
        )
        assert record.source == "mcp://github (path=A)"

    def test_record_remains_frozen(self):
        from nucleusiq.agents.agent_result import ToolCallRecord
        from pydantic import ValidationError

        record = ToolCallRecord(tool_name="t")
        # Frozen model — pydantic raises ValidationError on assignment.
        with pytest.raises(ValidationError):
            record.source = "x"
