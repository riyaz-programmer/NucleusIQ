"""Example 05: OAuth 2.1 + PKCE via the MCP SDK provider.

This example shows how to attach a fully-fledged ``OAuthClientProvider``
to ``MCPTool``.  The SDK handles the auth code grant, PKCE, token
storage, and refresh — we just wire it in.

We use a factory so the provider is constructed lazily (no work until
the first connect).  Production deployments will plug in their own
``TokenStorage``, ``redirect_handler``, and ``callback_handler``.

Requirements:
    pip install nucleusiq-mcp 'mcp>=1.27'

NOTE:  This file is intentionally non-runnable as-is — replace the
       ``InMemoryTokenStorage`` / handlers with real ones for your
       deployment.  The point is to show the wiring.
"""

from __future__ import annotations

import asyncio
from typing import Any


async def open_browser(authorization_url: str) -> None:
    """Open the user's browser to authorize the app.

    In production, use ``webbrowser.open(authorization_url)`` or print
    the URL for the user to copy.
    """
    print(f"\n>>> Please visit:\n    {authorization_url}\n")


async def wait_for_callback() -> tuple[str, str]:
    """Block until the OAuth server redirects with the auth code.

    In production, run a tiny ``aiohttp`` / ``starlette`` server on
    ``http://localhost:<port>/callback`` and resolve a Future from the
    handler.
    """
    code = input("Paste the auth code from the redirect URL: ").strip()
    state = input("Paste the state value: ").strip()
    return code, state


class InMemoryTokenStorage:
    """Bare-minimum ``TokenStorage`` for demos.

    For production, persist to disk / secrets manager.
    """

    def __init__(self) -> None:
        self._tokens: Any | None = None
        self._client_info: Any | None = None

    async def get_tokens(self) -> Any | None:
        return self._tokens

    async def set_tokens(self, tokens: Any) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> Any | None:
        return self._client_info

    async def set_client_info(self, info: Any) -> None:
        self._client_info = info


def build_oauth_provider() -> Any:
    """Build the SDK's OAuthClientProvider.

    Imports happen inside the factory so this file is importable even
    if ``mcp`` is missing (e.g. for documentation building).
    """
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    return OAuthClientProvider(
        server_url="https://mcp.example.com",
        client_metadata=OAuthClientMetadata(
            client_name="nucleusiq-demo",
            redirect_uris=["http://localhost:8765/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write",
        ),
        storage=InMemoryTokenStorage(),
        redirect_handler=open_browser,
        callback_handler=wait_for_callback,
    )


async def main() -> None:
    from nucleusiq_mcp import MCPTool, OAuthAuth

    tool = MCPTool(
        "https://mcp.example.com/api",
        auth=OAuthAuth(factory=build_oauth_provider),
    )
    try:
        await tool.connect()
        bound = await tool.expand()
        print(f"✓ OAuth-authenticated session opened. {len(bound)} tools available.")
    finally:
        await tool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
