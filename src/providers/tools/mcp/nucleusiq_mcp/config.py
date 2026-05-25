"""Configuration models for the ``nucleusiq-mcp`` adapter.

This module defines :class:`MCPTransport` (the enum of supported MCP
transports) and :class:`MCPServerConfig` (a single immutable record
describing how to reach one MCP server).

Design rationale
----------------
* **SRP** — ``MCPServerConfig`` owns *configuration only*; transport
  selection, auth wiring, and session lifecycle live in other modules.
* **OCP** — Adding a new transport means adding an enum value and a
  branch in :class:`~nucleusiq_mcp.session.MCPSession`; nothing in this
  module changes.
* **Validation** — All validation happens at construction time.
  Once built, the config is immutable (``frozen=True``).
"""

from __future__ import annotations

import enum
import shlex
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from nucleusiq_mcp.auth import MCPAuth

__all__ = [
    "MCPTransport",
    "MCPServerConfig",
    "infer_transport",
]


# ====================================================================== #
# Transport enum                                                           #
# ====================================================================== #


class MCPTransport(str, enum.Enum):
    """Supported MCP transports.

    Mirrors the three transports defined in the MCP spec and implemented
    by the official ``mcp`` Python SDK:

    * :attr:`STDIO` — Subprocess via stdin / stdout JSON-RPC.  Best for
      local tools shipped as CLI binaries / npm packages.  Uses
      :func:`mcp.client.stdio.stdio_client`.

    * :attr:`STREAMABLE_HTTP` — JSON-RPC over HTTP with optional
      Server-Sent Events for streaming.  The current recommended HTTP
      transport in the MCP spec.  Uses
      :func:`mcp.client.streamable_http.streamablehttp_client`.

    * :attr:`SSE` — Legacy Server-Sent Events transport.  Kept for
      compatibility with servers that have not yet migrated to
      Streamable HTTP.  Uses :func:`mcp.client.sse.sse_client`.
    """

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"


# ====================================================================== #
# Transport auto-detection                                                 #
# ====================================================================== #


def infer_transport(server: str) -> MCPTransport:
    """Heuristically choose the right transport for a server string.

    Rules (matching the design doc §6.2):
      * Starts with ``http://`` or ``https://`` → :attr:`STREAMABLE_HTTP`
        (recommended modern HTTP transport).
      * Anything else → :attr:`STDIO` (treat the string as a command).

    Note: :attr:`SSE` is **never** inferred — it is legacy and users
    must opt in by passing ``transport=MCPTransport.SSE`` explicitly.
    This is intentional: we do not want to silently pick the legacy
    transport for users connecting to servers that support both.
    """
    s = server.strip().lower()
    if s.startswith(("http://", "https://")):
        return MCPTransport.STREAMABLE_HTTP
    return MCPTransport.STDIO


# ====================================================================== #
# Server config (immutable)                                                #
# ====================================================================== #


class MCPServerConfig(BaseModel):
    """Immutable description of one MCP server connection.

    Built by :class:`~nucleusiq_mcp.mcp_tool.MCPTool` from user-facing
    arguments and then consumed by
    :class:`~nucleusiq_mcp.session.MCPSession`.  Users normally do
    **not** construct this directly — use :class:`MCPTool` instead.

    Attributes
    ----------
    server:
        The connection target — either a URL (for HTTP transports) or
        a command line (for stdio).  For stdio, the string is parsed
        with :func:`shlex.split` to support things like
        ``"npx -y @modelcontextprotocol/server-github"``.
    transport:
        The MCP transport to use.  Auto-detected from ``server`` if not
        supplied (see :func:`infer_transport`).
    name:
        A short human-readable label used in logs, telemetry, and
        :attr:`nucleusiq.agents.agent_result.ToolCallRecord.source`.
        Auto-derived from the URL host or command basename if not set.
    auth:
        An :class:`~nucleusiq_mcp.auth.MCPAuth` strategy.  ``None``
        for stdio (parent process trust model) or pre-authenticated
        environments.
    env:
        Environment variables passed to the stdio subprocess.  Ignored
        for HTTP transports.
    cwd:
        Working directory for the stdio subprocess.  Ignored for HTTP
        transports.
    headers:
        Extra HTTP headers (merged into the request).  Auth headers
        are applied *separately* via the auth strategy so secrets are
        never copied into this dict.
    timeout_seconds:
        Per-RPC timeout (default 30 s).  Applied to ``list_tools`` and
        ``call_tool``.  Connection timeout is handled by the SDK.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    server: str
    transport: MCPTransport
    name: str
    auth: Any | None = None  # MCPAuth — typed as Any to avoid import cycle
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    headers: Mapping[str, str] | None = None
    timeout_seconds: float = Field(default=30.0, gt=0.0)

    # ------------------------------------------------------------------ #
    # Convenience builders                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def build(
        cls,
        server: str,
        *,
        transport: MCPTransport | str | None = None,
        name: str | None = None,
        auth: MCPAuth | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> MCPServerConfig:
        """Build an :class:`MCPServerConfig` with auto-inferred defaults.

        Centralizes all transport / name inference logic in one place
        so :class:`MCPTool` and tests share the same behaviour.
        """
        resolved_transport = (
            MCPTransport(transport)
            if isinstance(transport, str)
            else (transport or infer_transport(server))
        )
        resolved_name = name or _derive_name(server, resolved_transport)
        return cls(
            server=server,
            transport=resolved_transport,
            name=resolved_name,
            auth=auth,
            env=env,
            cwd=cwd,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def stdio_command_argv(self) -> list[str]:
        """Return the parsed argv for a stdio command.

        Raises
        ------
        ValueError
            If this is not a stdio config or the command is empty.
        """
        if self.transport != MCPTransport.STDIO:
            raise ValueError(
                f"stdio_command_argv() only valid for STDIO transport, "
                f"got {self.transport}"
            )
        argv = shlex.split(self.server)
        if not argv:
            raise ValueError("stdio command is empty")
        return argv

    def is_http(self) -> bool:
        """``True`` if this config uses an HTTP-based transport."""
        return self.transport in (MCPTransport.STREAMABLE_HTTP, MCPTransport.SSE)

    # ------------------------------------------------------------------ #
    # Validators                                                          #
    # ------------------------------------------------------------------ #

    @field_validator("server")
    @classmethod
    def _server_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("server must be a non-empty string")
        return v.strip()

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must be a non-empty string")
        return v.strip()

    @model_validator(mode="after")
    def _check_url_schemes(self) -> MCPServerConfig:
        """Cross-field validation: HTTP transports require a URL scheme."""
        if self.transport in (
            MCPTransport.STREAMABLE_HTTP,
            MCPTransport.SSE,
        ) and not self.server.lower().startswith(("http://", "https://")):
            raise ValueError(
                f"Transport {self.transport.value!r} requires an http(s):// "
                f"URL, got: {self.server!r}"
            )
        return self


# ====================================================================== #
# Name derivation                                                          #
# ====================================================================== #


def _derive_name(server: str, transport: MCPTransport) -> str:
    """Pick a sensible default name from the connection string.

    Examples:
        ``https://mcp.slack.com/api`` → ``"mcp.slack.com"``
        ``"npx @org/server-x"``       → ``"server-x"``
        ``"./mytool.py"``             → ``"mytool.py"``
    """
    if transport in (MCPTransport.STREAMABLE_HTTP, MCPTransport.SSE):
        # URL host
        try:
            from urllib.parse import urlparse

            parsed = urlparse(server)
            return parsed.hostname or server
        except Exception:
            return server

    # stdio: pick last segment of the last argv token
    try:
        argv = shlex.split(server)
    except ValueError:
        argv = [server]
    if not argv:
        return server
    last = argv[-1]
    # Strip leading paths and common prefixes
    base = last.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return base or last
