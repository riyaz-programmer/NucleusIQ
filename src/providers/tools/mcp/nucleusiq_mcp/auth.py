"""Authentication strategies for HTTP-based MCP transports.

We use the **Strategy pattern** (DIP / OCP from SOLID) so the session
layer depends on the abstract :class:`MCPAuth` protocol — not on any
specific scheme.  Users mix and match concrete strategies:

* :class:`BearerAuth`         — raw bearer token string
* :class:`EnvAuth`            — read bearer token from an env var
* :class:`CustomHeadersAuth`  — arbitrary header dict (escape hatch)
* :class:`OAuthAuth`          — full OAuth 2.1 + PKCE via the MCP SDK

All strategies expose the same two methods so the session never needs
to know which scheme is in play.  Stdio servers do not use auth (the
parent-process trust model already covers them).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from nucleusiq_mcp.exceptions import MCPAuthError

if TYPE_CHECKING:
    # Heavy SDK type imported only when needed (avoids forcing OAuth deps
    # on users who only need bearer / env auth).
    pass

__all__ = [
    "MCPAuth",
    "BearerAuth",
    "EnvAuth",
    "CustomHeadersAuth",
    "OAuthAuth",
    "build_auth",
]


# ====================================================================== #
# Protocol — the Strategy interface                                        #
# ====================================================================== #


@runtime_checkable
class MCPAuth(Protocol):
    """Strategy interface for MCP HTTP authentication.

    ``apply_headers``
        Synchronous — return the headers to add to every HTTP request.
        Used by simple schemes (bearer, custom headers, env-derived).

    ``httpx_auth``
        Optional — return an ``httpx.Auth`` instance that the MCP SDK
        will use directly (handles refresh / PKCE flows).  Return
        ``None`` when ``apply_headers`` is sufficient.

    Concrete implementations should choose exactly one mechanism —
    either return headers, OR return an httpx.Auth — never both.
    """

    def apply_headers(self) -> dict[str, str]:
        """Return additional HTTP headers (may be empty)."""
        ...

    def httpx_auth(self) -> Any | None:
        """Return an :class:`httpx.Auth` for SDK-managed auth, or None."""
        ...


# ====================================================================== #
# Concrete strategies                                                      #
# ====================================================================== #


class BearerAuth:
    """Static ``Authorization: Bearer <token>`` header.

    Use for service tokens (Slack ``xoxb-``, GitHub PAT, etc.) where
    the value is already minted and rotation is handled out-of-band.

    Example:
        >>> auth = BearerAuth("xoxb-1234")
        >>> auth.apply_headers()
        {'Authorization': 'Bearer xoxb-1234'}
    """

    __slots__ = ("_token",)

    def __init__(self, token: str) -> None:
        if not token or not str(token).strip():
            raise ValueError("BearerAuth requires a non-empty token")
        self._token = str(token).strip()

    def apply_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def httpx_auth(self) -> Any | None:
        return None

    def __repr__(self) -> str:
        # NEVER include the token — secrets must not leak via repr / logs.
        return "BearerAuth(token=<redacted>)"


class EnvAuth:
    """Bearer auth where the token is fetched from an environment variable.

    Resolution happens lazily at :meth:`apply_headers` time — so rotating
    the env var between executions takes effect on the next call without
    rebuilding the agent.

    Args:
        env_var: The environment variable name (e.g. ``"SLACK_BOT_TOKEN"``).
        header: HTTP header name (default ``"Authorization"``).
        scheme: Token scheme prefix (default ``"Bearer"``; pass ``""``
            for raw token without a scheme prefix).
        required: When True (default), raises :class:`MCPAuthError` if
            the env var is missing at lookup time.  Set False to fall
            back silently (e.g. for tools that work anonymously).
    """

    __slots__ = ("_env_var", "_header", "_scheme", "_required")

    def __init__(
        self,
        env_var: str,
        *,
        header: str = "Authorization",
        scheme: str = "Bearer",
        required: bool = True,
    ) -> None:
        if not env_var:
            raise ValueError("EnvAuth requires a non-empty env_var name")
        self._env_var = env_var
        self._header = header
        self._scheme = scheme
        self._required = required

    def apply_headers(self) -> dict[str, str]:
        token = os.environ.get(self._env_var, "").strip()
        if not token:
            if self._required:
                raise MCPAuthError(
                    f"Required environment variable {self._env_var!r} is "
                    f"not set or empty",
                )
            return {}
        value = f"{self._scheme} {token}".strip() if self._scheme else token
        return {self._header: value}

    def httpx_auth(self) -> Any | None:
        return None

    def __repr__(self) -> str:
        return f"EnvAuth(env_var={self._env_var!r})"


class CustomHeadersAuth:
    """Arbitrary static headers (escape hatch for non-standard schemes).

    Use for vendor-specific headers like ``X-API-Key``, mTLS proxies,
    or multi-header schemes.

    Example:
        >>> auth = CustomHeadersAuth({"X-API-Key": "secret", "X-Tenant": "acme"})
    """

    __slots__ = ("_headers",)

    def __init__(self, headers: dict[str, str]) -> None:
        if not headers:
            raise ValueError("CustomHeadersAuth requires at least one header")
        # Defensive copy — caller mutations must not affect our state.
        self._headers = dict(headers)

    def apply_headers(self) -> dict[str, str]:
        return dict(self._headers)

    def httpx_auth(self) -> Any | None:
        return None

    def __repr__(self) -> str:
        # Show keys but redact values.
        keys = list(self._headers)
        return f"CustomHeadersAuth(headers={keys!r}, values=<redacted>)"


class OAuthAuth:
    """OAuth 2.1 + PKCE via the official MCP SDK.

    This strategy returns an :class:`mcp.client.auth.OAuthClientProvider`
    (which is an ``httpx.Auth``) so the SDK handles the full flow —
    authorization, token caching, refresh.  We simply wire it up.

    Because the SDK's ``OAuthClientProvider`` requires several inputs
    (client metadata, token storage, redirect handler, callback handler),
    we accept either:

    * A **pre-built** :class:`OAuthClientProvider` — for advanced users
      who already have token storage set up.
    * A factory callable returning one — for lazy construction (the
      factory is only invoked the first time the session needs auth).

    Example::

        from mcp.client.auth import OAuthClientProvider
        from mcp.shared.auth import OAuthClientMetadata

        provider = OAuthClientProvider(
            server_url="https://mcp.example.com",
            client_metadata=OAuthClientMetadata(
                client_name="my-app",
                redirect_uris=["http://localhost:8000/callback"],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope="read write",
            ),
            storage=my_token_storage,           # implements TokenStorage
            redirect_handler=open_browser,      # async def(str) -> None
            callback_handler=wait_for_callback, # async def() -> (code, state)
        )
        MCPTool("https://mcp.example.com/api", auth=OAuthAuth(provider=provider))

    Adding convenience constructors (browser-based defaults, in-memory
    token storage, etc.) is OCP-clean — extend with new factory helpers
    instead of modifying this class.
    """

    __slots__ = ("_provider", "_factory")

    def __init__(
        self,
        provider: Any | None = None,
        *,
        factory: Any | None = None,
    ) -> None:
        if provider is None and factory is None:
            raise ValueError(
                "OAuthAuth requires either a provider or a factory callable"
            )
        if provider is not None and factory is not None:
            raise ValueError("OAuthAuth: pass provider OR factory, not both")
        self._provider = provider
        self._factory = factory

    def apply_headers(self) -> dict[str, str]:
        # OAuth flow is delegated entirely to the httpx.Auth instance;
        # we never inject a static Authorization header ourselves.
        return {}

    def httpx_auth(self) -> Any | None:
        if self._provider is not None:
            return self._provider
        # Lazy construction
        assert self._factory is not None
        provider = self._factory()
        self._provider = provider
        return provider

    def __repr__(self) -> str:
        return "OAuthAuth(provider=<OAuthClientProvider>)"


# ====================================================================== #
# Convenience builder (DIP — callers depend on protocol, not concretes)    #
# ====================================================================== #


def build_auth(value: Any) -> MCPAuth | None:
    """Coerce a user-facing ``auth=...`` value into an :class:`MCPAuth`.

    Behaviour matches the design doc §6.1:

    * ``None``                              → ``None`` (no auth)
    * already an :class:`MCPAuth`           → returned as-is
    * ``str``                               → :class:`BearerAuth`
    * ``dict``                              → :class:`CustomHeadersAuth`
    * anything else                         → raises :class:`TypeError`

    This is the single coercion point used by :class:`MCPTool` so the
    matrix is defined in exactly one place.
    """
    if value is None:
        return None
    if isinstance(value, MCPAuth):
        return value
    if isinstance(value, str):
        return BearerAuth(value)
    if isinstance(value, dict):
        return CustomHeadersAuth(value)
    raise TypeError(
        f"Unsupported auth value of type {type(value).__name__}; "
        f"expected None, str, dict, or an MCPAuth strategy"
    )
