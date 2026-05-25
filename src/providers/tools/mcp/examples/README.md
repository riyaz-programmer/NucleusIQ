# `nucleusiq-mcp` examples

Each example is a single, runnable Python file. To run any of them:

```bash
pip install -e ".[examples]"
python examples/<name>.py
```

| File | What it shows |
|------|---------------|
| [`01_basic_stdio.py`](01_basic_stdio.py) | Connecting a local MCP server over stdio (no auth). |
| [`02_http_with_auth.py`](02_http_with_auth.py) | Streamable HTTP transport + `EnvAuth` + filtering tools with `MCPToolset`. |
| [`03_multi_server.py`](03_multi_server.py) | Multiple MCP servers in one agent + per-server prefix + collision policy. |
| [`04_low_level_session.py`](04_low_level_session.py) | Using `MCPSession` directly without `Agent` (for scripts / discovery). |
| [`05_oauth.py`](05_oauth.py) | OAuth 2.1 + PKCE wiring via the official MCP SDK provider. |
| [`06_error_handling.py`](06_error_handling.py) | Catching every error class — connection, auth, timeout, protocol, tool. |
| [`07_decorator_filters.py`](07_decorator_filters.py) | Decorator-style tool filters: `@mcp_tool_filter`, `MCPToolset`. |
| [`08_full_agent_with_llm.py`](08_full_agent_with_llm.py) | End-to-end agent that uses MCP tools through an LLM (OpenAI). |

All examples are environment-aware — they read from `os.environ` and
skip cleanly when the required server/token is not configured.
