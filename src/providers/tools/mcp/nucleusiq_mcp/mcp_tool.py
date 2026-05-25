"""``MCPTool`` — the single public entry point users interact with.

Add an MCP server to a NucleusIQ agent in **one line**::

    from nucleusiq_mcp import MCPTool
    from nucleusiq.agents.agent import Agent

    agent = Agent(
        name="researcher",
        llm=llm,
        prompt=prompt,
        tools=[
            MCPTool("https://mcp.slack.com/api", auth="xoxb-...token..."),
            MCPTool("npx -y @modelcontextprotocol/server-github"),
        ],
    )
    await agent.initialize()  # adapter connects + expands tools

Design rationale (SOLID)
------------------------
* **SRP** — ``MCPTool`` is *only* a factory; it does not own RPCs (that
  is :class:`MCPSession`) or tool execution (that is :class:`MCPBoundTool`).
* **OCP** — Filtering / renaming behaviour goes through small
  composable callables (``include_tools``, ``rename``,
  ``tool_filter``).  New strategies = new callable, no edits here.
* **LSP** — ``MCPTool`` satisfies the
  :class:`~nucleusiq.tools.protocols.ExpandableTool` protocol; the
  agent treats it the same as any other adapter.
* **ISP** — Public API is small (constructor + 3 lifecycle methods).
* **DIP** — Depends on :class:`~nucleusiq_mcp.auth.MCPAuth` (a protocol),
  not on concrete strategies.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from nucleusiq_mcp.auth import MCPAuth, build_auth
from nucleusiq_mcp.bound_tool import MCPBoundTool
from nucleusiq_mcp.config import MCPServerConfig, MCPTransport
from nucleusiq_mcp.session import MCPSession

if TYPE_CHECKING:
    from nucleusiq.tools.base_tool import BaseTool

    from nucleusiq_mcp.models import MCPToolSpec

__all__ = ["MCPTool"]


_logger = logging.getLogger(__name__)


# ====================================================================== #
# Type aliases — make the public API self-documenting                      #
# ====================================================================== #

ToolFilter = Callable[["MCPToolSpec"], bool]
"""User predicate: return True to *include* a tool in the agent's toolset."""

ToolRenamer = Callable[[str], str]
"""User callable to rename a tool (returns the new tool name)."""

CollisionPolicy = str  # "auto_prefix" | "skip" | "raise"

ConnectFailurePolicy = str  # "raise" | "skip"


class MCPTool:
    """User-facing factory for one MCP server connection.

    Implements :class:`~nucleusiq.tools.protocols.ExpandableTool` so the
    NucleusIQ agent expands it into many :class:`MCPBoundTool` instances
    during ``Agent.initialize()``.

    Parameters
    ----------
    server:
        Either an HTTP(S) URL (Streamable HTTP / SSE) or a stdio command
        line.  Transport is auto-detected unless ``transport`` is passed.
    transport:
        Explicit transport override.  Pass
        :attr:`MCPTransport.SSE` to use the legacy SSE transport.
    name:
        Short label used in logs / telemetry / collisions.  Derived from
        ``server`` if not provided.
    auth:
        One of:

        * ``None`` — no auth (stdio, anonymous HTTP)
        * ``str``  — bearer token (sugar for :class:`BearerAuth`)
        * ``dict`` — custom headers (sugar for :class:`CustomHeadersAuth`)
        * :class:`MCPAuth` instance — any strategy (e.g. :class:`EnvAuth`,
          :class:`OAuthAuth`).
    env, cwd:
        Subprocess environment / working directory for stdio.
    headers:
        Extra HTTP headers (merged with auth headers).
    timeout_seconds:
        Per-RPC timeout (default 30s).
    include_tools:
        Optional whitelist of remote tool names.  Tools not in the list
        are dropped at expansion time.
    exclude_tools:
        Optional blacklist of remote tool names.
    tool_filter:
        A predicate ``(MCPToolSpec) -> bool``.  Combined with the
        whitelist / blacklist using AND semantics.  Wins over both.
    rename:
        Either a static mapping ``{remote_name: final_name}`` or a
        callable ``(remote_name) -> final_name`` for full control.
    prefix:
        Static prefix prepended to every tool name (after rename).
    on_collision:
        How to handle name collisions with tools already on the agent:

        * ``"auto_prefix"`` (default) — prefix the colliding tool with
          ``{server_name}_``.
        * ``"skip"``  — drop the colliding tool silently.
        * ``"raise"`` — raise :class:`ValueError`.
    on_connect_failure:
        How to react if this server is unreachable / mis-authenticated
        when the agent calls :meth:`connect`:

        * ``"raise"`` (default) — re-raise :class:`MCPError` so the
          agent halts initialization.
        * ``"skip"`` — log a warning and degrade gracefully:
          subsequent :meth:`expand` returns an empty list.  Use this
          when one of many MCP servers being optional is acceptable
          (e.g. multi-tenant dashboards where each user has different
          permissions).
    health_check:
        When ``True`` (default), :meth:`connect` issues a single
        ``list_tools`` round-trip to confirm the JSON-RPC channel is
        actually usable.  Set ``False`` only if you need the fastest
        possible startup and trust the transport.

    Examples
    --------
    Simple Slack connection via bearer token::

        MCPTool("https://mcp.slack.com/api", auth="xoxb-...")

    GitHub local stdio (token from env)::

        from nucleusiq_mcp import EnvAuth
        MCPTool(
            "npx -y @modelcontextprotocol/server-github",
            env={"GITHUB_TOKEN": "<token>"},  # passed to subprocess
        )

    Subset of tools only::

        MCPTool(
            "https://mcp.example.com/api",
            auth="...",
            include_tools=["search", "summarize"],
            prefix="ex",  # → "ex_search", "ex_summarize"
        )
    """

    def __init__(
        self,
        server: str,
        *,
        transport: MCPTransport | str | None = None,
        name: str | None = None,
        auth: MCPAuth | str | dict[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
        include_tools: list[str] | None = None,
        exclude_tools: list[str] | None = None,
        tool_filter: ToolFilter | None = None,
        rename: Mapping[str, str] | ToolRenamer | None = None,
        prefix: str | None = None,
        on_collision: CollisionPolicy = "auto_prefix",
        on_connect_failure: ConnectFailurePolicy = "raise",
        health_check: bool = True,
    ) -> None:
        if on_collision not in ("auto_prefix", "skip", "raise"):
            raise ValueError(
                f"on_collision must be one of 'auto_prefix', 'skip', 'raise'; "
                f"got {on_collision!r}"
            )
        if on_connect_failure not in ("raise", "skip"):
            raise ValueError(
                f"on_connect_failure must be 'raise' or 'skip'; "
                f"got {on_connect_failure!r}"
            )

        self._config = MCPServerConfig.build(
            server=server,
            transport=transport,
            name=name,
            auth=build_auth(auth),
            env=env,
            cwd=cwd,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )

        self._include = set(include_tools) if include_tools else None
        self._exclude = set(exclude_tools or [])
        self._tool_filter = tool_filter
        self._rename = self._coerce_renamer(rename)
        self._prefix = prefix
        self._on_collision = on_collision
        self._on_connect_failure = on_connect_failure
        self._health_check = health_check

        # Lazily created in connect().
        self._session: MCPSession | None = None
        # Set when on_connect_failure="skip" and connect() actually failed,
        # so expand() can return [] without raising.
        self._connect_skipped = False
        self._connect_error: BaseException | None = None

    # ------------------------------------------------------------------ #
    # Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    @property
    def session(self) -> MCPSession | None:
        return self._session

    @property
    def name(self) -> str:
        """Server label — exposed so :class:`Agent` doesn't treat this
        as a tool with ``getattr(t, 'name', None) is None`` in the
        collision-existing-names set."""
        return self._config.name

    # ------------------------------------------------------------------ #
    # ExpandableTool contract                                             #
    # ------------------------------------------------------------------ #

    async def connect(self) -> None:
        """Open the MCP session (idempotent).

        Failure handling honors :attr:`on_connect_failure`:

        * ``"raise"`` — propagate the original :class:`MCPError`.
        * ``"skip"``  — log a warning, set a flag, and return cleanly
          so the agent keeps initializing.  Subsequent :meth:`expand`
          returns an empty list.

        When :attr:`health_check` is True, we also do a single
        ``list_tools`` round-trip after the protocol handshake to
        verify the JSON-RPC stream is alive — many bugs (wrong URL,
        wrong content-type, proxy stripping headers, expired token)
        only surface on the first RPC, not on transport open.
        """
        if self._session is None:
            self._session = MCPSession(self._config)
        try:
            await self._session.connect()
            if self._health_check:
                # One round-trip catches "transport opened but server
                # speaks something else" failure modes.  ``list_tools``
                # is the cheapest valid MCP call.
                await self._session.list_tools()
        except (KeyboardInterrupt, SystemExit):
            # Always let user-driven aborts through.  Best-effort cleanup.
            with contextlib.suppress(Exception):
                await self._session.disconnect()
            raise
        except BaseException as exc:
            # We deliberately catch BaseException (after carving out the
            # user-abort cases above) because anyio's TaskGroup raises
            # ``asyncio.CancelledError`` (a BaseException) when its
            # internal sub-task fails — this is how
            # ``streamablehttp_client`` surfaces ``httpx.ConnectError``.
            # If we only caught Exception, the "skip" policy would be
            # silently bypassed for HTTP transports that can't open.
            if self._on_connect_failure == "skip":
                self._connect_skipped = True
                self._connect_error = exc
                _logger.warning(
                    "MCPTool(%r): connect failed; skipping "
                    "(on_connect_failure='skip'): %s",
                    self._config.name,
                    exc,
                )
                with contextlib.suppress(Exception):
                    await self._session.disconnect()
                return
            raise

    async def ping(self) -> bool:
        """Public health-check.  Returns True iff a ``list_tools`` RPC
        currently succeeds on this server.

        Does NOT raise — returns False on any error.  Useful for
        liveness probes and dashboards.  Does not change ``_connect_skipped``
        so a previously skipped tool stays skipped.
        """
        if self._session is None or not self._session.is_connected:
            return False
        try:
            await self._session.list_tools()
            return True
        except Exception as exc:  # noqa: BLE001 — diagnostic
            _logger.debug("MCPTool(%r) ping failed: %s", self._config.name, exc)
            return False

    async def expand(
        self,
        existing_names: set[str] | None = None,
    ) -> list[BaseTool]:
        """Discover MCP tools and wrap each as an :class:`MCPBoundTool`.

        ``existing_names`` is mutated externally by
        :meth:`Agent.initialize` between adapters; we treat it as a
        read-only snapshot here (callers pass a fresh copy).

        Returns an empty list when :meth:`connect` was skipped due to
        the ``on_connect_failure="skip"`` policy.
        """
        if self._connect_skipped:
            return []
        if self._session is None or not self._session.is_connected:
            raise RuntimeError(
                "MCPTool.expand() called before connect(); the agent core "
                "is expected to call connect() first."
            )

        remote_specs = await self._session.list_tools()
        existing = set(existing_names or set())

        bound: list[BaseTool] = []
        for spec in remote_specs:
            if not self._passes_filters(spec):
                continue

            final_name = self._final_name_for(spec.name)

            # Collision handling
            if final_name in existing:
                if self._on_collision == "raise":
                    raise ValueError(
                        f"MCPTool({self._config.name!r}): tool name "
                        f"{final_name!r} collides with an existing tool"
                    )
                if self._on_collision == "skip":
                    continue
                # auto_prefix
                final_name = f"{self._config.name}_{final_name}"
                if final_name in existing:
                    # Extremely unlikely, but be safe.
                    continue

            existing.add(final_name)
            bound.append(
                MCPBoundTool(
                    session=self._session,
                    tool_spec=spec,
                    final_name=final_name,
                )
            )
        return bound

    async def disconnect(self) -> None:
        """Tear down the MCP session (idempotent)."""
        if self._session is not None:
            await self._session.disconnect()

    # ------------------------------------------------------------------ #
    # Diagnostics                                                         #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"MCPTool(server={self._config.name!r}, "
            f"transport={self._config.transport.value!r})"
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _passes_filters(self, spec: MCPToolSpec) -> bool:
        if self._include is not None and spec.name not in self._include:
            return False
        if spec.name in self._exclude:
            return False
        return not (self._tool_filter is not None and not self._tool_filter(spec))

    def _final_name_for(self, remote_name: str) -> str:
        renamed = self._rename(remote_name) if self._rename else remote_name
        if self._prefix:
            return f"{self._prefix}_{renamed}"
        return renamed

    @staticmethod
    def _coerce_renamer(
        value: Mapping[str, str] | ToolRenamer | None,
    ) -> ToolRenamer | None:
        if value is None:
            return None
        if callable(value):
            return value
        if isinstance(value, Mapping):
            mapping = dict(value)
            return lambda n: mapping.get(n, n)
        raise TypeError(
            f"rename must be a Mapping, a callable, or None; got {type(value).__name__}"
        )
