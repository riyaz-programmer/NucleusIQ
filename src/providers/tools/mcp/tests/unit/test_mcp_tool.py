"""Tests for the public MCPTool facade."""

from __future__ import annotations

import pytest
from nucleusiq.tools import ExpandableTool

from nucleusiq_mcp.auth import BearerAuth, CustomHeadersAuth, EnvAuth
from nucleusiq_mcp.bound_tool import MCPBoundTool
from nucleusiq_mcp.config import MCPTransport
from nucleusiq_mcp.mcp_tool import MCPTool
from nucleusiq_mcp.models import MCPToolSpec
from tests.unit.conftest import FakeMCPSession

# ====================================================================== #
# Construction / config                                                    #
# ====================================================================== #


class TestConstruction:
    def test_url_auto_infers_streamable_http(self):
        tool = MCPTool("https://mcp.example.com")
        assert tool.config.transport == MCPTransport.STREAMABLE_HTTP

    def test_stdio_inferred_for_command(self):
        tool = MCPTool("npx -y @org/srv")
        assert tool.config.transport == MCPTransport.STDIO

    def test_string_auth_becomes_bearer(self):
        tool = MCPTool("https://x.com", auth="xoxb-1")
        assert isinstance(tool.config.auth, BearerAuth)

    def test_dict_auth_becomes_custom_headers(self):
        tool = MCPTool("https://x.com", auth={"X-API-Key": "v"})
        assert isinstance(tool.config.auth, CustomHeadersAuth)

    def test_env_auth_passed_through(self):
        a = EnvAuth("MY_TOKEN")
        tool = MCPTool("https://x.com", auth=a)
        assert tool.config.auth is a

    def test_invalid_collision_policy_rejected(self):
        with pytest.raises(ValueError, match="on_collision"):
            MCPTool("https://x.com", on_collision="bogus")

    def test_satisfies_expandable_protocol(self):
        tool = MCPTool("https://x.com")
        assert isinstance(tool, ExpandableTool)

    def test_repr_includes_server(self):
        tool = MCPTool("https://x.com", name="ex")
        r = repr(tool)
        assert "ex" in r
        assert "streamable_http" in r

    def test_explicit_name_used(self):
        tool = MCPTool("https://x.com", name="custom")
        assert tool.name == "custom"

    def test_rename_accepts_dict(self):
        tool = MCPTool("https://x.com", rename={"foo": "bar"})
        renamer = tool._rename
        assert renamer("foo") == "bar"
        assert renamer("baz") == "baz"

    def test_rename_accepts_callable(self):
        tool = MCPTool("https://x.com", rename=lambda n: n.upper())
        assert tool._rename("x") == "X"

    def test_rename_invalid_type(self):
        with pytest.raises(TypeError):
            MCPTool("https://x.com", rename=42)


# ====================================================================== #
# expand() — filtering, prefixing, collisions                              #
# ====================================================================== #


def _make_tool_with_fake_session(
    *,
    tool_specs: list[MCPToolSpec],
    **kwargs,
) -> tuple[MCPTool, FakeMCPSession]:
    """Build an MCPTool and pre-inject a FakeMCPSession bypassing connect."""
    tool = MCPTool("https://x.com", name="ex", **kwargs)
    fake = FakeMCPSession(config=tool.config, tools=tool_specs)
    tool._session = fake  # type: ignore[attr-defined]
    return tool, fake


@pytest.mark.asyncio
class TestExpand:
    async def test_expand_before_connect_raises(self):
        tool = MCPTool("https://x.com")
        with pytest.raises(RuntimeError, match="connect"):
            await tool.expand()

    async def test_expand_returns_bound_tools(self):
        specs = [
            MCPToolSpec(name="search", description="Search"),
            MCPToolSpec(name="list", description="List"),
        ]
        tool, fake = _make_tool_with_fake_session(tool_specs=specs)
        await fake.connect()
        bound = await tool.expand()
        assert len(bound) == 2
        assert all(isinstance(b, MCPBoundTool) for b in bound)
        assert sorted(b.name for b in bound) == ["list", "search"]

    async def test_include_tools_whitelist(self):
        specs = [MCPToolSpec(name="search"), MCPToolSpec(name="list")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, include_tools=["search"]
        )
        await fake.connect()
        bound = await tool.expand()
        assert [b.name for b in bound] == ["search"]

    async def test_exclude_tools_blacklist(self):
        specs = [MCPToolSpec(name="search"), MCPToolSpec(name="dangerous")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, exclude_tools=["dangerous"]
        )
        await fake.connect()
        bound = await tool.expand()
        assert [b.name for b in bound] == ["search"]

    async def test_tool_filter_callable(self):
        specs = [
            MCPToolSpec(name="get_x"),
            MCPToolSpec(name="set_x"),
            MCPToolSpec(name="get_y"),
        ]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs,
            tool_filter=lambda s: s.name.startswith("get_"),
        )
        await fake.connect()
        bound = await tool.expand()
        names = sorted(b.name for b in bound)
        assert names == ["get_x", "get_y"]

    async def test_prefix_applied(self):
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(tool_specs=specs, prefix="gh")
        await fake.connect()
        bound = await tool.expand()
        assert bound[0].name == "gh_search"
        assert bound[0].remote_name == "search"

    async def test_rename_with_dict(self):
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, rename={"search": "find"}
        )
        await fake.connect()
        bound = await tool.expand()
        assert bound[0].name == "find"
        assert bound[0].remote_name == "search"

    async def test_rename_with_callable(self):
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, rename=lambda n: n.upper()
        )
        await fake.connect()
        bound = await tool.expand()
        assert bound[0].name == "SEARCH"

    async def test_collision_auto_prefix(self):
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(tool_specs=specs)
        await fake.connect()
        bound = await tool.expand(existing_names={"search"})
        # Auto-prefixed with server name "ex_".
        assert bound[0].name == "ex_search"

    async def test_collision_skip(self):
        specs = [MCPToolSpec(name="search"), MCPToolSpec(name="other")]
        tool, fake = _make_tool_with_fake_session(tool_specs=specs, on_collision="skip")
        await fake.connect()
        bound = await tool.expand(existing_names={"search"})
        # Only "other" survives.
        assert [b.name for b in bound] == ["other"]

    async def test_collision_raise(self):
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, on_collision="raise"
        )
        await fake.connect()
        with pytest.raises(ValueError, match="collides"):
            await tool.expand(existing_names={"search"})

    async def test_internal_collision_within_adapter(self):
        # Two tools that, after rename, end up with the same final name.
        specs = [MCPToolSpec(name="a"), MCPToolSpec(name="b")]
        tool, fake = _make_tool_with_fake_session(
            tool_specs=specs, rename={"a": "x", "b": "x"}
        )
        await fake.connect()
        bound = await tool.expand()
        # First wins (kept as "x"); second collides and is auto-prefixed.
        names = sorted(b.name for b in bound)
        assert "x" in names
        assert "ex_x" in names


@pytest.mark.asyncio
class TestLifecycle:
    async def test_connect_idempotent(self):
        tool = MCPTool("https://x.com", name="ex")
        fake = FakeMCPSession(config=tool.config, tools=[])
        tool._session = fake
        await tool.connect()
        await tool.connect()  # second call must not fail
        # FakeMCPSession.connect_calls is incremented twice but disconnect
        # idempotency at session level is its own concern.
        assert fake.connect_calls == 2

    async def test_disconnect_with_no_session(self):
        tool = MCPTool("https://x.com")
        await tool.disconnect()  # must not raise

    async def test_disconnect_after_connect(self):
        tool = MCPTool("https://x.com", name="ex")
        fake = FakeMCPSession(config=tool.config)
        tool._session = fake
        await tool.connect()
        await tool.disconnect()
        assert fake.disconnect_calls == 1


class TestProperties:
    def test_config_property(self):
        tool = MCPTool("https://x.com", name="ex")
        assert tool.config.name == "ex"

    def test_session_starts_none(self):
        tool = MCPTool("https://x.com")
        assert tool.session is None


@pytest.mark.asyncio
class TestExpandEdgeCases:
    async def test_double_collision_with_auto_prefix_drops_tool(self):
        # If the auto-prefixed name *also* collides, the tool is dropped.
        specs = [MCPToolSpec(name="search")]
        tool, fake = _make_tool_with_fake_session(tool_specs=specs)
        await fake.connect()
        # Both "search" and "ex_search" already exist on the agent.
        bound = await tool.expand(existing_names={"search", "ex_search"})
        assert bound == []


# ====================================================================== #
# Graceful degradation + health checks (Phase 2 hardening)                  #
# ====================================================================== #


class TestConnectFailurePolicy:
    def test_invalid_policy_rejected(self):
        with pytest.raises(ValueError, match="on_connect_failure"):
            MCPTool("https://x.com", on_connect_failure="bogus")

    def test_default_is_raise(self):
        tool = MCPTool("https://x.com")
        assert tool._on_connect_failure == "raise"

    def test_health_check_defaults_true(self):
        tool = MCPTool("https://x.com")
        assert tool._health_check is True


@pytest.mark.asyncio
class TestGracefulDegradation:
    async def test_connect_skip_swallows_error(self):
        tool = MCPTool(
            "https://x.com",
            name="ex",
            on_connect_failure="skip",
            health_check=False,
        )
        # Inject a session whose connect() blows up
        fake = FakeMCPSession(config=tool.config)

        async def boom():
            fake.connect_calls += 1
            raise RuntimeError("server is down")

        fake.connect = boom
        tool._session = fake

        await tool.connect()  # must NOT raise

        assert tool._connect_skipped is True
        assert isinstance(tool._connect_error, RuntimeError)

    async def test_skipped_expand_returns_empty(self):
        tool = MCPTool(
            "https://x.com",
            name="ex",
            on_connect_failure="skip",
            health_check=False,
        )
        fake = FakeMCPSession(config=tool.config)
        fake.connect = lambda: (_ for _ in ()).throw(  # type: ignore[assignment]
            RuntimeError("nope")
        )

        async def boom():
            raise RuntimeError("nope")

        fake.connect = boom
        tool._session = fake

        await tool.connect()
        bound = await tool.expand()
        assert bound == []

    async def test_skip_disconnects_half_open_session(self):
        tool = MCPTool(
            "https://x.com",
            on_connect_failure="skip",
            health_check=False,
        )
        fake = FakeMCPSession(config=tool.config)

        async def boom():
            fake.is_connected = True  # pretend transport was open
            raise RuntimeError("auth failed mid-handshake")

        fake.connect = boom
        tool._session = fake

        await tool.connect()

        # disconnect was invoked exactly once during cleanup.
        assert fake.disconnect_calls == 1

    async def test_raise_policy_still_propagates(self):
        tool = MCPTool(
            "https://x.com",
            on_connect_failure="raise",  # default, made explicit
            health_check=False,
        )
        fake = FakeMCPSession(config=tool.config)

        async def boom():
            raise RuntimeError("boom")

        fake.connect = boom
        tool._session = fake

        with pytest.raises(RuntimeError, match="boom"):
            await tool.connect()
        assert tool._connect_skipped is False

    async def test_skip_catches_cancelled_error(self):
        """Regression: anyio's TaskGroup re-raises a sub-task failure
        as ``asyncio.CancelledError`` (a BaseException).  The "skip"
        policy MUST swallow this — otherwise HTTP-transport graceful
        degradation silently breaks.
        """
        import asyncio as _asyncio

        tool = MCPTool(
            "https://x.com",
            on_connect_failure="skip",
            health_check=False,
        )
        fake = FakeMCPSession(config=tool.config)

        async def boom():
            raise _asyncio.CancelledError("anyio cancelled cancel scope")

        fake.connect = boom
        tool._session = fake

        await tool.connect()  # must NOT raise
        assert tool._connect_skipped is True
        assert isinstance(tool._connect_error, _asyncio.CancelledError)

    async def test_skip_does_not_swallow_keyboard_interrupt(self):
        """KeyboardInterrupt / SystemExit should always propagate."""
        tool = MCPTool(
            "https://x.com",
            on_connect_failure="skip",
            health_check=False,
        )
        fake = FakeMCPSession(config=tool.config)

        async def boom():
            raise KeyboardInterrupt()

        fake.connect = boom
        tool._session = fake

        with pytest.raises(KeyboardInterrupt):
            await tool.connect()


@pytest.mark.asyncio
class TestHealthCheckOnConnect:
    async def test_health_check_does_list_tools(self):
        tool = MCPTool("https://x.com", name="ex", health_check=True)
        fake = FakeMCPSession(config=tool.config, tools=[MCPToolSpec(name="t1")])
        tool._session = fake

        await tool.connect()
        # FakeMCPSession.list_tools doesn't track calls but we can verify
        # via the result of expand() — if the health check succeeded,
        # the session is ready and expand returns the cached tool.
        bound = await tool.expand()
        assert len(bound) == 1
        assert bound[0].name == "t1"

    async def test_health_check_failure_under_skip_swallowed(self):
        tool = MCPTool(
            "https://x.com",
            health_check=True,
            on_connect_failure="skip",
        )
        fake = FakeMCPSession(
            config=tool.config,
            list_should_raise=RuntimeError("server speaks gibberish"),
        )
        tool._session = fake

        await tool.connect()
        assert tool._connect_skipped is True

    async def test_health_check_disabled_skips_list_tools(self):
        tool = MCPTool("https://x.com", health_check=False)
        # Set up a session whose list_tools would FAIL — proves we
        # did not call it.
        fake = FakeMCPSession(
            config=tool.config,
            list_should_raise=AssertionError("must not be called"),
        )
        tool._session = fake
        await tool.connect()  # must not raise
        assert tool._connect_skipped is False


@pytest.mark.asyncio
class TestPing:
    async def test_ping_true_when_list_tools_succeeds(self):
        tool = MCPTool("https://x.com", health_check=False)
        fake = FakeMCPSession(config=tool.config, tools=[MCPToolSpec(name="t")])
        tool._session = fake
        await tool.connect()
        assert await tool.ping() is True

    async def test_ping_false_when_not_connected(self):
        tool = MCPTool("https://x.com")
        assert await tool.ping() is False

    async def test_ping_false_when_list_tools_raises(self):
        tool = MCPTool("https://x.com", health_check=False)
        fake = FakeMCPSession(
            config=tool.config,
            list_should_raise=RuntimeError("rpc down"),
        )
        tool._session = fake
        await tool.connect()
        assert await tool.ping() is False
