"""Tests for the MCP exception hierarchy."""

from __future__ import annotations

import pytest
from nucleusiq.errors.base import NucleusIQError
from nucleusiq.tools.errors import ToolError, ToolExecutionError
from nucleusiq_mcp.exceptions import (
    MCPAuthError,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPToolError,
)


class TestHierarchy:
    """MCPError IS-A ToolError IS-A NucleusIQError so existing handlers work."""

    @pytest.mark.parametrize(
        "cls",
        [MCPError, MCPConnectionError, MCPAuthError, MCPTimeoutError, MCPProtocolError],
    )
    def test_inherits_tool_error(self, cls):
        exc = cls("boom")
        assert isinstance(exc, ToolError)
        assert isinstance(exc, NucleusIQError)

    def test_tool_error_inherits_tool_execution_error(self):
        exc = MCPToolError("boom")
        assert isinstance(exc, ToolExecutionError)
        assert isinstance(exc, ToolError)
        assert isinstance(exc, NucleusIQError)


class TestMCPError:
    def test_basic_message(self):
        exc = MCPError("connection failed", server="github")
        assert "connection failed" in str(exc)
        assert exc.server == "github"

    def test_repr_includes_server_and_tool(self):
        exc = MCPError("failed", server="slack", tool_name="search")
        r = repr(exc)
        assert "slack" in r
        assert "search" in r

    def test_repr_when_server_is_none(self):
        exc = MCPError("failed")
        r = repr(exc)
        assert "server=" not in r

    def test_carries_original_error(self):
        cause = RuntimeError("underlying")
        exc = MCPError("wrap", original_error=cause)
        assert exc.original_error is cause

    def test_args_snapshot(self):
        exc = MCPError("failed", args_snapshot={"q": "search"})
        assert exc.args_snapshot == {"q": "search"}


class TestMCPAuthError:
    def test_status_code(self):
        exc = MCPAuthError("forbidden", status_code=403)
        assert exc.status_code == 403

    def test_default_status_code_is_none(self):
        exc = MCPAuthError("missing token")
        assert exc.status_code is None


class TestMCPToolError:
    def test_content_text_carried(self):
        exc = MCPToolError(
            "tool returned error",
            server="github",
            content_text="rate limit exceeded",
            tool_name="search",
            args_snapshot={"q": "rust"},
        )
        assert exc.content_text == "rate limit exceeded"
        assert exc.server == "github"
        assert exc.tool_name == "search"
        assert exc.args_snapshot == {"q": "rust"}

    def test_no_content_text(self):
        exc = MCPToolError("oops")
        assert exc.content_text is None
