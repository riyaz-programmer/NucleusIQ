"""Shared fixtures and helpers for nucleusiq-mcp unit tests."""

from __future__ import annotations

from typing import Any

import pytest
from nucleusiq_mcp.config import MCPServerConfig
from nucleusiq_mcp.models import MCPContent, MCPToolResult, MCPToolSpec


class FakeMCPSession:
    """A drop-in MCPSession for tests that does not touch the SDK.

    Used in bound_tool / mcp_tool tests to validate the adapter logic
    without needing a live MCP server.
    """

    def __init__(
        self,
        *,
        config: MCPServerConfig,
        tools: list[MCPToolSpec] | None = None,
        results: dict[str, MCPToolResult] | None = None,
        list_should_raise: BaseException | None = None,
        call_should_raise: BaseException | None = None,
    ) -> None:
        self._config = config
        self._tools = list(tools or [])
        self._results = results or {}
        self._list_should_raise = list_should_raise
        self._call_should_raise = call_should_raise
        self.is_connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    @property
    def server_name(self) -> str:
        return self._config.name

    async def connect(self) -> None:
        self.connect_calls += 1
        self.is_connected = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.is_connected = False

    async def list_tools(self) -> list[MCPToolSpec]:
        if self._list_should_raise:
            raise self._list_should_raise
        return list(self._tools)

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> MCPToolResult:
        self.calls.append((tool_name, dict(arguments or {})))
        if self._call_should_raise:
            raise self._call_should_raise
        if tool_name in self._results:
            return self._results[tool_name]
        return MCPToolResult(content=[MCPContent(kind="text", text=f"ok:{tool_name}")])


@pytest.fixture
def http_config() -> MCPServerConfig:
    return MCPServerConfig.build("https://mcp.example.com/api", name="example")


@pytest.fixture
def stdio_config() -> MCPServerConfig:
    return MCPServerConfig.build("npx -y @org/server-x", name="server-x")
