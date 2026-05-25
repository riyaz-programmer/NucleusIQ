"""Generic tool-adapter protocols for NucleusIQ.

This module defines structural protocols that **tool adapter packages**
(e.g. ``nucleusiq-mcp``, future A2A adapters, custom registry adapters)
implement so the agent core can expand a single user-facing factory into
many concrete :class:`~nucleusiq.tools.base_tool.BaseTool` instances at
``Agent.initialize()`` time.

Why a protocol (and not an ABC)?
    Protocols decouple the *contract* from the *inheritance chain*.
    Adapter packages do **not** have to import a class from
    ``nucleusiq``; they only need to expose the three required async
    methods.  This keeps core lean and respects ISP/DIP from SOLID.

Core uses :func:`isinstance` against the ``@runtime_checkable`` protocol
to distinguish *expandable* tools from regular :class:`BaseTool`
instances.  See ``MCP_INTEGRATION_DESIGN.md`` §10 for design rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nucleusiq.tools.base_tool import BaseTool


__all__ = ["ExpandableTool"]


@runtime_checkable
class ExpandableTool(Protocol):
    """A tool *factory* that expands into multiple :class:`BaseTool` instances.

    Implemented by adapter packages where a single user-facing object
    represents a connection to an external service (an MCP server, an
    A2A agent endpoint, a remote tool registry, …) that exposes many
    tools dynamically.

    Contract
    --------
    ``connect()``
        Open external resources (TCP / HTTP session, subprocess, OAuth
        flow).  **MUST be idempotent.**  Called once per agent
        ``initialize()`` cycle, in parallel with other adapters' connect
        calls via ``asyncio.gather``.

    ``expand(existing_names=None)``
        Discover the adapter's available tools and return concrete
        :class:`BaseTool` instances.  ``existing_names`` is the set of
        names already registered on the agent (from other tools or
        other adapters); adapters use it to enforce per-agent
        uniqueness via their own collision policy (e.g. prefix on
        conflict, raise, ignore).

    ``disconnect()``
        Tear down all resources opened by ``connect()``.  **MUST be
        idempotent and not raise on already-disconnected state.**
        Called via :func:`asyncio.gather` with ``return_exceptions=True``
        so one failing adapter does not block others.

    Notes
    -----
    * The protocol is intentionally minimal (3 methods) — Interface
      Segregation Principle.
    * Implementations remain free to add additional helper methods
      (e.g. ``list_prompts()``, ``health_check()``) without affecting
      the core contract.
    * Adapters returned tools should themselves be regular
      :class:`BaseTool` instances; core treats them no differently
      from hand-written tools after expansion.
    """

    async def connect(self) -> None:
        """Open external resources required to enumerate / call tools.

        Idempotent.  A second invocation on an already-connected
        adapter is a no-op.
        """
        ...

    async def expand(
        self,
        existing_names: set[str] | None = None,
    ) -> list[BaseTool]:
        """Return the list of :class:`BaseTool` instances this adapter exposes.

        Parameters
        ----------
        existing_names:
            Names already registered on the host agent.  Implementations
            should consult this set to detect collisions and apply
            their configured policy (e.g. auto-prefix, raise, ignore).

        Returns
        -------
        list[BaseTool]
            One :class:`BaseTool` per discovered tool, ready to be added
            to the agent's executor.
        """
        ...

    async def disconnect(self) -> None:
        """Tear down resources opened by :meth:`connect`.

        Idempotent.  Must not raise on already-disconnected state.
        """
        ...
