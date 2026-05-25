"""Long-lived connection to a single MCP server.

:class:`MCPSession` owns the lifecycle of one MCP connection: the
transport (stdio subprocess or HTTP), the JSON-RPC :class:`ClientSession`,
and the :class:`AsyncExitStack` that ties everything together.

Design rationale (SRP / DIP from SOLID)
---------------------------------------
* The session knows about **transports** and **RPCs** — it does NOT
  know anything about :class:`BaseTool`, schemas, or NucleusIQ.  That
  separation lets us mock the session for bound-tool tests and reuse
  it for prompt / resource APIs later.
* All three transports go through one ``_open_transport`` branch so
  the rest of the lifecycle code is transport-agnostic.
* Concurrency:
    - Connect / disconnect are guarded by ``_state_lock`` so two
      callers (e.g. agent init racing with an early ``call_tool``)
      cannot corrupt state.
    - Call / list go through ``_call_lock`` so they are serialized
      against the single underlying RPC stream (the MCP SDK is not
      thread-safe).
* Rate-limit retries reuse :mod:`nucleusiq.llms.retry_policy` so we
  share the same observability and backoff caps as LLM provider
  packages.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from nucleusiq_mcp.config import MCPServerConfig, MCPTransport
from nucleusiq_mcp.exceptions import (
    MCPAuthError,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
)
from nucleusiq_mcp.models import MCPContent, MCPToolResult, MCPToolSpec
from nucleusiq_mcp.retry import (
    DEFAULT_MAX_RETRIES,
    looks_transient,
    rate_limit_sleep,
    sleep_with_cancel,
)

if TYPE_CHECKING:
    from mcp import ClientSession

__all__ = ["MCPSession"]


_logger = logging.getLogger(__name__)


class MCPSession:
    """A connected MCP session bound to one :class:`MCPServerConfig`.

    Lifecycle:
        1. ``connect()`` — open the transport, initialize the protocol,
           call ``ClientSession.initialize``.
        2. ``list_tools()`` / ``call_tool()`` — concurrent-safe RPCs.
        3. ``disconnect()`` — tear down everything in reverse order.

    All three are idempotent (the lock + ``_connected`` flag absorb
    duplicate calls), which keeps :class:`MCPTool` simple.
    """

    def __init__(
        self,
        config: MCPServerConfig,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._config = config
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._connected = False
        self._state_lock = asyncio.Lock()
        # Serialize RPCs against the single MCP stream (SDK is not
        # safe for concurrent in-flight requests on one ClientSession).
        self._call_lock = asyncio.Lock()
        self._max_retries = max(0, int(max_retries))

    # ------------------------------------------------------------------ #
    # Public properties                                                   #
    # ------------------------------------------------------------------ #

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def server_name(self) -> str:
        return self._config.name

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def connect(self) -> None:
        """Open the transport and initialize the MCP protocol.

        Idempotent.  Concurrent calls are serialized; the first wins,
        subsequent calls are fast no-ops once connected.
        """
        async with self._state_lock:
            if self._connected:
                return
            self._stack = AsyncExitStack()
            try:
                read, write = await self._open_transport(self._stack)
                # ClientSession is from mcp SDK; imported here to keep
                # the top-level import cost low for users only doing
                # config-time work (e.g. tests).
                from mcp import ClientSession

                session = await self._stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                self._session = session
                self._connected = True
                _logger.debug(
                    "MCPSession connected to %r via %s",
                    self._config.name,
                    self._config.transport.value,
                )
            except MCPAuthError:
                await self._safe_close_stack()
                raise
            except Exception as exc:
                await self._safe_close_stack()
                raise MCPConnectionError(
                    f"Failed to connect to MCP server {self._config.name!r}: {exc}",
                    server=self._config.name,
                    original_error=exc,
                ) from exc

    async def disconnect(self) -> None:
        """Tear down the session and transport.

        Idempotent — safe to call multiple times.  Errors during
        shutdown are logged but not raised, mirroring the convention
        used by other NucleusIQ providers.
        """
        async with self._state_lock:
            if not self._stack:
                self._connected = False
                self._session = None
                return
            await self._safe_close_stack()
            self._connected = False
            self._session = None

    async def __aenter__(self) -> MCPSession:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------ #
    # RPCs                                                                #
    # ------------------------------------------------------------------ #

    async def list_tools(self) -> list[MCPToolSpec]:
        """List tools advertised by the server.

        Raises:
            MCPConnectionError: if the session is not connected.
            MCPTimeoutError: if the RPC exceeds the configured timeout.
            MCPProtocolError: if the response is malformed.
        """
        self._ensure_connected()
        async with self._call_lock:
            try:
                result = await asyncio.wait_for(
                    self._session.list_tools(),  # type: ignore[union-attr]
                    timeout=self._config.timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise MCPTimeoutError(
                    f"list_tools timed out after {self._config.timeout_seconds}s "
                    f"on server {self._config.name!r}",
                    server=self._config.name,
                    original_error=exc,
                ) from exc
            except Exception as exc:
                raise MCPProtocolError(
                    f"list_tools failed on server {self._config.name!r}: {exc}",
                    server=self._config.name,
                    original_error=exc,
                ) from exc

        return [_convert_tool(t) for t in (result.tools or [])]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Invoke ``tools/call`` for ``tool_name`` with ``arguments``.

        Retries up to :attr:`max_retries` times on transient errors
        (429 / 503 / timeouts) using NucleusIQ's shared rate-limit
        policy (:mod:`nucleusiq.llms.retry_policy`).

        Returns the raw :class:`MCPToolResult` — including ``is_error``.
        It is the caller's job (typically :class:`MCPBoundTool`) to
        raise :class:`MCPToolError` when ``is_error`` is True.

        Raises:
            MCPConnectionError: if the session is not connected.
            MCPTimeoutError: if the RPC exceeds the configured timeout
                after all retries.
            MCPProtocolError: if the response is malformed after all
                retries.
        """
        self._ensure_connected()

        last_exc: MCPError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._call_tool_once(tool_name, arguments)
            except (MCPTimeoutError, MCPProtocolError) as exc:
                last_exc = exc
                if attempt >= self._max_retries or not looks_transient(exc):
                    raise
                sleep = rate_limit_sleep(attempt + 1)
                _logger.warning(
                    "mcp.call_tool retry attempt=%d server=%r tool=%r sleep=%.2fs cause=%s",
                    attempt + 1,
                    self._config.name,
                    tool_name,
                    sleep,
                    exc,
                )
                await sleep_with_cancel(sleep)

        # Defensive — loop should have either returned or raised.
        assert last_exc is not None  # pragma: no cover
        raise last_exc  # pragma: no cover

    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> MCPToolResult:
        """Single ``tools/call`` invocation without retry."""
        timeout_td = timedelta(seconds=self._config.timeout_seconds)
        async with self._call_lock:
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(  # type: ignore[union-attr]
                        tool_name,
                        arguments or {},
                        read_timeout_seconds=timeout_td,
                    ),
                    timeout=self._config.timeout_seconds * 1.2,
                )
            except asyncio.TimeoutError as exc:
                raise MCPTimeoutError(
                    f"call_tool({tool_name!r}) timed out after "
                    f"{self._config.timeout_seconds}s on {self._config.name!r}",
                    server=self._config.name,
                    tool_name=tool_name,
                    original_error=exc,
                ) from exc
            except Exception as exc:
                raise MCPProtocolError(
                    f"call_tool({tool_name!r}) failed on {self._config.name!r}: {exc}",
                    server=self._config.name,
                    tool_name=tool_name,
                    original_error=exc,
                ) from exc

        return _convert_result(result)

    # ------------------------------------------------------------------ #
    # Private — transport opening                                         #
    # ------------------------------------------------------------------ #

    async def _open_transport(self, stack: AsyncExitStack) -> tuple[Any, Any]:
        """Open the right transport, enter its context, return (read, write).

        Centralized branching so adding a new transport is local
        (OCP-friendly).
        """
        transport = self._config.transport
        if transport == MCPTransport.STDIO:
            return await self._open_stdio(stack)
        if transport == MCPTransport.STREAMABLE_HTTP:
            return await self._open_streamable_http(stack)
        if transport == MCPTransport.SSE:
            return await self._open_sse(stack)
        raise MCPProtocolError(  # pragma: no cover — exhaustive enum
            f"Unsupported transport: {transport!r}",
            server=self._config.name,
        )

    async def _open_stdio(self, stack: AsyncExitStack) -> tuple[Any, Any]:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        argv = self._config.stdio_command_argv()
        command, args = argv[0], argv[1:]

        env = dict(self._config.env) if self._config.env else None
        params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
            cwd=self._config.cwd,
        )
        # stdio_client yields (read, write) only — 2-tuple
        read, write = await stack.enter_async_context(stdio_client(params))
        return read, write

    async def _open_streamable_http(self, stack: AsyncExitStack) -> tuple[Any, Any]:
        from mcp.client.streamable_http import streamablehttp_client

        url = self._config.server
        headers = self._build_http_headers()
        httpx_auth = self._build_httpx_auth()

        # streamablehttp_client yields (read, write, get_session_id) — 3-tuple
        ctx = streamablehttp_client(
            url,
            headers=headers,
            timeout=self._config.timeout_seconds,
            auth=httpx_auth,
        )
        read, write, _get_session_id = await stack.enter_async_context(ctx)
        return read, write

    async def _open_sse(self, stack: AsyncExitStack) -> tuple[Any, Any]:
        from mcp.client.sse import sse_client

        url = self._config.server
        headers = self._build_http_headers()
        httpx_auth = self._build_httpx_auth()

        # sse_client yields (read, write) — 2-tuple
        read, write = await stack.enter_async_context(
            sse_client(
                url,
                headers=headers,
                timeout=self._config.timeout_seconds,
                auth=httpx_auth,
            )
        )
        return read, write

    # ------------------------------------------------------------------ #
    # Private — HTTP helpers                                              #
    # ------------------------------------------------------------------ #

    def _build_http_headers(self) -> dict[str, str] | None:
        """Merge user-supplied headers with auth-strategy headers.

        Returns ``None`` when no headers are needed (lets the SDK use
        its defaults).
        """
        merged: dict[str, str] = {}
        if self._config.headers:
            merged.update(self._config.headers)
        auth = self._config.auth
        if auth is not None:
            try:
                merged.update(auth.apply_headers())
            except MCPAuthError:
                # Re-raise auth errors so connect() can surface them
                # with a clear message rather than as transport errors.
                raise
        return merged or None

    def _build_httpx_auth(self) -> Any | None:
        auth = self._config.auth
        if auth is None:
            return None
        return auth.httpx_auth()

    # ------------------------------------------------------------------ #
    # Private — state helpers                                             #
    # ------------------------------------------------------------------ #

    def _ensure_connected(self) -> None:
        if not self._connected or self._session is None:
            raise MCPConnectionError(
                f"MCPSession({self._config.name!r}) is not connected. "
                f"Did you forget to await session.connect()?",
                server=self._config.name,
            )

    async def _safe_close_stack(self) -> None:
        stack = self._stack
        self._stack = None
        if stack is None:
            return
        try:
            await stack.aclose()
        except Exception as exc:  # noqa: BLE001 — best-effort shutdown
            _logger.warning(
                "Error while closing MCPSession transport for %r: %s",
                self._config.name,
                exc,
            )


# ====================================================================== #
# Conversion helpers                                                       #
# ====================================================================== #


def _convert_tool(t: Any) -> MCPToolSpec:
    """Convert ``mcp.types.Tool`` into our local :class:`MCPToolSpec`.

    Tolerates both attribute access (Pydantic model) and dict access
    (some test doubles use dicts).
    """
    get = _safe_getter(t)
    return MCPToolSpec(
        name=get("name") or "",
        description=get("description") or "",
        input_schema=get("inputSchema") or get("input_schema") or {},
        output_schema=get("outputSchema") or get("output_schema"),
        title=get("title"),
        annotations=_dump(get("annotations")),
    )


def _convert_result(r: Any) -> MCPToolResult:
    """Convert ``mcp.types.CallToolResult`` into our :class:`MCPToolResult`."""
    get = _safe_getter(r)
    raw_content = get("content") or []
    content = [_convert_content(c) for c in raw_content]
    return MCPToolResult(
        content=content,
        structured=get("structuredContent"),
        is_error=bool(get("isError")),
        meta=_dump(get("meta")),
    )


def _convert_content(c: Any) -> MCPContent:
    """Convert a single content block (text / image / resource / audio)."""
    get = _safe_getter(c)
    type_ = (get("type") or "").lower()
    mime = get("mimeType") or get("mime_type")
    annotations_meta = _dump(get("annotations"))

    if type_ == "text":
        return MCPContent(kind="text", text=get("text") or "", meta=annotations_meta)
    if type_ == "image":
        return MCPContent(
            kind="image",
            data=get("data"),
            mime_type=mime,
            meta=annotations_meta,
        )
    if type_ == "audio":
        return MCPContent(
            kind="audio",
            data=get("data"),
            mime_type=mime,
            meta=annotations_meta,
        )
    if type_ in ("resource", "embedded_resource"):
        resource = get("resource")
        rget = _safe_getter(resource) if resource is not None else (lambda _k: None)
        return MCPContent(
            kind="resource",
            text=rget("text"),
            uri=rget("uri"),
            mime_type=rget("mimeType") or rget("mime_type") or mime,
            meta=annotations_meta,
        )
    # Unknown / future content type — keep it for diagnostics.
    return MCPContent(
        kind="unknown",
        text=str(get("text") or ""),
        meta=annotations_meta,
    )


def _safe_getter(obj: Any):
    """Return a callable that fetches attributes or dict keys safely."""
    if obj is None:
        return lambda _k: None
    if isinstance(obj, dict):
        return lambda k: obj.get(k)
    return lambda k: getattr(obj, k, None)


def _dump(value: Any) -> dict[str, Any] | None:
    """Best-effort conversion of a Pydantic model / dict to dict-or-None."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            result = dump()
        except Exception:  # pragma: no cover — defensive
            return None
        return result if isinstance(result, dict) else None
    return None
