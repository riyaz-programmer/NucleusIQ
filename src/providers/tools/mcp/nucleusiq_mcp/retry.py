"""Retry coordination for MCP RPCs.

This module is a thin adapter on top of
:mod:`nucleusiq.llms.retry_policy` so the MCP package shares the same
backoff caps and observability semantics as NucleusIQ's LLM providers
(see :class:`nucleusiq.llms.retry_policy.RateLimitRetryMeta`).

We intentionally keep the retry surface very small:

* Only ``call_tool`` retries are configurable (list_tools is rare).
* Only HTTP transports actually benefit — stdio servers do not return
  429s.  The session checks the transport before invoking the retry.
* We never retry on auth, validation, or tool errors — those are
  permanent.  We only retry on :class:`MCPTimeoutError` and
  :class:`MCPProtocolError` whose root cause looks transient
  (``"429"``, ``"rate limit"``, ``"unavailable"``).

Following SRP — this module owns *only* the retry decision.  The session
owns the call itself.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from nucleusiq.llms.retry_policy import (
    DEFAULT_RATE_LIMIT_MAX_SLEEP_SECONDS,
    compute_rate_limit_sleep,
)

if TYPE_CHECKING:
    from nucleusiq_mcp.exceptions import MCPError

__all__ = [
    "looks_transient",
    "rate_limit_sleep",
    "DEFAULT_MAX_RETRIES",
]


DEFAULT_MAX_RETRIES = 2

_logger = logging.getLogger(__name__)


# Substrings (lowercased) that, when present in an exception message,
# indicate the failure is likely transient and worth retrying.
_TRANSIENT_MARKERS = (
    "429",
    "rate limit",
    "rate-limit",
    "too many requests",
    "503",
    "unavailable",
    "temporarily",
    "timed out",
    "connection reset",
    "connection aborted",
)


def looks_transient(exc: MCPError) -> bool:
    """Heuristic check: does the exception look retryable?

    We deliberately keep this conservative.  False positives waste
    time but never corrupt state; false negatives just surface the
    error (which is what the caller wanted anyway).
    """
    msg = (str(exc) or "").lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def rate_limit_sleep(
    attempt: int,
    *,
    retry_after_header: str | None = None,
    max_sleep_seconds: float = DEFAULT_RATE_LIMIT_MAX_SLEEP_SECONDS,
) -> float:
    """Compute how long to sleep before the next retry.

    Delegates to :func:`nucleusiq.llms.retry_policy.compute_rate_limit_sleep`
    so we share NucleusIQ's standard exponential-with-cap policy.
    Returns just the seconds — the structured metadata is logged at
    DEBUG level for observability.
    """
    sleep, meta = compute_rate_limit_sleep(
        attempt,
        retry_after_header,
        max_sleep_seconds=max_sleep_seconds,
    )
    _logger.debug("mcp.retry.rate_limit_sleep meta=%r", dict(meta))
    return sleep


async def sleep_with_cancel(seconds: float) -> None:
    """Sleep without swallowing cancellation."""
    if seconds <= 0:
        return
    await asyncio.sleep(seconds)
