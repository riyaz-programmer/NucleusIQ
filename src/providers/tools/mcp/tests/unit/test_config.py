"""Tests for MCPServerConfig + MCPTransport + transport inference."""

from __future__ import annotations

import pytest
from nucleusiq_mcp.auth import BearerAuth
from nucleusiq_mcp.config import (
    MCPServerConfig,
    MCPTransport,
    _derive_name,
    infer_transport,
)
from pydantic import ValidationError


class TestInferTransport:
    def test_https_url_streamable_http(self):
        assert (
            infer_transport("https://example.com/api") == MCPTransport.STREAMABLE_HTTP
        )

    def test_http_url_streamable_http(self):
        assert infer_transport("http://localhost:3000") == MCPTransport.STREAMABLE_HTTP

    def test_https_with_whitespace(self):
        assert infer_transport(" https://x.com ") == MCPTransport.STREAMABLE_HTTP

    def test_command_is_stdio(self):
        assert infer_transport("npx -y @scope/server") == MCPTransport.STDIO

    def test_path_is_stdio(self):
        assert infer_transport("./mytool.py") == MCPTransport.STDIO

    def test_uppercase_url(self):
        assert infer_transport("HTTPS://X.COM") == MCPTransport.STREAMABLE_HTTP


class TestDeriveName:
    def test_url_returns_host(self):
        assert (
            _derive_name("https://mcp.slack.com/api", MCPTransport.STREAMABLE_HTTP)
            == "mcp.slack.com"
        )

    def test_url_with_port(self):
        assert (
            _derive_name("http://localhost:3000/mcp", MCPTransport.STREAMABLE_HTTP)
            == "localhost"
        )

    def test_stdio_npx_command(self):
        assert (
            _derive_name(
                "npx -y @modelcontextprotocol/server-github", MCPTransport.STDIO
            )
            == "server-github"
        )

    def test_stdio_python_script(self):
        assert _derive_name("./mytool.py", MCPTransport.STDIO) == "mytool.py"

    def test_stdio_forward_slash_path(self):
        assert _derive_name("/usr/local/bin/tool", MCPTransport.STDIO) == "tool"

    def test_url_invalid_returns_server(self, monkeypatch):
        # When urlparse fails or hostname is None, fall back to server.
        monkeypatch.setattr(
            "nucleusiq_mcp.config.urlparse" if False else "urllib.parse.urlparse",
            lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # Importing here to bind under patched module
        from nucleusiq_mcp.config import _derive_name as dn

        out = dn("https://", MCPTransport.STREAMABLE_HTTP)
        assert out == "https://"

    def test_stdio_single_token(self):
        assert _derive_name("tool", MCPTransport.STDIO) == "tool"


class TestMCPServerConfigBuild:
    def test_build_with_url_auto_infers(self):
        cfg = MCPServerConfig.build("https://x.com/api")
        assert cfg.transport == MCPTransport.STREAMABLE_HTTP
        assert cfg.name == "x.com"

    def test_build_with_stdio_command(self):
        cfg = MCPServerConfig.build("npx -y @org/server-x")
        assert cfg.transport == MCPTransport.STDIO
        assert cfg.name == "server-x"

    def test_build_with_explicit_transport_enum(self):
        cfg = MCPServerConfig.build("https://x.com/sse", transport=MCPTransport.SSE)
        assert cfg.transport == MCPTransport.SSE

    def test_build_with_explicit_transport_string(self):
        cfg = MCPServerConfig.build("https://x.com/api", transport="streamable_http")
        assert cfg.transport == MCPTransport.STREAMABLE_HTTP

    def test_build_with_explicit_name(self):
        cfg = MCPServerConfig.build("https://x.com", name="my-server")
        assert cfg.name == "my-server"

    def test_build_with_auth(self):
        auth = BearerAuth("xoxb-123")
        cfg = MCPServerConfig.build("https://x.com", auth=auth)
        assert cfg.auth is auth

    def test_build_with_env_and_cwd(self):
        cfg = MCPServerConfig.build(
            "tool",
            env={"K": "V"},
            cwd="/tmp",
        )
        assert cfg.env == {"K": "V"}
        assert cfg.cwd == "/tmp"

    def test_build_with_headers_and_timeout(self):
        cfg = MCPServerConfig.build(
            "https://x.com",
            headers={"X-Tenant": "acme"},
            timeout_seconds=10.0,
        )
        assert cfg.headers == {"X-Tenant": "acme"}
        assert cfg.timeout_seconds == 10.0


class TestMCPServerConfigValidation:
    def test_empty_server_rejected(self):
        with pytest.raises(ValidationError):
            MCPServerConfig.build("")

    def test_whitespace_only_server_rejected(self):
        with pytest.raises(ValidationError):
            MCPServerConfig.build("   ")

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValidationError):
            MCPServerConfig.build("tool", timeout_seconds=0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValidationError):
            MCPServerConfig.build("tool", timeout_seconds=-1)

    def test_http_transport_without_url_rejected(self):
        # Explicitly setting STREAMABLE_HTTP but providing a non-URL must fail.
        with pytest.raises(ValidationError):
            MCPServerConfig.build("not-a-url", transport=MCPTransport.STREAMABLE_HTTP)

    def test_sse_transport_without_url_rejected(self):
        with pytest.raises(ValidationError):
            MCPServerConfig.build("tool", transport=MCPTransport.SSE)

    def test_config_is_frozen(self):
        cfg = MCPServerConfig.build("https://x.com")
        # Pydantic raises ValidationError on assignment when frozen=True.
        from pydantic import ValidationError

        with pytest.raises((ValidationError, AttributeError, TypeError)):
            cfg.server = "https://y.com"  # type: ignore[misc]


class TestMCPServerConfigHelpers:
    def test_is_http_streamable(self):
        cfg = MCPServerConfig.build("https://x.com")
        assert cfg.is_http()

    def test_is_http_sse(self):
        cfg = MCPServerConfig.build("https://x.com/sse", transport=MCPTransport.SSE)
        assert cfg.is_http()

    def test_is_http_stdio(self):
        cfg = MCPServerConfig.build("tool")
        assert not cfg.is_http()

    def test_stdio_command_argv(self):
        cfg = MCPServerConfig.build("npx -y @org/srv")
        assert cfg.stdio_command_argv() == ["npx", "-y", "@org/srv"]

    def test_stdio_command_argv_rejects_http(self):
        cfg = MCPServerConfig.build("https://x.com")
        with pytest.raises(ValueError, match="STDIO"):
            cfg.stdio_command_argv()

    def test_stdio_command_argv_handles_quoted(self):
        cfg = MCPServerConfig.build('python -c "print(1)"')
        argv = cfg.stdio_command_argv()
        assert argv == ["python", "-c", "print(1)"]
