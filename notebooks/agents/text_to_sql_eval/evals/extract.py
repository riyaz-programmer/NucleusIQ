from __future__ import annotations

from typing import Any

from nucleusiq.agents.agent_result import AgentResult


def final_answer(result: AgentResult) -> str:
    return str(result.output or "")


def tool_names(result: AgentResult) -> list[str]:
    return [tc.tool_name for tc in result.tool_calls]


def tool_names_in_round(result: AgentResult, round_no: int) -> list[str]:
    return [tc.tool_name for tc in result.tool_calls if tc.round == round_no]


def executed_sql(result: AgentResult) -> list[str]:
    out: list[str] = []
    for tc in result.tool_calls:
        if tc.tool_name == "sql_query" and isinstance(tc.args, dict):
            q = tc.args.get("query", "")
            if q:
                out.append(str(q))
    return out


def telemetry_dict(result: AgentResult) -> Any:
    tel = result.context_telemetry
    if tel is None:
        return None
    if hasattr(tel, "model_dump"):
        return tel.model_dump(exclude_none=True)
    if hasattr(tel, "__dict__"):
        return {k: v for k, v in tel.__dict__.items() if not k.startswith("_")}
    return str(tel)
