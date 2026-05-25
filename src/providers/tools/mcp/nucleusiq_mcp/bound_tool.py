"""``MCPBoundTool`` — one MCP tool wrapped as a NucleusIQ :class:`BaseTool`.

Each instance is produced by :class:`~nucleusiq_mcp.mcp_tool.MCPTool` and
represents *exactly one* remote tool on *exactly one* MCP server.  The
agent layer treats it indistinguishably from a local :class:`BaseTool`.

Design rationale
----------------
* **Single Responsibility** — Bound tools translate between
  ``BaseTool.execute`` and ``MCPSession.call_tool``; they do not
  manage the connection (the session owns that).
* **Open / Closed** — Result-formatting strategy (text vs multimodal
  vs structured) is encapsulated; adding new content types is a
  local change in :mod:`nucleusiq_mcp.session`'s ``_convert_content``.
* **Liskov** — A bound tool is a perfect substitute for any
  :class:`BaseTool` (agent code never special-cases it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nucleusiq.tools.base_tool import BaseTool

from nucleusiq_mcp.exceptions import MCPToolError
from nucleusiq_mcp.schema_adapter import MCPSchemaAdapter

if TYPE_CHECKING:
    from nucleusiq_mcp.models import MCPToolResult, MCPToolSpec
    from nucleusiq_mcp.session import MCPSession

__all__ = ["MCPBoundTool", "format_result"]


class MCPBoundTool(BaseTool):
    """A single remote MCP tool, presented as a NucleusIQ :class:`BaseTool`.

    Attributes:
        remote_name: The original MCP tool name (used in the RPC).
        server_label: Human-readable server label (for telemetry / logs).
    """

    def __init__(
        self,
        *,
        session: MCPSession,
        tool_spec: MCPToolSpec,
        final_name: str,
    ) -> None:
        super().__init__(
            name=final_name,
            description=tool_spec.description or tool_spec.name,
            version=None,
        )
        self._session = session
        self._tool_spec = tool_spec
        # The name we send in the RPC (the *remote* name) may differ from
        # the name we expose to the agent (the *final* name) when a
        # collision policy rewrote it.
        self.remote_name = tool_spec.name
        self.server_label = session.server_name
        # Telemetry source label read by NucleusIQ's tracer
        # (``base_mode.call_tool`` -> ``ToolCallRecord.source``).  We use
        # the standard ``mcp://`` URI scheme + (path=A) marker for the
        # client-side adapter (this package).
        self.source = f"mcp://server={session.server_name} (path=A)"
        self._spec_dict = MCPSchemaAdapter.to_nucleusiq_spec(
            tool_spec, final_name=final_name
        )

    # ------------------------------------------------------------------ #
    # BaseTool contract                                                   #
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        # The session has already been initialized by MCPTool.connect();
        # we deliberately do NOT connect lazily here to keep the
        # contract crisp: ExpandableTool.connect() must run first.
        return None

    async def execute(self, **kwargs: Any) -> Any:
        """Invoke the underlying MCP tool.

        Raises:
            MCPToolError: When the server returns ``is_error=True``.
                Mapped to :class:`nucleusiq.tools.errors.ToolExecutionError`
                via inheritance, so executor / plugins react uniformly.
        """
        result: MCPToolResult = await self._session.call_tool(self.remote_name, kwargs)
        if result.is_error:
            raise MCPToolError(
                message=(
                    f"MCP tool {self.remote_name!r} on server "
                    f"{self.server_label!r} returned an error"
                ),
                server=self.server_label,
                content_text=result.join_text() or None,
                tool_name=self.name,
                args_snapshot=dict(kwargs),
            )
        return format_result(result)

    def get_spec(self) -> dict[str, Any]:
        # Return a defensive copy so callers cannot mutate our cached spec.
        return dict(self._spec_dict)

    # ------------------------------------------------------------------ #
    # Diagnostics                                                         #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"MCPBoundTool(name={self.name!r}, remote={self.remote_name!r}, "
            f"server={self.server_label!r})"
        )


# ====================================================================== #
# Result formatting (Strategy)                                             #
# ====================================================================== #


def format_result(result: MCPToolResult) -> Any:
    """Pick the most useful Python representation of an MCP result.

    Selection rules (matching the design doc §6.5):
      1. If the server returned ``structuredContent``, return that
         (typed payload — best for downstream code).
      2. Else if all content blocks are text, return the joined text
         string (most ergonomic for LLM tool responses).
      3. Else return a structured dict ``{"content": [...]}`` carrying
         all blocks so multimodal callers don't lose anything.

    Returning ``Any`` is intentional — different MCP tools naturally
    return different shapes, and the agent's tool-result handling can
    take whatever we give it.
    """
    if result.structured is not None:
        return result.structured

    if not result.has_non_text():
        text = result.join_text()
        return text if text else ""

    # Multimodal — preserve everything.
    return {
        "content": [
            {
                "kind": c.kind,
                "text": c.text,
                "data": c.data,
                "mime_type": c.mime_type,
                "uri": c.uri,
            }
            for c in result.content
        ],
        "structured": result.structured,
    }
