"""Phase B: Anthropic prompt caching (cache_system + cache_tools).

Run from ``src/providers/llms/anthropic``::

    uv run python examples/agents/11_anthropic_prompt_caching.py

Requires ``ANTHROPIC_API_KEY``.

What this demo shows
--------------------
``AnthropicLLMParams.cache_system=True`` and ``cache_tools=True`` enable
Anthropic's prompt-caching feature: a ``cache_control`` block is appended
to the system prompt and (if any) the last tool definition, telling
Anthropic to keep that prefix in cache for ~5 minutes.

We run the SAME agent twice with a long, identical system prompt.  The
second call should have ``cache_read_input_tokens > 0`` and
``cache_creation_input_tokens == 0`` — proving Anthropic served the
system prompt out of cache instead of re-billing every prompt token.

Look at the ``LLMCallRecord`` rows in ``AgentResult.llm_calls`` for the
exact cache token split.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from util_env import load_repo_dotenv  # noqa: E402

load_repo_dotenv()

from nucleusiq.agents import Agent  # noqa: E402
from nucleusiq.agents.config import AgentConfig, ExecutionMode  # noqa: E402
from nucleusiq.agents.task import Task  # noqa: E402
from nucleusiq.llms.llm_params import LLMParams  # noqa: E402
from nucleusiq.prompts.zero_shot import ZeroShotPrompt  # noqa: E402
from nucleusiq_anthropic import AnthropicLLMParams, BaseAnthropic  # noqa: E402

# Anthropic requires at least ~1024 prompt tokens before caching kicks in.
# 30 copies of the paragraph below is comfortably above that floor.
_PARAGRAPH = (
    "You are a meticulous senior systems engineer with two decades of "
    "experience reviewing distributed systems for retail, finance, and "
    "infrastructure customers.  When asked to evaluate a design, walk "
    "through correctness, fault tolerance, capacity, security, and "
    "operability one heading at a time before giving an overall verdict.\n"
)
_LONG_SYSTEM = "".join([_PARAGRAPH] * 30)


def _model() -> str:
    return os.getenv("ANTHROPIC_PHASE_B_MODEL", "claude-sonnet-4-5-20250929")


async def _ask(agent: Agent, q: str, label: str) -> None:
    result = await agent.execute(Task(id=f"caching-{label}", objective=q))
    print(f"--- {label} ---")
    print(result.output[:280].rstrip(), "...\n" if len(result.output) > 280 else "\n")
    for rec in result.llm_calls:
        print(
            f"  round={rec.round} purpose={rec.purpose:<8} "
            f"prompt={rec.prompt_tokens:>5} "
            f"cache_read={rec.cache_read_input_tokens:>5} "
            f"cache_create={rec.cache_creation_input_tokens:>5} "
            f"stop_reason={rec.stop_reason}"
        )
    print()


async def main() -> None:
    llm = BaseAnthropic(
        model_name=_model(),
        async_mode=True,
        llm_params=AnthropicLLMParams(
            # Both knobs go through build_create_kwargs and become
            # cache_control: ephemeral blocks on the wire.
            cache_system=True,
            cache_tools=False,  # no tools in this demo, but flip on if you add some
        ),
    )

    agent = Agent(
        name="anthropic-prompt-caching",
        prompt=ZeroShotPrompt().configure(system=_LONG_SYSTEM),
        llm=llm,
        config=AgentConfig(
            execution_mode=ExecutionMode.DIRECT,
            enable_tracing=True,
            llm_params=LLMParams(temperature=0.0, max_output_tokens=256),
        ),
    )

    await agent.initialize()

    print("=== PHASE B: prompt caching (cache_system=True) ===")
    print(f"Model:        {_model()}")
    print(f"System chars: {len(_LONG_SYSTEM):,} (~{len(_LONG_SYSTEM) // 4:,} tokens)\n")

    await _ask(
        agent,
        "In one sentence, what is the most common cause of cascading failure?",
        "call-1 (cache create)",
    )
    await _ask(
        agent,
        "In one sentence, define the term 'graceful degradation'.",
        "call-2 (cache hit)",
    )


if __name__ == "__main__":
    asyncio.run(main())
