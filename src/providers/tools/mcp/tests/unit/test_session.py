"""Tests for MCPSession lifecycle, RPCs, and conversion helpers.

The strategy here is to monkeypatch the three transport clients from the
MCP SDK and the ``ClientSession`` class.  This lets us exercise the full
session lifecycle (connect → list_tools → call_tool → disconnect) without
ever spawning a subprocess or opening an HTTP connection.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from nucleusiq_mcp.auth import BearerAuth
from nucleusiq_mcp.config import MCPServerConfig, MCPTransport
from nucleusiq_mcp.exceptions import (
    MCPAuthError,
    MCPConnectionError,
    MCPProtocolError,
    MCPTimeoutError,
)
from nucleusiq_mcp.session import (
    MCPSession,
    _convert_content,
    _convert_result,
    _convert_tool,
    _dump,
    _safe_getter,
)

# ====================================================================== #
# Test doubles for the MCP SDK                                             #
# ====================================================================== #


class _FakeClientSession:
    """Stand-in for ``mcp.ClientSession`` injected via monkeypatch."""

    initialize_calls = 0

    def __init__(self, read, write):
        self.read = read
        self.write = write
        self._initialized = False
        self.list_tools_should_raise: BaseException | None = None
        self.call_tool_should_raise: BaseException | None = None
        self.tools: list[Any] = []
        self.results: dict[str, Any] = {}
        self.list_tools_calls = 0
        self.call_tool_calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def initialize(self):
        _FakeClientSession.initialize_calls += 1
        self._initialized = True

    async def list_tools(self, cursor=None, *, params=None):
        self.list_tools_calls += 1
        if self.list_tools_should_raise:
            raise self.list_tools_should_raise
        return SimpleNamespace(tools=list(self.tools))

    async def call_tool(
        self,
        name,
        arguments=None,
        read_timeout_seconds=None,
        progress_callback=None,
        *,
        meta=None,
    ):
        self.call_tool_calls.append((name, dict(arguments or {})))
        if self.call_tool_should_raise:
            raise self.call_tool_should_raise
        return self.results.get(
            name,
            SimpleNamespace(
                content=[SimpleNamespace(type="text", text=f"ok:{name}")],
                structuredContent=None,
                isError=False,
                meta=None,
            ),
        )


@asynccontextmanager
async def _fake_stdio_client(params):
    # Returns (read, write) like the real SDK
    yield ("READ", "WRITE")


@asynccontextmanager
async def _fake_streamablehttp_client(url, headers=None, timeout=None, auth=None, **_):
    # Returns (read, write, get_session_id)
    yield ("READ", "WRITE", lambda: "sess-1")


@asynccontextmanager
async def _fake_sse_client(url, headers=None, timeout=None, auth=None, **_):
    yield ("READ", "WRITE")


@pytest.fixture
def patched_sdk(monkeypatch):
    """Patch the SDK's transports and ClientSession with fakes.

    Returns the FakeClientSession class so tests can poke its instance.
    """
    import mcp
    import mcp.client.sse as sse_mod
    import mcp.client.stdio as stdio_mod
    import mcp.client.streamable_http as sh_mod

    monkeypatch.setattr(mcp, "ClientSession", _FakeClientSession)
    monkeypatch.setattr(stdio_mod, "stdio_client", _fake_stdio_client)
    monkeypatch.setattr(sh_mod, "streamablehttp_client", _fake_streamablehttp_client)
    monkeypatch.setattr(sse_mod, "sse_client", _fake_sse_client)

    # Reset counter
    _FakeClientSession.initialize_calls = 0
    yield _FakeClientSession


# ====================================================================== #
# Lifecycle                                                                #
# ====================================================================== #


@pytest.mark.asyncio
class TestConnectDisconnect:
    async def test_connect_streamable_http(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        assert not s.is_connected
        await s.connect()
        assert s.is_connected
        assert patched_sdk.initialize_calls == 1
        assert s.server_name == http_config.name

    async def test_connect_stdio(self, patched_sdk, stdio_config):
        s = MCPSession(stdio_config)
        await s.connect()
        assert s.is_connected

    async def test_connect_sse(self, patched_sdk):
        cfg = MCPServerConfig.build("https://x.com/sse", transport=MCPTransport.SSE)
        s = MCPSession(cfg)
        await s.connect()
        assert s.is_connected

    async def test_connect_idempotent(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        await s.connect()
        # Second call short-circuits; initialize called only once.
        assert patched_sdk.initialize_calls == 1

    async def test_connect_failure_wraps_into_connection_error(
        self, monkeypatch, http_config
    ):
        @asynccontextmanager
        async def boom(*a, **k):
            raise RuntimeError("boom")
            yield  # pragma: no cover

        import mcp.client.streamable_http as sh_mod

        monkeypatch.setattr(sh_mod, "streamablehttp_client", boom)
        s = MCPSession(http_config)
        with pytest.raises(MCPConnectionError):
            await s.connect()
        assert not s.is_connected

    async def test_connect_propagates_mcp_auth_error(self, monkeypatch, http_config):
        @asynccontextmanager
        async def auth_boom(*a, **k):
            raise MCPAuthError("nope", server="example")
            yield  # pragma: no cover

        import mcp.client.streamable_http as sh_mod

        monkeypatch.setattr(sh_mod, "streamablehttp_client", auth_boom)
        s = MCPSession(http_config)
        with pytest.raises(MCPAuthError):
            await s.connect()

    async def test_disconnect_idempotent(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        await s.disconnect()
        await s.disconnect()  # no-op
        assert not s.is_connected

    async def test_disconnect_without_connect(self, http_config):
        s = MCPSession(http_config)
        await s.disconnect()
        assert not s.is_connected

    async def test_context_manager(self, patched_sdk, http_config):
        async with MCPSession(http_config) as s:
            assert s.is_connected
        assert not s.is_connected


# ====================================================================== #
# RPCs                                                                     #
# ====================================================================== #


@pytest.mark.asyncio
class TestListTools:
    async def test_list_tools_returns_specs(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        # Replace tools on the underlying FakeClientSession.
        s._session.tools = [  # type: ignore[attr-defined,union-attr]
            SimpleNamespace(
                name="search",
                description="Search",
                inputSchema={"type": "object", "properties": {}},
                outputSchema=None,
                title=None,
                annotations=None,
            )
        ]
        specs = await s.list_tools()
        assert len(specs) == 1
        assert specs[0].name == "search"

    async def test_list_tools_not_connected(self, http_config):
        s = MCPSession(http_config)
        with pytest.raises(MCPConnectionError):
            await s.list_tools()

    async def test_list_tools_timeout(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        s._session.list_tools_should_raise = asyncio.TimeoutError()  # type: ignore[union-attr]
        with pytest.raises(MCPTimeoutError):
            await s.list_tools()

    async def test_list_tools_protocol_error(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        s._session.list_tools_should_raise = RuntimeError("bad response")  # type: ignore[union-attr]
        with pytest.raises(MCPProtocolError):
            await s.list_tools()


@pytest.mark.asyncio
class TestCallTool:
    async def test_call_tool_success(self, patched_sdk, http_config):
        s = MCPSession(http_config)
        await s.connect()
        result = await s.call_tool("search", {"q": "rust"})
        assert result.is_error is False
        assert result.join_text() == "ok:search"

    async def test_call_tool_not_connected(self, http_config):
        s = MCPSession(http_config)
        with pytest.raises(MCPConnectionError):
            await s.call_tool("search")

    async def test_call_tool_with_is_error_returns_result(
        self, patched_sdk, http_config
    ):
        s = MCPSession(http_config)
        await s.connect()
        s._session.results["search"] = SimpleNamespace(  # type: ignore[union-attr]
            content=[SimpleNamespace(type="text", text="rate limit")],
            structuredContent=None,
            isError=True,
            meta=None,
        )
        result = await s.call_tool("search")
        assert result.is_error is True
        # Session returns the raw result; MCPBoundTool raises from this.

    async def test_call_tool_retries_on_transient(
        self, patched_sdk, http_config, monkeypatch
    ):
        # Speed up: zero sleep on retry.
        monkeypatch.setattr("nucleusiq_mcp.retry.rate_limit_sleep", lambda *a, **k: 0)
        s = MCPSession(http_config, max_retries=2)
        await s.connect()
        # First two calls raise transient, third succeeds.
        call_state = {"n": 0}

        async def call_tool(*a, **k):
            call_state["n"] += 1
            if call_state["n"] < 3:
                raise RuntimeError("429 too many requests")
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                structuredContent=None,
                isError=False,
                meta=None,
            )

        s._session.call_tool = call_tool  # type: ignore[union-attr]
        result = await s.call_tool("search")
        assert result.is_error is False
        assert call_state["n"] == 3

    async def test_call_tool_no_retry_on_permanent(
        self, patched_sdk, http_config, monkeypatch
    ):
        monkeypatch.setattr("nucleusiq_mcp.retry.rate_limit_sleep", lambda *a, **k: 0)
        s = MCPSession(http_config, max_retries=3)
        await s.connect()
        call_state = {"n": 0}

        async def call_tool(*a, **k):
            call_state["n"] += 1
            raise RuntimeError("schema validation failed")  # not transient

        s._session.call_tool = call_tool  # type: ignore[union-attr]
        with pytest.raises(MCPProtocolError):
            await s.call_tool("search")
        # Should have run exactly once (no retry on permanent error).
        assert call_state["n"] == 1

    async def test_call_tool_exhausts_retries(
        self, patched_sdk, http_config, monkeypatch
    ):
        monkeypatch.setattr("nucleusiq_mcp.retry.rate_limit_sleep", lambda *a, **k: 0)
        s = MCPSession(http_config, max_retries=2)
        await s.connect()

        async def call_tool(*a, **k):
            raise RuntimeError("429 too many")

        s._session.call_tool = call_tool  # type: ignore[union-attr]
        with pytest.raises(MCPProtocolError):
            await s.call_tool("search")

    async def test_call_tool_timeout(self, patched_sdk, http_config):
        s = MCPSession(http_config, max_retries=0)
        await s.connect()

        async def slow(*a, **k):
            raise asyncio.TimeoutError()

        s._session.call_tool = slow  # type: ignore[union-attr]
        with pytest.raises(MCPTimeoutError):
            await s.call_tool("search")

    async def test_max_retries_clamped_to_zero(self, patched_sdk, http_config):
        s = MCPSession(http_config, max_retries=-5)
        assert s._max_retries == 0


@pytest.mark.asyncio
class TestSessionProperties:
    async def test_config_property(self, http_config):
        s = MCPSession(http_config)
        assert s.config is http_config

    async def test_server_name(self, http_config):
        s = MCPSession(http_config)
        assert s.server_name == http_config.name


@pytest.mark.asyncio
class TestAuthHeadersBuildErrors:
    async def test_auth_apply_headers_error_raised(self, monkeypatch):
        from nucleusiq_mcp.auth import EnvAuth
        from nucleusiq_mcp.config import MCPServerConfig

        monkeypatch.delenv("MISSING_TOK", raising=False)
        cfg = MCPServerConfig.build("https://x.com", auth=EnvAuth("MISSING_TOK"))
        s = MCPSession(cfg)
        # _build_http_headers raises MCPAuthError when required env var missing.
        with pytest.raises(MCPAuthError):
            s._build_http_headers()


@pytest.mark.asyncio
class TestSafeCloseStack:
    async def test_close_with_error_logs_but_does_not_raise(
        self, patched_sdk, http_config, caplog
    ):
        s = MCPSession(http_config)
        await s.connect()

        # Replace the stack with one whose aclose raises.
        class BrokenStack:
            async def aclose(self):
                raise RuntimeError("close boom")

        s._stack = BrokenStack()  # type: ignore[assignment]
        # disconnect calls _safe_close_stack — must swallow the error.
        await s.disconnect()
        assert not s.is_connected


@pytest.mark.asyncio
class TestHttpAuthHeaders:
    async def test_bearer_auth_headers_merged(self, monkeypatch, http_config):
        captured = {}

        @asynccontextmanager
        async def capture_streamable(url, headers=None, **kw):
            captured["url"] = url
            captured["headers"] = headers
            captured["auth"] = kw.get("auth")
            yield ("R", "W", lambda: "x")

        import mcp
        import mcp.client.streamable_http as sh_mod

        monkeypatch.setattr(mcp, "ClientSession", _FakeClientSession)
        monkeypatch.setattr(sh_mod, "streamablehttp_client", capture_streamable)

        cfg = MCPServerConfig.build(
            "https://x.com/api",
            auth=BearerAuth("tok"),
            headers={"X-Tenant": "acme"},
        )
        s = MCPSession(cfg)
        await s.connect()
        assert captured["headers"]["Authorization"] == "Bearer tok"
        assert captured["headers"]["X-Tenant"] == "acme"
        # BearerAuth uses headers, not httpx auth.
        assert captured["auth"] is None

    async def test_no_auth_passes_no_headers(self, monkeypatch, http_config):
        captured = {}

        @asynccontextmanager
        async def capture(url, headers=None, **kw):
            captured["headers"] = headers
            yield ("R", "W", lambda: "x")

        import mcp
        import mcp.client.streamable_http as sh_mod

        monkeypatch.setattr(mcp, "ClientSession", _FakeClientSession)
        monkeypatch.setattr(sh_mod, "streamablehttp_client", capture)

        cfg = MCPServerConfig.build("https://x.com/api")
        await MCPSession(cfg).connect()
        assert captured["headers"] is None


# ====================================================================== #
# Conversion helpers                                                       #
# ====================================================================== #


class TestConverters:
    def test_safe_getter_dict(self):
        g = _safe_getter({"a": 1})
        assert g("a") == 1
        assert g("missing") is None

    def test_safe_getter_object(self):
        obj = SimpleNamespace(a=1)
        g = _safe_getter(obj)
        assert g("a") == 1
        assert g("missing") is None

    def test_safe_getter_none(self):
        g = _safe_getter(None)
        assert g("anything") is None

    def test_dump_with_dict(self):
        assert _dump({"a": 1}) == {"a": 1}

    def test_dump_with_pydantic_like(self):
        class M:
            def model_dump(self):
                return {"x": 1}

        assert _dump(M()) == {"x": 1}

    def test_dump_with_none(self):
        assert _dump(None) is None

    def test_dump_with_plain_object(self):
        # Object without model_dump - returns None
        class M:
            pass

        assert _dump(M()) is None

    def test_convert_tool(self):
        raw = SimpleNamespace(
            name="search",
            description="Search",
            inputSchema={"type": "object"},
            outputSchema=None,
            title="Search",
            annotations=None,
        )
        spec = _convert_tool(raw)
        assert spec.name == "search"
        assert spec.description == "Search"
        assert spec.title == "Search"

    def test_convert_tool_with_dict(self):
        raw = {
            "name": "x",
            "description": "y",
            "inputSchema": {},
        }
        spec = _convert_tool(raw)
        assert spec.name == "x"

    def test_convert_content_text(self):
        c = _convert_content(SimpleNamespace(type="text", text="hi"))
        assert c.kind == "text"
        assert c.text == "hi"

    def test_convert_content_image(self):
        c = _convert_content(
            SimpleNamespace(type="image", data="b64", mimeType="image/png")
        )
        assert c.kind == "image"
        assert c.data == "b64"
        assert c.mime_type == "image/png"

    def test_convert_content_audio(self):
        c = _convert_content(
            SimpleNamespace(type="audio", data="b64", mimeType="audio/mp3")
        )
        assert c.kind == "audio"
        assert c.mime_type == "audio/mp3"

    def test_convert_content_resource(self):
        c = _convert_content(
            SimpleNamespace(
                type="resource",
                resource=SimpleNamespace(
                    text="x", uri="file:///x", mimeType="text/plain"
                ),
            )
        )
        assert c.kind == "resource"
        assert c.text == "x"
        assert c.uri == "file:///x"

    def test_convert_content_unknown(self):
        c = _convert_content(SimpleNamespace(type="weird"))
        assert c.kind == "unknown"

    def test_convert_result_full(self):
        raw = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            structuredContent={"a": 1},
            isError=False,
            meta=None,
        )
        r = _convert_result(raw)
        assert r.structured == {"a": 1}
        assert r.is_error is False
        assert r.join_text() == "hello"

    def test_convert_result_is_error_true(self):
        raw = SimpleNamespace(
            content=[],
            structuredContent=None,
            isError=True,
            meta=None,
        )
        r = _convert_result(raw)
        assert r.is_error is True
