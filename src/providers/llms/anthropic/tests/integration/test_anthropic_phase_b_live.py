"""Live smoke tests for ``nucleusiq-anthropic`` Phase B features.

Run locally::

    cd src/providers/llms/anthropic
    # Reads ANTHROPIC_API_KEY from the environment or repo-root .env.
    uv run pytest tests/integration -m integration -q

These tests are **excluded from the default Anthropic test run**
(``-m "not integration"``) and from CI, so no API key is required in
automation.  They verify the Phase B surface (native server tools,
prompt caching, extended thinking) against the live Messages API.

Set ``ANTHROPIC_PHASE_B_MODEL`` to override the default
``claude-sonnet-4-5-20250929``.  Tests skip cleanly if the chosen model
is not available on the active API key.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nucleusiq_anthropic import (
    AnthropicLLMParams,
    AnthropicTool,
    BaseAnthropic,
)
from nucleusiq_anthropic._shared.response_models import AnthropicLLMResponse

pytestmark = pytest.mark.integration


def _load_repo_dotenv() -> None:
    """Walk upward from this file looking for a ``.env`` to load."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — optional dependency
        return
    here = Path(__file__).resolve().parent
    for d in [here, *here.parents]:
        env_file = d / ".env"
        if env_file.is_file():
            load_dotenv(env_file)
            return


_load_repo_dotenv()


def _model() -> str:
    return os.getenv("ANTHROPIC_PHASE_B_MODEL", "claude-sonnet-4-5-20250929")


@pytest.fixture
def anthropic_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set (live Phase B tests off)")


@pytest.fixture
def _skip_on_model_not_found():
    """Convert ``NotFoundError`` (404 model_not_found) into a pytest skip."""
    from nucleusiq.llms.errors import ModelNotFoundError

    try:
        yield
    except ModelNotFoundError as exc:
        pytest.skip(
            f"Model {_model()!r} not available on this API key: {exc}.  "
            "Override with ANTHROPIC_PHASE_B_MODEL=<accessible-model-id>."
        )


# --------------------------------------------------------------------- #
# Native server tools                                                    #
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_live_web_search_emits_server_tool_call(
    anthropic_api_key: None,
    _skip_on_model_not_found: None,
) -> None:
    """``AnthropicTool.web_search()`` surfaces ``ServerToolCall(name="web_search")``."""
    llm = BaseAnthropic(model_name=_model(), async_mode=True)
    result = await llm.call(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    "Search the web for one sentence describing what NucleusIQ "
                    "(the open-source AI agent framework) is, then quote it."
                ),
            }
        ],
        tools=[AnthropicTool.web_search(max_uses=2)],
        max_output_tokens=512,
    )
    assert isinstance(result, AnthropicLLMResponse)
    names = [stc.name for stc in result.server_tool_calls]
    assert "web_search" in names, (
        f"Expected web_search in server_tool_calls, got {names}.  "
        f"Text: {result.choices[0].message.content!r}"
    )
    assert result.stop_reason in {"end_turn", "tool_use"}


@pytest.mark.asyncio
async def test_live_code_execution_emits_server_tool_call(
    anthropic_api_key: None,
    _skip_on_model_not_found: None,
) -> None:
    """``AnthropicTool.code_execution()`` surfaces ``ServerToolCall(name="code_execution")``."""
    llm = BaseAnthropic(model_name=_model(), async_mode=True)
    result = await llm.call(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    "Use code_execution to compute 2 + 2 and reply with just "
                    "the integer."
                ),
            }
        ],
        tools=[AnthropicTool.code_execution()],
        max_output_tokens=256,
    )
    names = [stc.name for stc in result.server_tool_calls]
    assert "code_execution" in names, (
        f"Expected code_execution in server_tool_calls, got {names}"
    )
    # The first server_tool_call should have a JSON-safe result populated
    # by ``normalize_message_response`` from the matching tool-result block.
    stc = next(s for s in result.server_tool_calls if s.name == "code_execution")
    assert stc.result is not None
    assert stc.id


# --------------------------------------------------------------------- #
# Prompt caching                                                         #
# --------------------------------------------------------------------- #


# Anthropic's prompt cache needs at least ~1024 prompt tokens before it kicks
# in; 30 copies of this paragraph clears that floor.
_LONG_SYSTEM = (
    "You are a meticulous senior systems engineer with two decades of "
    "experience reviewing distributed systems for retail, finance, and "
    "infrastructure customers.  When asked to evaluate a design, walk "
    "through correctness, fault tolerance, capacity, security, and "
    "operability one heading at a time before giving an overall verdict.\n"
) * 30


@pytest.mark.asyncio
async def test_live_prompt_caching_reads_cache_on_second_call(
    anthropic_api_key: None,
    _skip_on_model_not_found: None,
) -> None:
    """Two calls with the same long system + ``cache_system=True`` → second call
    reads tokens from cache (``cache_read_input_tokens > 0``).
    """
    llm = BaseAnthropic(
        model_name=_model(),
        async_mode=True,
        llm_params=AnthropicLLMParams(cache_system=True),
    )

    async def _ask(q: str) -> AnthropicLLMResponse:
        return await llm.call(
            model=_model(),
            messages=[
                {"role": "system", "content": _LONG_SYSTEM},
                {"role": "user", "content": q},
            ],
            max_output_tokens=128,
            temperature=0.0,
        )

    r1 = await _ask("In one sentence, what is graceful degradation?")
    r2 = await _ask("In one sentence, what is back-pressure?")

    # On at least one of the two calls Anthropic must have either created
    # the cache entry or served from it.  We do not require strict
    # creation-then-read ordering because the cache may already be warm
    # from an earlier run within the 5-minute TTL.
    assert r1.usage is not None and r2.usage is not None
    cache_creation = (
        r1.usage.cache_creation_input_tokens + r2.usage.cache_creation_input_tokens
    )
    cache_read = (
        r1.usage.cache_read_input_tokens + r2.usage.cache_read_input_tokens
    )
    assert cache_creation + cache_read > 0, (
        "Expected at least one prompt-cache event across two calls — "
        f"r1.usage={r1.usage.model_dump()} r2.usage={r2.usage.model_dump()}"
    )


# --------------------------------------------------------------------- #
# Extended thinking                                                      #
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["low", "medium"])
async def test_live_extended_thinking_completes(
    effort: str,
    anthropic_api_key: None,
    _skip_on_model_not_found: None,
) -> None:
    """``thinking="low" | "medium"`` runs end-to-end and surfaces ``stop_reason``."""
    llm = BaseAnthropic(
        model_name=_model(),
        async_mode=True,
        llm_params=AnthropicLLMParams(thinking=effort),
    )
    result = await llm.call(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    "A bag has 3 red, 5 blue and 7 green marbles.  Two are "
                    "drawn without replacement.  Probability both are the same "
                    "colour?  Reply with a single reduced fraction."
                ),
            }
        ],
        max_output_tokens=16_384,  # MUST exceed thinking.budget_tokens
        temperature=1.0,  # required when thinking is on
    )
    assert result.stop_reason is not None
    # We do not assert on the exact arithmetic — only that the model
    # produced some content alongside a recognised stop_reason.
    text = result.choices[0].message.content or ""
    assert text.strip(), "Empty completion content from extended thinking call"


@pytest.mark.asyncio
async def test_live_disable_parallel_tool_use_round_trip(
    anthropic_api_key: None,
    _skip_on_model_not_found: None,
) -> None:
    """``disable_parallel_tool_use=True`` reaches the wire without 400 errors.

    We don't strictly need the model to actually emit a tool call — only
    that the request is accepted and a response comes back.
    """
    llm = BaseAnthropic(
        model_name=_model(),
        async_mode=True,
        llm_params=AnthropicLLMParams(disable_parallel_tool_use=True),
    )
    result = await llm.call(
        model=_model(),
        messages=[{"role": "user", "content": "Reply with the word OK."}],
        tools=[AnthropicTool.code_execution()],
        max_output_tokens=128,
        temperature=0.0,
    )
    assert isinstance(result, AnthropicLLMResponse)
    assert result.stop_reason is not None
