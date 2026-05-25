"""Tests for the retry helper."""

from __future__ import annotations

import pytest

from nucleusiq_mcp.exceptions import (
    MCPAuthError,
    MCPProtocolError,
)
from nucleusiq_mcp.retry import (
    DEFAULT_MAX_RETRIES,
    looks_transient,
    rate_limit_sleep,
    sleep_with_cancel,
)


class TestLooksTransient:
    @pytest.mark.parametrize(
        "msg",
        [
            "rate limit exceeded",
            "Rate-limit hit",
            "429 too many requests",
            "503 service unavailable",
            "connection reset by peer",
            "connection aborted",
            "request timed out",
        ],
    )
    def test_transient_markers_detected(self, msg):
        exc = MCPProtocolError(msg)
        assert looks_transient(exc)

    def test_non_transient(self):
        exc = MCPProtocolError("schema validation failed")
        assert not looks_transient(exc)

    def test_empty_message(self):
        exc = MCPProtocolError("")
        assert not looks_transient(exc)

    def test_auth_error_not_transient(self):
        exc = MCPAuthError("invalid token")
        assert not looks_transient(exc)


class TestRateLimitSleep:
    def test_returns_positive_for_first_attempt(self):
        s = rate_limit_sleep(1)
        assert s > 0

    def test_capped(self):
        # Even at high attempts the cap is enforced.
        s = rate_limit_sleep(20)
        from nucleusiq.llms.retry_policy import DEFAULT_RATE_LIMIT_MAX_SLEEP_SECONDS

        assert s <= DEFAULT_RATE_LIMIT_MAX_SLEEP_SECONDS

    def test_honors_retry_after_header(self):
        s = rate_limit_sleep(1, retry_after_header="5")
        assert s >= 5

    def test_invalid_retry_after_falls_back_to_exponential(self):
        s = rate_limit_sleep(1, retry_after_header="not-a-number")
        assert s > 0


@pytest.mark.asyncio
class TestSleepWithCancel:
    async def test_negative_is_noop(self):
        await sleep_with_cancel(-1)
        await sleep_with_cancel(0)

    async def test_positive_sleeps(self):
        import time

        start = time.monotonic()
        await sleep_with_cancel(0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04


class TestConstants:
    def test_default_max_retries_reasonable(self):
        assert DEFAULT_MAX_RETRIES >= 1
        assert DEFAULT_MAX_RETRIES <= 5
