"""Phase B: Anthropic extended thinking (``thinking="low"|"medium"|"high"|"max"``).

Run from ``src/providers/llms/anthropic``::

    uv run python examples/agents/12_anthropic_extended_thinking.py

Requires ``ANTHROPIC_API_KEY`` and a model that supports extended thinking
(Claude Sonnet 4.5+ / Opus 4.1+ / 3.7 Sonnet).  Default model is
``claude-sonnet-4-5-20250929``; override with ``ANTHROPIC_PHASE_B_MODEL``.

What this demo shows
--------------------
``AnthropicLLMParams.thinking`` accepts the new ``ThinkingEffort`` literal
(``"low" | "medium" | "high" | "max"``) which the wire layer resolves to
``{"type": "enabled", "budget_tokens": N}`` per ``_THINKING_EFFORT_BUDGETS``.

The resulting response surfaces ``stop_reason`` (``"end_turn"`` /
``"max_tokens"`` / ``"tool_use"``) on the ``LLMCallRecord`` and any
``reasoning_tokens`` in the usage record.
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


def _model() -> str:
    return os.getenv("ANTHROPIC_PHASE_B_MODEL", "claude-sonnet-4-5-20250929")


async def _run(effort: str) -> None:
    llm = BaseAnthropic(
        model_name=_model(),
        async_mode=True,
        llm_params=AnthropicLLMParams(thinking=effort),
    )

    agent = Agent(
        name=f"anthropic-thinking-{effort}",
        prompt=ZeroShotPrompt().configure(
            system="You are a careful problem solver.  Think step by step."
        ),
        llm=llm,
        config=AgentConfig(
            execution_mode=ExecutionMode.DIRECT,
            enable_tracing=True,
            llm_params=LLMParams(
                temperature=1.0,  # Anthropic requires temp=1.0 when thinking is on
                # max_output_tokens MUST be > thinking.budget_tokens
                # (budgets: low=2000, medium=8000, high=32000).
                max_output_tokens=16_384,
            ),
        ),
    )

    await agent.initialize()

    print(f"--- thinking={effort!r} ---")
    result = await agent.execute(
        Task(
            id=f"thinking-{effort}",
            objective=(
                "A bag has 3 red, 5 blue and 7 green marbles.  Two marbles are "
                "drawn without replacement.  Probability both are the same colour? "
                "Reply with a single reduced fraction."
            ),
        )
    )
    answer = (result.output or "").strip().splitlines()
    print("answer:", answer[-1] if answer else "<no output>")
    for rec in result.llm_calls:
        print(
            f"  round={rec.round} stop_reason={rec.stop_reason} "
            f"prompt={rec.prompt_tokens} completion={rec.completion_tokens} "
            f"reasoning={rec.reasoning_tokens}"
        )
    print()


async def main() -> None:
    print("=== PHASE B: extended thinking ===")
    print(f"Model: {_model()}\n")
    for effort in ("low", "medium"):
        await _run(effort)


if __name__ == "__main__":
    asyncio.run(main())
