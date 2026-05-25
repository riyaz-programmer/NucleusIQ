"""Tests for MCPBoundTool."""

from __future__ import annotations

import pytest
from nucleusiq.tools.errors import ToolExecutionError
from nucleusiq_mcp.bound_tool import MCPBoundTool, format_result
from nucleusiq_mcp.exceptions import MCPToolError
from nucleusiq_mcp.models import MCPContent, MCPToolResult, MCPToolSpec

from tests.unit.conftest import FakeMCPSession

# ====================================================================== #
# format_result strategy                                                   #
# ====================================================================== #


class TestFormatResult:
    def test_text_only_returns_joined_text(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="hello"),
                MCPContent(kind="text", text="world"),
            ]
        )
        assert format_result(r) == "hello\nworld"

    def test_empty_returns_empty_string(self):
        assert format_result(MCPToolResult()) == ""

    def test_structured_wins(self):
        r = MCPToolResult(
            content=[MCPContent(kind="text", text="legacy")],
            structured={"items": [1, 2, 3]},
        )
        assert format_result(r) == {"items": [1, 2, 3]}

    def test_multimodal_preserves_all(self):
        r = MCPToolResult(
            content=[
                MCPContent(kind="text", text="x"),
                MCPContent(kind="image", data="b64", mime_type="image/png"),
            ]
        )
        out = format_result(r)
        assert isinstance(out, dict)
        assert len(out["content"]) == 2
        assert out["content"][0]["kind"] == "text"
        assert out["content"][1]["kind"] == "image"
        assert out["content"][1]["mime_type"] == "image/png"


# ====================================================================== #
# MCPBoundTool                                                             #
# ====================================================================== #


@pytest.mark.asyncio
class TestMCPBoundTool:
    async def test_initialize_is_noop(self, http_config):
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(name="search", description="d")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        await t.initialize()  # must not raise

    async def test_execute_returns_text(self, http_config):
        sess = FakeMCPSession(
            config=http_config,
            results={
                "search": MCPToolResult(
                    content=[MCPContent(kind="text", text="result")]
                )
            },
        )
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        out = await t.execute(q="rust")
        assert out == "result"
        assert sess.calls == [("search", {"q": "rust"})]

    async def test_execute_with_renamed_tool_uses_remote_name_in_rpc(self, http_config):
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="example_search")
        await t.execute(q="x")
        # RPC uses the *remote* name, not the final NucleusIQ name.
        assert sess.calls[0][0] == "search"
        assert t.name == "example_search"
        assert t.remote_name == "search"

    async def test_execute_raises_mcp_tool_error_on_is_error(self, http_config):
        sess = FakeMCPSession(
            config=http_config,
            results={
                "search": MCPToolResult(
                    content=[MCPContent(kind="text", text="quota exceeded")],
                    is_error=True,
                )
            },
        )
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        with pytest.raises(MCPToolError) as exc_info:
            await t.execute(q="x")
        assert exc_info.value.content_text == "quota exceeded"
        assert exc_info.value.args_snapshot == {"q": "x"}
        # MCPToolError IS-A ToolExecutionError (LSP).
        assert isinstance(exc_info.value, ToolExecutionError)

    async def test_get_spec_returns_dict(self, http_config):
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(
            name="search",
            description="Search",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        out = t.get_spec()
        assert out["name"] == "search"
        assert "q" in out["parameters"]["properties"]

    async def test_get_spec_returns_defensive_copy(self, http_config):
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        out1 = t.get_spec()
        out1["name"] = "MUTATED"
        out2 = t.get_spec()
        assert out2["name"] == "search"

    async def test_repr_includes_names(self, http_config):
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="example_search")
        r = repr(t)
        assert "example_search" in r
        assert "search" in r
        assert "example" in r  # server label

    async def test_source_label_set_for_telemetry(self, http_config):
        """The ``source`` attr is consumed by NucleusIQ's tracer to
        attribute MCP tool calls."""
        sess = FakeMCPSession(config=http_config)
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        assert t.source == f"mcp://server={sess.server_name} (path=A)"
        assert "(path=A)" in t.source  # Path A = client-side adapter

    async def test_structured_result_returned_directly(self, http_config):
        sess = FakeMCPSession(
            config=http_config,
            results={
                "search": MCPToolResult(
                    content=[MCPContent(kind="text", text="legacy")],
                    structured={"count": 7},
                )
            },
        )
        await sess.connect()
        spec = MCPToolSpec(name="search")
        t = MCPBoundTool(session=sess, tool_spec=spec, final_name="search")
        assert await t.execute() == {"count": 7}
