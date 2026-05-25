"""Shared fixtures for live MCP integration tests.

These tests are **opt-in** — they run only when invoked with::

    pytest -m integration

They spin up the official ``@modelcontextprotocol/server-everything``
reference MCP server (which ships all three transports — stdio, SSE,
Streamable HTTP) and exercise our adapter against it end-to-end.

Requirements:
    * ``node`` and ``npx`` on PATH (Node.js 18+ recommended)
    * Internet access on the first run so ``npx -y`` can fetch the
      package; cached afterwards.

We deliberately do not gate on environment variables — these are
pure transport / protocol tests, not auth tests.  See
``tests/integration/test_with_anthropic.py`` for tests that DO need
``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import closing

import pytest


def _find_free_port() -> int:
    """Return an OS-assigned free TCP port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    """Block until ``(host, port)`` accepts a TCP connection."""
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.settimeout(1.0)
                s.connect((host, port))
                return
        except OSError as exc:
            last_err = exc
            time.sleep(0.2)
    raise TimeoutError(
        f"MCP test server did not start on {host}:{port} within {timeout}s "
        f"(last error: {last_err!r})"
    )


def _npx_path() -> str | None:
    """Return the absolute path to ``npx`` or ``None`` if missing."""
    return shutil.which("npx")


# Skip *all* integration tests cleanly if Node is unavailable so CI on
# minimal images doesn't fail spuriously.
requires_node = pytest.mark.skipif(
    _npx_path() is None,
    reason="npx not on PATH; install Node.js to run MCP integration tests",
)


@pytest.fixture(scope="session")
def npx() -> str:
    """Absolute path to the system ``npx``."""
    p = _npx_path()
    if p is None:
        pytest.skip("npx unavailable")
    return p


@pytest.fixture
def stdio_command() -> str:
    """Command line that launches the reference server on stdio."""
    # We intentionally use the package as-is (no flag) — server-everything
    # defaults to stdio mode.
    return "npx -y @modelcontextprotocol/server-everything"


@pytest.fixture
def http_server(npx: str) -> Iterator[str]:
    """Start the reference server in *Streamable HTTP* mode on a free port.

    Yields the base URL.  Tears down on teardown.
    """
    port = _find_free_port()
    env = {**os.environ, "PORT": str(port)}
    proc = subprocess.Popen(
        [npx, "-y", "@modelcontextprotocol/server-everything", "streamableHttp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        shell=False,
    )
    try:
        _wait_for_port("127.0.0.1", port, timeout=60.0)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture
def sse_server(npx: str) -> Iterator[str]:
    """Start the reference server in *SSE* mode on a free port.

    Yields the base URL.  Tears down on teardown.
    """
    port = _find_free_port()
    env = {**os.environ, "PORT": str(port)}
    proc = subprocess.Popen(
        [npx, "-y", "@modelcontextprotocol/server-everything", "sse"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        shell=False,
    )
    try:
        _wait_for_port("127.0.0.1", port, timeout=60.0)
        yield f"http://127.0.0.1:{port}/sse"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
