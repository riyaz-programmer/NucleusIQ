"""Phase B: native Claude server tools (web_search + code_execution).

Run from ``src/providers/llms/anthropic``::

    uv run python examples/agents/10_anthropic_native_tools.py

Requires ``ANTHROPIC_API_KEY`` (e.g. repo-root ``.env``).  By default uses
``claude-sonnet-4-5-20250929`` (Sonnet 4.5) which supports every Phase B
feature; override with ``ANTHROPIC_PHASE_B_MODEL=<your-model-id>``.

What this demo shows
--------------------
``AnthropicTool.web_search()`` and ``AnthropicTool.code_execution()`` are
**server-executed** tools — Anthropic runs them inside its own
infrastructure and returns the results inline.  Native tools are an
LLM-layer concept, so this demo talks to ``BaseAnthropic`` directly
(rather than wrapping in an :class:`~nucleusiq.agents.Agent`).

The framework surfaces them via
``AnthropicLLMResponse.server_tool_calls`` (and the core agent loop
emits ``ToolCallRecord(executed_by="provider")`` automatically when a
real agent layer is used, see ``base_mode.py``).
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from util_env import load_repo_dotenv  # noqa: E402

load_repo_dotenv()

from nucleusiq_anthropic import AnthropicTool, BaseAnthropic  # noqa: E402


def _model() -> str:
    return os.getenv("ANTHROPIC_PHASE_B_MODEL", "claude-sonnet-4-5-20250929")


async def _run_web_search(llm: BaseAnthropic) -> None:
    print("--- web_search (server-side) ---")
    result = await llm.call(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    "Search the web for one sentence describing what "
                    "NucleusIQ (the open-source AI agent framework) is, "
                    "then quote it."
                ),
            }
        ],
        tools=[AnthropicTool.web_search(max_uses=2)],
        max_output_tokens=512,
    )
    msg = result.choices[0].message
    print("text:", (msg.content or "").strip()[:240])
    print(f"server_tool_calls: {len(result.server_tool_calls)}")
    for stc in result.server_tool_calls:
        print(f"  - {stc.name:<16} id={stc.id}")
    print(f"stop_reason: {result.stop_reason}")
    print(f"usage: prompt={result.usage.prompt_tokens if result.usage else 0} "
          f"completion={result.usage.completion_tokens if result.usage else 0}")
    print()


async def _run_code_execution(llm: BaseAnthropic) -> None:
    print("--- code_execution (server-side) ---")
    result = await llm.call(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    "Use code_execution to compute the 12th Fibonacci number "
                    "and print the result.  Reply with just the integer."
                ),
            }
        ],
        tools=[AnthropicTool.code_execution()],
        max_output_tokens=512,
    )
    msg = result.choices[0].message
    print("text:", (msg.content or "").strip()[:200])
    print(f"server_tool_calls: {len(result.server_tool_calls)}")
    for stc in result.server_tool_calls:
        print(f"  - {stc.name:<16} id={stc.id}")
    print(f"stop_reason: {result.stop_reason}")
    print()


async def main() -> None:
    llm = BaseAnthropic(model_name=_model(), async_mode=True)

    print("=== PHASE B: native server tools (web_search + code_execution) ===")
    print(f"Model: {_model()}\n")

    await _run_web_search(llm)
    await _run_code_execution(llm)


if __name__ == "__main__":
    asyncio.run(main())
