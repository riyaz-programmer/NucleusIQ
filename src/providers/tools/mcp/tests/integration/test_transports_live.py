"""Live transport tests against ``@modelcontextprotocol/server-everything``.

These exercise the *full stack* — config auto-detection, transport open,
MCP handshake, ``list_tools``, ``call_tool`` — for **all three**
transports we support (stdio, Streamable HTTP, SSE).

Run with::

    pytest -m integration tests/integration/test_transports_live.py
"""

from __future__ import annotations

import pytest

from nucleusiq_mcp import MCPSession, MCPTool
from nucleusiq_mcp.config import MCPServerConfig, MCPTransport
from tests.integration.conftest import requires_node

pytestmark = [pytest.mark.integration, requires_node, pytest.mark.asyncio]


# ====================================================================== #
# STDIO transport                                                          #
# ====================================================================== #


class TestStdioTransport:
    async def test_session_lifecycle(self, stdio_command: str):
        cfg = MCPServerConfig.build(stdio_command, name="everything-stdio")
        assert cfg.transport == MCPTransport.STDIO

        async with MCPSession(cfg) as sess:
            tools = await sess.list_tools()
            assert len(tools) > 0
            assert any(t.name == "echo" for t in tools), [t.name for t in tools]

    async def test_call_tool_echo(self, stdio_command: str):
        async with MCPSession(
            MCPServerConfig.build(stdio_command, name="everything-stdio")
        ) as sess:
            result = await sess.call_tool("echo", {"message": "hello-stdio"})
            assert not result.is_error
            text = result.join_text()
            assert "hello-stdio" in text

    async def test_mcptool_facade(self, stdio_command: str):
        """End-to-end through ``MCPTool`` — the public API users see."""
        tool = MCPTool(stdio_command, name="everything-stdio")
        try:
            await tool.connect()
            bound = await tool.expand()
            assert len(bound) > 0
            assert all(t.source.startswith("mcp://server=") for t in bound)
            assert all("(path=A)" in t.source for t in bound)
        finally:
            await tool.disconnect()


# ====================================================================== #
# Streamable HTTP transport                                                #
# ====================================================================== #


class TestStreamableHttpTransport:
    async def test_session_lifecycle(self, http_server: str):
        cfg = MCPServerConfig.build(http_server, name="everything-http")
        assert cfg.transport == MCPTransport.STREAMABLE_HTTP

        async with MCPSession(cfg) as sess:
            tools = await sess.list_tools()
            assert len(tools) > 0

    async def test_call_tool(self, http_server: str):
        async with MCPSession(
            MCPServerConfig.build(http_server, name="everything-http")
        ) as sess:
            result = await sess.call_tool("echo", {"message": "hello-http"})
            assert not result.is_error
            assert "hello-http" in result.join_text()


# ====================================================================== #
# SSE transport (legacy, but still widely deployed)                        #
# ====================================================================== #


class TestSseTransport:
    async def test_session_lifecycle(self, sse_server: str):
        cfg = MCPServerConfig.build(
            sse_server, name="everything-sse", transport=MCPTransport.SSE
        )
        assert cfg.transport == MCPTransport.SSE

        async with MCPSession(cfg) as sess:
            tools = await sess.list_tools()
            assert len(tools) > 0

    async def test_call_tool(self, sse_server: str):
        cfg = MCPServerConfig.build(
            sse_server, name="everything-sse", transport=MCPTransport.SSE
        )
        async with MCPSession(cfg) as sess:
            result = await sess.call_tool("echo", {"message": "hello-sse"})
            assert not result.is_error
            assert "hello-sse" in result.join_text()


# ====================================================================== #
# Cross-cutting: ping() + on_connect_failure                                #
# ====================================================================== #


class TestPhase2Hardening:
    async def test_ping_against_live_server(self, stdio_command: str):
        tool = MCPTool(stdio_command, name="everything-stdio")
        try:
            await tool.connect()
            assert await tool.ping() is True
        finally:
            await tool.disconnect()

    async def test_on_connect_failure_skip_on_bad_stdio(self):
        # A command that does not exist on the system.  With skip
        # policy, the tool degrades gracefully and expand() returns [].
        tool = MCPTool(
            "definitely-not-a-real-mcp-binary",
            on_connect_failure="skip",
            health_check=False,
        )
        await tool.connect()  # must not raise
        assert tool._connect_skipped is True
        assert await tool.expand() == []

    async def test_on_connect_failure_raise_on_bad_stdio(self):
        tool = MCPTool(
            "definitely-not-a-real-mcp-binary",
            on_connect_failure="raise",
            health_check=False,
        )
        with pytest.raises(Exception):  # noqa: B017 — broad on purpose
            await tool.connect()
