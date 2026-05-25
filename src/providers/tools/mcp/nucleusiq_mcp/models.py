"""Adapter-local domain models used by ``nucleusiq-mcp``.

These models mirror just enough of the MCP SDK's domain to give us:
* a stable surface that does not leak ``mcp.types`` everywhere
* a clean unit-test boundary (we can build instances by hand)
* a place to attach NucleusIQ-specific extras (e.g. source labels)

We deliberately do **not** wrap every MCP type — only the ones the
adapter consumes / emits.  Following Interface Segregation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MCPContent",
    "MCPToolSpec",
    "MCPToolResult",
]


class MCPContent(BaseModel):
    """A single content block returned by an MCP tool call.

    MCP tools can return mixed content (text, images, embedded
    resources).  We normalize all variants into this single model
    with ``kind`` indicating the original type.

    Attributes:
        kind: One of ``"text"``, ``"image"``, ``"resource"``,
            ``"audio"``, ``"unknown"``.
        text: Text payload (set when ``kind == "text"``).
        data: Binary payload as base64 string (set when
            ``kind in {"image", "audio"}``).
        mime_type: MIME type if applicable.
        uri: URI for embedded resources (when ``kind == "resource"``).
        meta: Untyped escape hatch for content-level metadata.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    text: str | None = None
    data: str | None = None
    mime_type: str | None = None
    uri: str | None = None
    meta: dict[str, Any] | None = None


class MCPToolSpec(BaseModel):
    """A tool *advertised* by an MCP server.

    Returned by :meth:`~nucleusiq_mcp.session.MCPSession.list_tools`.
    Consumed by :class:`~nucleusiq_mcp.schema_adapter.MCPSchemaAdapter`
    to produce a NucleusIQ-compatible JSON Schema.

    Attributes:
        name: MCP tool name (used in ``call_tool`` RPCs).
        description: Human-readable description.
        input_schema: The tool's ``inputSchema`` field (JSON Schema).
            We keep this as a plain dict — callers can normalize.
        output_schema: Optional ``outputSchema`` for structured output.
        title: Optional display title (separate from name).
        annotations: Optional MCP tool annotations (read-only, etc.).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    title: str | None = None
    annotations: dict[str, Any] | None = None


class MCPToolResult(BaseModel):
    """The result of one MCP ``tools/call`` RPC.

    Attributes:
        content: One or more content blocks (text, images, etc.).
        structured: Optional structured / typed payload provided
            alongside ``content`` (set when the server returns
            ``structuredContent``).
        is_error: ``True`` if the MCP server flagged this result as an
            error (we then raise :class:`MCPToolError` in the bound tool).
        meta: Untyped escape hatch for server-level metadata.
    """

    model_config = ConfigDict(frozen=True)

    content: list[MCPContent] = Field(default_factory=list)
    structured: Any | None = None
    is_error: bool = False
    meta: dict[str, Any] | None = None

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def join_text(self, sep: str = "\n") -> str:
        """Concatenate all text-content blocks (skipping non-text)."""
        return sep.join(c.text for c in self.content if c.kind == "text" and c.text)

    def has_non_text(self) -> bool:
        """Return True if any content block is non-text (image/resource)."""
        return any(c.kind != "text" for c in self.content)
