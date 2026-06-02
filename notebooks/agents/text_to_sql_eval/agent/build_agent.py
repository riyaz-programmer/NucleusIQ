from __future__ import annotations

from typing import Any

from nucleusiq.agents import Agent
from nucleusiq.agents.config import AgentConfig, ExecutionMode
from nucleusiq.agents.context.config import ContextConfig, ContextStrategy
from nucleusiq.memory.base import BaseMemory
from nucleusiq.prompts.zero_shot import ZeroShotPrompt

from .sql_tools import make_sql_tools

SYSTEM = (
    "You are a careful text-to-SQL analyst for a SQLite media-store database.\n"
    "You work in Autonomous mode: decompose complex questions, verify your work, "
    "and only answer after you have evidence from the database.\n"
    "ALWAYS explore before you answer:\n"
    "  1. Call sql_list_tables to see what exists.\n"
    "  2. Call sql_schema on the relevant tables to learn columns.\n"
    "  3. (Optional) Call sql_query_checker to validate your SQL.\n"
    "  4. Call sql_query to run a read-only SELECT.\n"
    "Never write to the database. Answer with the number/fact you found."
)


def build_sql_agent(
    llm: Any,
    *,
    mode: ExecutionMode = ExecutionMode.AUTONOMOUS,
    context: ContextStrategy = ContextStrategy.PROGRESSIVE,
    optimal_budget: int = 30_000,
    memory: BaseMemory | None = None,
) -> Agent:
    """Text-to-SQL agent. Default: Autonomous (planning + Critic/Refiner)."""
    return Agent(
        name="text2sql",
        prompt=ZeroShotPrompt().configure(system=SYSTEM),
        llm=llm,
        tools=make_sql_tools(),
        memory=memory,
        config=AgentConfig(
            execution_mode=mode,
            enable_tracing=True,
            context=ContextConfig(strategy=context, optimal_budget=optimal_budget),
        ),
    )


def make_llm(model_name: str = "claude-haiku-4-5-20251001") -> Any:
    from nucleusiq_anthropic import BaseAnthropic

    return BaseAnthropic(
        model_name=model_name,
        temperature=0.0,
        async_mode=True,
    )
