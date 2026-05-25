"""Example 06: catching every MCP-specific error class.

Demonstrates the public exception hierarchy and how to react to each:

    MCPError          (base, inherits from nucleusiq.tools.errors.ToolError)
      ├─ MCPConnectionError   — transport failed, server unreachable
      ├─ MCPAuthError         — credentials missing / rejected
      ├─ MCPTimeoutError      — RPC took longer than ``timeout_seconds``
      ├─ MCPProtocolError     — server returned malformed / unexpected JSON-RPC
      └─ MCPToolError         — server returned ``isError=True`` from tools/call
                                (also inherits ToolExecutionError so the
                                 executor / plugins handle it uniformly)
"""

from __future__ import annotations

import asyncio
import os

from nucleusiq_mcp import (
    BearerAuth,
    MCPAuthError,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPTool,
    MCPToolError,
)


async def try_connect(tool: MCPTool) -> None:
    try:
        await tool.connect()
        bound = await tool.expand()
        for t in bound:
            try:
                await t.execute()  # may raise MCPToolError
            except MCPToolError as exc:
                print(f"  ! tool error: {exc.tool_name} → {exc!s}")
    except MCPAuthError as exc:
        print(f"  ! auth: server rejected credentials → {exc!s}")
    except MCPConnectionError as exc:
        print(f"  ! connection: cannot reach server → {exc!s}")
    except MCPTimeoutError as exc:
        print(f"  ! timeout: server too slow → {exc!s}")
    except MCPProtocolError as exc:
        print(f"  ! protocol: malformed response → {exc!s}")
    except MCPError as exc:
        # Fallback — any future subclass we add.
        print(f"  ! mcp: {type(exc).__name__}: {exc!s}")
    finally:
        await tool.disconnect()


async def main() -> None:
    # 1) Bad host → MCPConnectionError
    print("\n[1] Unreachable host:")
    await try_connect(MCPTool("https://nope.invalid.example/mcp", timeout_seconds=3.0))

    # 2) Bad token → MCPAuthError (server returns 401/403)
    if os.environ.get("MY_MCP_URL"):
        print("\n[2] Bad bearer token:")
        await try_connect(
            MCPTool(os.environ["MY_MCP_URL"], auth=BearerAuth("definitely-not-valid"))
        )

    # 3) Bogus stdio command → MCPConnectionError
    print("\n[3] Non-existent stdio command:")
    await try_connect(MCPTool("nope-no-such-mcp-binary"))


if __name__ == "__main__":
    asyncio.run(main())
