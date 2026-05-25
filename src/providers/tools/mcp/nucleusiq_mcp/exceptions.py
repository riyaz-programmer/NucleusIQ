"""Exception hierarchy for the ``nucleusiq-mcp`` adapter package.

All exceptions ultimately inherit from
:class:`nucleusiq.errors.base.NucleusIQError` (via NucleusIQ's
:class:`~nucleusiq.tools.errors.ToolError`) so callers can catch *any*
NucleusIQ error with a single ``except NucleusIQError`` clause.

Hierarchy::

    nucleusiq.errors.NucleusIQError
    └── nucleusiq.tools.ToolError
        └── MCPError                       — base for all MCP adapter errors
            ├── MCPConnectionError         — transport-level connection failure
            ├── MCPAuthError               — 401 / 403 / OAuth failure
            ├── MCPTimeoutError            — RPC exceeded configured timeout
            ├── MCPProtocolError           — malformed JSON-RPC / unexpected response
            └── MCPToolError               — server returned ``isError=true``
                                              (raised in MCPBoundTool.execute)

This hierarchy lets users:
    * catch broad failures: ``except MCPError``
    * catch only auth issues: ``except MCPAuthError`` (e.g. to re-prompt)
    * still benefit from NucleusIQ's plugin / executor error handling
      because every MCPError IS-A ToolError.
"""

from __future__ import annotations

from typing import Any

from nucleusiq.tools.errors import ToolError, ToolExecutionError

__all__ = [
    "MCPError",
    "MCPConnectionError",
    "MCPAuthError",
    "MCPTimeoutError",
    "MCPProtocolError",
    "MCPToolError",
]


class MCPError(ToolError):
    """Base for all MCP adapter errors.

    Inherits from :class:`nucleusiq.tools.ToolError`, so it is caught
    by NucleusIQ's executor error path (plugins, tracer, retries) just
    like any built-in tool error.

    Attributes:
        server: The server label (``MCPServerConfig.name``) where the
            error originated.  ``None`` for adapter-level errors that
            are not server-specific.
    """

    def __init__(
        self,
        message: str = "",
        *,
        server: str | None = None,
        tool_name: str = "unknown",
        original_error: BaseException | None = None,
        args_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.server = server
        super().__init__(
            message,
            tool_name=tool_name,
            original_error=original_error,
            args_snapshot=args_snapshot,
        )

    def __repr__(self) -> str:
        parts = [f"{type(self).__name__}({self!s})"]
        if self.server:
            parts.append(f"server={self.server!r}")
        if self.tool_name != "unknown":
            parts.append(f"tool_name={self.tool_name!r}")
        return " ".join(parts)


class MCPConnectionError(MCPError):
    """Transport-level connection failure.

    Raised when stdio subprocess fails to start, HTTP connection
    cannot be opened, or the underlying transport raises a network
    error.  Distinguishable from :class:`MCPAuthError` (which is a
    *semantic* failure after the transport is established).
    """


class MCPAuthError(MCPError):
    """Authentication or authorization failure.

    Raised on HTTP 401 / 403, OAuth flow failures, or when an
    ``Authorization`` header is required but absent.  Stored
    ``status_code`` (when known) helps callers decide whether to
    re-prompt for credentials or refresh tokens.
    """

    def __init__(
        self,
        message: str = "",
        *,
        server: str | None = None,
        status_code: int | None = None,
        tool_name: str = "unknown",
        original_error: BaseException | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(
            message,
            server=server,
            tool_name=tool_name,
            original_error=original_error,
        )


class MCPTimeoutError(MCPError):
    """Timeout while waiting for an MCP response.

    Raised when ``call_tool`` or ``list_tools`` does not return
    within the configured timeout (default 30 s).
    """


class MCPProtocolError(MCPError):
    """Malformed JSON-RPC payload or unexpected MCP server response.

    Raised when the MCP server returns a response that does not
    match the spec (e.g. missing required fields, invalid types).
    Indicates a bug in the server, not in the user's call.
    """


class MCPToolError(ToolExecutionError):
    """The MCP server returned ``isError=True`` for a tool invocation.

    Distinct from :class:`MCPProtocolError`: the protocol succeeded
    (a valid ``CallToolResult`` was received), but the *tool itself*
    reported an error.  We map this to
    :class:`nucleusiq.tools.errors.ToolExecutionError` so it flows
    through NucleusIQ's normal "tool failed at runtime" path —
    executor / plugins / tracer all see a uniform ToolExecutionError.

    Attributes:
        server: The MCP server label.
        content_text: Concatenated text content from the error result
            (the server's explanation of why the tool failed).
    """

    def __init__(
        self,
        message: str = "",
        *,
        server: str | None = None,
        content_text: str | None = None,
        tool_name: str = "unknown",
        args_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.server = server
        self.content_text = content_text
        super().__init__(
            message,
            tool_name=tool_name,
            args_snapshot=args_snapshot,
        )
