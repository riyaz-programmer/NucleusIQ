"""Decorator-style helpers for declaring MCP tool filters.

NucleusIQ users sometimes prefer a **decorator pattern** to declare
filters (similar to how FastMCP exposes ``@mcp.tool()`` on the server
side).  This module provides two ergonomic helpers:

* :func:`mcp_tool_filter` — decorate a predicate so it carries its own
  metadata (name, description, optional category whitelist).
* :class:`MCPToolset` — combine many filters under one
  ``MCPTool(tool_filter=toolset)`` call.

These are pure conveniences — equivalent to passing a callable to
``MCPTool(tool_filter=...)`` — but they document intent and compose
cleanly.  Open/Closed: filter logic lives outside :class:`MCPTool`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nucleusiq_mcp.models import MCPToolSpec

__all__ = ["mcp_tool_filter", "MCPToolset"]


# ====================================================================== #
# @mcp_tool_filter — decorator                                             #
# ====================================================================== #


def mcp_tool_filter(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[[Any], bool]], Callable[[Any], bool]]:
    """Annotate a predicate with metadata for diagnostics.

    Example::

        @mcp_tool_filter(name="read_only", description="Only read-only tools")
        def read_only(spec):
            return spec.name.startswith(("get_", "list_", "search_"))


        agent = Agent(
            ...,
            tools=[
                MCPTool("https://mcp.example.com", auth="...", tool_filter=read_only),
            ],
        )

    The decorated function behaves exactly like the original predicate;
    metadata is attached as attributes (``.filter_name``,
    ``.filter_description``) for tools that introspect it.
    """

    def _decorator(
        fn: Callable[[MCPToolSpec], bool],
    ) -> Callable[[MCPToolSpec], bool]:
        @wraps(fn)
        def _wrapped(spec: MCPToolSpec) -> bool:
            return fn(spec)

        _wrapped.filter_name = name or fn.__name__  # type: ignore[attr-defined]
        _wrapped.filter_description = description or fn.__doc__ or ""  # type: ignore[attr-defined]
        return _wrapped

    return _decorator


# ====================================================================== #
# MCPToolset — compose multiple filters                                    #
# ====================================================================== #


class MCPToolset:
    """Compose multiple filters into a single callable.

    By default, all sub-filters must accept (AND semantics).  Use
    :meth:`any_of` to OR them.

    Example::

        toolset = MCPToolset.all_of(
            read_only,
            mcp_tool_filter(name="not_admin")(lambda s: "admin" not in s.name),
        )

        agent = Agent(
            ...,
            tools=[
                MCPTool("https://mcp.example.com", tool_filter=toolset),
            ],
        )
    """

    def __init__(
        self,
        filters: Iterable[Callable[[MCPToolSpec], bool]],
        *,
        mode: str = "all",
    ) -> None:
        if mode not in ("all", "any"):
            raise ValueError(f"mode must be 'all' or 'any'; got {mode!r}")
        self._filters: tuple[Callable[[MCPToolSpec], bool], ...] = tuple(filters)
        self._mode = mode

    @classmethod
    def all_of(cls, *filters: Callable[[MCPToolSpec], bool]) -> MCPToolset:
        return cls(filters, mode="all")

    @classmethod
    def any_of(cls, *filters: Callable[[MCPToolSpec], bool]) -> MCPToolset:
        return cls(filters, mode="any")

    def __call__(self, spec: MCPToolSpec) -> bool:
        if not self._filters:
            return True
        if self._mode == "all":
            return all(f(spec) for f in self._filters)
        return any(f(spec) for f in self._filters)

    def __repr__(self) -> str:
        names = [
            getattr(f, "filter_name", getattr(f, "__name__", repr(f)))
            for f in self._filters
        ]
        return f"MCPToolset(mode={self._mode!r}, filters={names!r})"
