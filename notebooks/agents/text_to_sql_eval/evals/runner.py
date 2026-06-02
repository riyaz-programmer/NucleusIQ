from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

from nucleusiq.agents.agent_result import AgentResult
from nucleusiq.agents.config import ExecutionMode
from nucleusiq.agents.context.config import ContextStrategy
from nucleusiq.agents.task import Task
from nucleusiq.memory.factory import MemoryFactory, MemoryStrategy

from agent.build_agent import build_sql_agent
from evals import graders as g
from evals.extract import final_answer, telemetry_dict, tool_names, tool_names_in_round
from evals.production_evaluators import run_production_evaluators

DEFAULT_MODE = ExecutionMode.AUTONOMOUS


@dataclass
class PatternResult:
    pattern_id: str
    name: str
    passed: bool
    detail: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    feedback: dict[str, float] = field(default_factory=dict)
    tool_calls: int = 0
    duration_ms: float = 0.0
    trajectory: list[str] = field(default_factory=list)
    autonomous: dict[str, Any] | None = None


async def run_question(
    llm: Any,
    question: str,
    *,
    mode: ExecutionMode = DEFAULT_MODE,
    context: ContextStrategy = ContextStrategy.PROGRESSIVE,
    memory: Any = None,
    task_id: str = "q",
) -> AgentResult:
    agent = build_sql_agent(
        llm, mode=mode, context=context, memory=memory, optimal_budget=30_000
    )
    await agent.initialize()
    return await agent.execute(Task(id=task_id, objective=question))


def _autonomous_summary(result: AgentResult) -> dict[str, Any] | None:
    auto = result.autonomous
    if auto is None:
        return None
    return {
        "attempts": auto.attempts,
        "sub_tasks": list(auto.sub_tasks),
        "complexity": auto.complexity,
        "critic_verdicts": len(auto.critic_verdicts),
        "refined": auto.refined,
    }


def _row(
    pattern_id: str,
    name: str,
    result: AgentResult,
    passed: bool,
    detail: str = "",
    scores: dict[str, float] | None = None,
    feedback: dict[str, float] | None = None,
) -> PatternResult:
    return PatternResult(
        pattern_id=pattern_id,
        name=name,
        passed=passed,
        detail=detail,
        scores=scores or {},
        feedback=feedback or g.feedback_scores(result, scores),
        tool_calls=result.tool_call_count,
        duration_ms=result.duration_ms,
        trajectory=[tc.tool_name for tc in result.tool_calls],
        autonomous=_autonomous_summary(result),
    )


async def eval_pattern_1a(llm: Any) -> PatternResult:
    r = await run_question(llm, "How many customers are from Canada?")
    ok = g.answer_contains(r, "8")
    fb = g.feedback_scores(r, {"correct_answer": 1.0 if ok else 0.0})
    return _row("p1a", "Custom per-datapoint: Canada (code)", r, ok, "expected '8'", feedback=fb)


async def eval_pattern_1b(llm: Any) -> PatternResult:
    q = "Which employee generated the most revenue and from which countries?"
    r = await run_question(llm, q)
    scores = await g.llm_judge(llm, q, final_answer(r), "Jane Peacock")
    ok = scores["correctness"] >= 0.5
    return _row(
        "p1b",
        "Custom per-datapoint: revenue (LLM judge)",
        r,
        ok,
        f"correctness={scores['correctness']:.2f}",
        scores=scores,
    )


async def eval_pattern_2(llm: Any) -> PatternResult:
    r = await run_question(llm, "How many customers are from Canada?")
    names = tool_names(r)
    ok = bool(g.SQL_TOOLS & set(names))
    fb = g.feedback_scores(r, {"used_sql_tools": 1.0 if ok else 0.0})
    return _row("p2", "Single-step: uses SQL tools", r, ok, f"tools={names}", feedback=fb)


async def eval_pattern_3(llm: Any) -> PatternResult:
    r = await run_question(llm, "How many customers are from Canada?")
    ok = g.executed_a_query(r) and g.answer_contains(r, "8")
    fb = g.feedback_scores(r, {"executed_query": 1.0 if g.executed_a_query(r) else 0.0, "correct_answer": 1.0 if ok else 0.0})
    return _row("p3", "Full turn (order-free)", r, ok, feedback=fb)


async def eval_pattern_4(llm: Any) -> PatternResult:
    memory = MemoryFactory.create_memory(MemoryStrategy.FULL_HISTORY)
    agent = build_sql_agent(llm, memory=memory, mode=DEFAULT_MODE)
    await agent.initialize()
    r1 = await agent.execute(
        Task(id="t1", objective="What are the top 5 best-selling artists?")
    )
    a1 = final_answer(r1)
    if not a1 or len(a1) < 20:
        return _row("p4", "Multi-turn follow-up", r1, False, "turn 1 empty — skip turn 2")
    r2 = await agent.execute(
        Task(id="t2", objective="For the top artist, how many albums do they have?")
    )
    ok = len(final_answer(r2)) > 20
    fb = g.feedback_scores(r2, {"turn1_success": 1.0, "turn2_success": 1.0 if ok else 0.0})
    return _row("p4", "Multi-turn follow-up", r2, ok, f"turn1_len={len(a1)}", feedback=fb)


async def eval_pattern_5(llm: Any) -> PatternResult:
    q = "What is the total revenue per genre, and which genre has the most tracks?"
    r = await run_question(llm, q)
    safe = g.no_dml_executed(r)
    substantive = len(final_answer(r)) > 50
    planned = g.has_autonomous_planning(r)
    ok = safe and substantive and planned
    fb = g.feedback_scores(r, {"sql_safety": 1.0 if safe else 0.0, "substantive_answer": 1.0 if substantive else 0.0, "planning": 1.0 if planned else 0.0})
    return _row(
        "p5",
        "Safety + state (Autonomous planning)",
        r,
        ok,
        f"safe={safe} substantive={substantive} planning={planned}",
        feedback=fb,
    )


async def eval_production_style(llm: Any) -> dict[str, Any]:
    """Offline run of production-style evaluators on a sample trace."""
    q = "How many customers are from Canada?"
    r = await run_question(llm, q, task_id="prod-eval")
    scores = await run_production_evaluators(llm, q, r)
    return {"question": q, "scores": scores, "passed": scores.get("overall_quality", 0) >= 0.7}


async def eval_trials(
    llm: Any,
    question: str,
    check: Callable[[AgentResult], bool],
    k: int = 3,
) -> dict[str, Any]:
    results = [await run_question(llm, question, task_id=f"trial-{i}") for i in range(k)]
    passes = [check(r) for r in results]
    return {
        "question": question,
        "k": k,
        "passes": passes,
        "pass_count": sum(passes),
        "pass@k": any(passes),
        "pass^k": all(passes),
        "pass_rate": sum(passes) / k if k else 0.0,
        "eval_type": "regression",
    }


async def eval_context_stress(llm: Any) -> dict[str, Any]:
    """Context OFF vs ON on fat DB with a schema-heavy question."""
    from agent import sql_tools
    from agent.db import FAT_DB_PATH

    if not FAT_DB_PATH.is_file():
        return {"skipped": True, "reason": "run scripts/build_fat_db.py"}

    question = (
        "Return the CREATE statement for every table in the database, "
        "then tell me how many customers are from Canada."
    )
    sql_tools.set_active_db(FAT_DB_PATH)

    async def _one(strategy: ContextStrategy) -> dict[str, Any]:
        r = await run_question(
            llm, question, context=strategy, task_id=f"stress-{strategy.value}"
        )
        return {
            "strategy": strategy.value,
            "status": str(r.status),
            "passed": g.answer_contains(r, "8"),
            "answer_preview": final_answer(r)[:200],
            "tool_calls": r.tool_call_count,
            "telemetry": telemetry_dict(r),
        }

    try:
        off = await _one(ContextStrategy.NONE)
        on = await _one(ContextStrategy.PROGRESSIVE)
        return {"skipped": False, "question": question, "off": off, "on": on}
    finally:
        sql_tools.set_active_db(None)
