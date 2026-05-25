"""Tests for the auth strategies."""

from __future__ import annotations

import pytest

from nucleusiq_mcp.auth import (
    BearerAuth,
    CustomHeadersAuth,
    EnvAuth,
    MCPAuth,
    OAuthAuth,
    build_auth,
)
from nucleusiq_mcp.exceptions import MCPAuthError


class TestBearerAuth:
    def test_basic(self):
        a = BearerAuth("xoxb-123")
        assert a.apply_headers() == {"Authorization": "Bearer xoxb-123"}

    def test_httpx_auth_is_none(self):
        assert BearerAuth("t").httpx_auth() is None

    def test_repr_redacts_token(self):
        a = BearerAuth("super-secret")
        r = repr(a)
        assert "super-secret" not in r
        assert "redacted" in r

    def test_empty_token_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            BearerAuth("")

    def test_whitespace_token_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            BearerAuth("   ")

    def test_satisfies_protocol(self):
        assert isinstance(BearerAuth("t"), MCPAuth)


class TestEnvAuth:
    def test_reads_env(self, monkeypatch):
        monkeypatch.setenv("MY_TOK", "abc")
        a = EnvAuth("MY_TOK")
        assert a.apply_headers() == {"Authorization": "Bearer abc"}

    def test_custom_header_and_scheme(self, monkeypatch):
        monkeypatch.setenv("K", "secret")
        a = EnvAuth("K", header="X-API-Key", scheme="")
        assert a.apply_headers() == {"X-API-Key": "secret"}

    def test_required_missing_raises(self, monkeypatch):
        monkeypatch.delenv("ABSENT", raising=False)
        a = EnvAuth("ABSENT")
        with pytest.raises(MCPAuthError):
            a.apply_headers()

    def test_optional_missing_returns_empty(self, monkeypatch):
        monkeypatch.delenv("ABSENT", raising=False)
        a = EnvAuth("ABSENT", required=False)
        assert a.apply_headers() == {}

    def test_lazy_resolution(self, monkeypatch):
        a = EnvAuth("LATE")
        monkeypatch.setenv("LATE", "v1")
        assert a.apply_headers() == {"Authorization": "Bearer v1"}
        monkeypatch.setenv("LATE", "v2")  # rotation
        assert a.apply_headers() == {"Authorization": "Bearer v2"}

    def test_empty_env_var_name_rejected(self):
        with pytest.raises(ValueError, match="non-empty env_var"):
            EnvAuth("")

    def test_repr_shows_env_var_only(self):
        r = repr(EnvAuth("MY_TOK"))
        assert "MY_TOK" in r

    def test_httpx_auth_is_none(self):
        assert EnvAuth("X").httpx_auth() is None


class TestCustomHeadersAuth:
    def test_basic(self):
        a = CustomHeadersAuth({"X-API-Key": "secret"})
        assert a.apply_headers() == {"X-API-Key": "secret"}

    def test_multiple_headers(self):
        a = CustomHeadersAuth({"X-A": "1", "X-B": "2"})
        h = a.apply_headers()
        assert h["X-A"] == "1"
        assert h["X-B"] == "2"

    def test_defensive_copy(self):
        src = {"X-A": "1"}
        a = CustomHeadersAuth(src)
        src["X-A"] = "MUTATED"
        assert a.apply_headers()["X-A"] == "1"

    def test_apply_returns_copy(self):
        a = CustomHeadersAuth({"X-A": "1"})
        h = a.apply_headers()
        h["X-A"] = "MUTATED"
        assert a.apply_headers()["X-A"] == "1"

    def test_empty_dict_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            CustomHeadersAuth({})

    def test_repr_redacts_values(self):
        a = CustomHeadersAuth({"X-Secret": "topsecret"})
        r = repr(a)
        assert "topsecret" not in r
        assert "X-Secret" in r

    def test_httpx_auth_is_none(self):
        assert CustomHeadersAuth({"X": "y"}).httpx_auth() is None


class TestOAuthAuth:
    def test_requires_provider_or_factory(self):
        with pytest.raises(ValueError, match="provider or a factory"):
            OAuthAuth()

    def test_cannot_pass_both(self):
        with pytest.raises(ValueError, match="not both"):
            OAuthAuth(provider=object(), factory=lambda: object())

    def test_apply_headers_returns_empty(self):
        a = OAuthAuth(provider=object())
        assert a.apply_headers() == {}

    def test_httpx_auth_returns_provider(self):
        provider = object()
        a = OAuthAuth(provider=provider)
        assert a.httpx_auth() is provider

    def test_factory_called_lazily(self):
        calls = []

        def factory():
            calls.append(1)
            return "provider"

        a = OAuthAuth(factory=factory)
        assert calls == []  # not called at construction
        assert a.httpx_auth() == "provider"
        assert calls == [1]
        # Cached — second call doesn't invoke factory again.
        assert a.httpx_auth() == "provider"
        assert calls == [1]

    def test_repr(self):
        r = repr(OAuthAuth(provider=object()))
        assert "OAuth" in r


class TestBuildAuth:
    def test_none_returns_none(self):
        assert build_auth(None) is None

    def test_string_returns_bearer(self):
        a = build_auth("xoxb-x")
        assert isinstance(a, BearerAuth)
        assert a.apply_headers() == {"Authorization": "Bearer xoxb-x"}

    def test_dict_returns_custom_headers(self):
        a = build_auth({"X-Key": "v"})
        assert isinstance(a, CustomHeadersAuth)

    def test_existing_auth_returned_as_is(self):
        src = EnvAuth("X")
        assert build_auth(src) is src

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Unsupported auth value"):
            build_auth(42)
