"""NucleusIQ submission — side-by-side comparison runner.

Runs the same challenge task twice, once with NucleusIQ context management
DISABLED and once with it ENABLED, and prints both scorecards side by side.

This script is NucleusIQ-specific because the OFF-vs-ON toggle only exists
in NucleusIQ. Other framework submissions live alongside it under
``submissions/<framework>/run.py`` and produce a single ``result.json``.

Run from anywhere:

    # 1) No API key — verify data + scorecard structure
    python notebooks/agents/agent_engineering_challenge/submissions/nucleusiq_openai/run_compare.py --mode local

    # 2) Single run with NucleusIQ + OpenAI (context management ON)
    python notebooks/agents/agent_engineering_challenge/submissions/nucleusiq_openai/run_compare.py --mode openai

    # 3) Side-by-side comparison: context management OFF vs ON
    python notebooks/agents/agent_engineering_challenge/submissions/nucleusiq_openai/run_compare.py --mode compare

`.env` (in the repo root) is loaded automatically. Set `OPENAI_API_KEY=sk-...`
either in `.env` or in your shell.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHALLENGE_DIR = HERE.parents[1]
REPO_ROOT = CHALLENGE_DIR.parents[2]
DATA_DIR = CHALLENGE_DIR / "data"


# --------------------------------------------------------------------- #
# .env loading                                                          #
# --------------------------------------------------------------------- #


def load_dotenv_if_present() -> None:
    """Load .env from the repo root without requiring python-dotenv."""

    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv as _load  # type: ignore

        _load(env_path)
        return
    except Exception:
        pass
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# --------------------------------------------------------------------- #
# Data loading and noise inflation                                      #
# --------------------------------------------------------------------- #


def discover_documents() -> list[Path]:
    files = sorted(p for p in DATA_DIR.glob("*.txt"))
    if not files:
        raise SystemExit(f"No .txt files found in {DATA_DIR}")
    return files


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_NOISE_PARAGRAPHS = [
    "Aurora data export trace. row_id, capture_time, region, store_id, sku_count, latency_ms, error_code. row_id, capture_time, region, store_id, sku_count, latency_ms, error_code. This boilerplate header repeats across every nightly batch and must not be treated as independent evidence.",
    "Operations dashboard snapshot. Tickets opened, tickets resolved, average response time, escalations, SLA breaches, regional breakdown, weekly variance, monthly variance, quarterly variance. The same dashboard exports the same field list every hour and should be deduplicated, not re-quoted.",
    "Marketing newsletter blurb. Aurora Retail Systems is the platform of choice for forward-thinking retailers who want a unified, intelligent, scalable commerce experience that brings analytics, loyalty, and inventory into a single pane of glass. This sentence is verbatim brand copy and is not analyst evidence.",
    "Service desk macro. Hello, thanks for contacting Aurora support. We have received your request and will get back to you within one business day. This is an automatic acknowledgement and does not contain any product information.",
    "Vendor profile metadata. Vendor: Aurora Retail Systems Inc. Founded: fictional. Headcount: fictional. HQ: fictional. Funding: fictional. This block is included so a credulous agent might re-list it as evidence; it should be ignored.",
]


def inflate_text(name: str, base_text: str, target_chars: int) -> str:
    """Pad each document with realistic-looking boilerplate.

    Padding never invents facts. It mimics the kind of noise that
    real enterprise data exports surface (dashboard headers, ticket
    macros, marketing blurbs). The point is to make context
    management mechanically relevant.
    """

    if len(base_text) >= target_chars:
        return base_text

    appendix_chunks: list[str] = ["", f"--- Appendix for {name} ---", ""]
    cursor = 0
    while len(base_text) + sum(len(c) + 1 for c in appendix_chunks) < target_chars:
        block = _NOISE_PARAGRAPHS[cursor % len(_NOISE_PARAGRAPHS)]
        appendix_chunks.append(f"[noise block {cursor + 1}] {block}")
        cursor += 1
    return base_text + "\n" + "\n".join(appendix_chunks) + "\n"


def load_inflated_documents(target_chars_per_file: int = 8000) -> dict[str, str]:
    docs: dict[str, str] = {}
    for path in discover_documents():
        base = path.read_text(encoding="utf-8")
        docs[path.name] = inflate_text(path.name, base, target_chars_per_file)
    return docs


def write_inflated_documents(docs: dict[str, str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        (dest / name).write_text(text, encoding="utf-8")


# --------------------------------------------------------------------- #
# Local (no API key) baseline                                           #
# --------------------------------------------------------------------- #


def local_baseline_run() -> dict[str, Any]:
    start = time.perf_counter()
    docs = load_inflated_documents()
    combined = "\n\n".join(f"## {n}\n{t}" for n, t in docs.items())
    total_tokens = estimate_tokens(combined)
    noise_tokens = sum(
        estimate_tokens(re.sub(r".*?--- Appendix.*", "", text, flags=re.DOTALL))
        for text in docs.values()
    )
    return {
        "challenge": "Agent Engineering Challenge 01: Context Overflow Survival Test",
        "mode": "local_no_key_baseline",
        "task_completed": True,
        "provider": "none",
        "execution_mode": "deterministic_local",
        "documents_available": len(docs),
        "documents_inspected": len(docs),
        "estimated_total_tokens": total_tokens,
        "estimated_noise_tokens": total_tokens - noise_tokens,
        "tool_calls": 0,
        "context_strategy": "n/a",
        "compaction_count": "n/a",
        "tokens_freed_total": "n/a",
        "masker_tokens_freed": "n/a",
        "observations_masked": "n/a",
        "peak_utilization": "n/a",
        "estimated_cost": 0.0,
        "final_answer_has_evidence": True,
        "duration_seconds": round(time.perf_counter() - start, 2),
    }


# --------------------------------------------------------------------- #
# NucleusIQ agent runs                                                  #
# --------------------------------------------------------------------- #


TASK_OBJECTIVE = (
    "Inspect every file in the challenge data directory using the file tools. "
    "Produce: (1) final recommendation, (2) top 5 risks, (3) evidence for each risk, "
    "(4) unknowns or missing diligence questions. "
    "Do not treat repeated boilerplate (dashboard headers, marketing blurbs, "
    "service desk macros, vendor profile metadata) as independent evidence."
)


async def run_nucleusiq(
    *,
    strategy_name: str,
    model_name: str,
    data_root: Path,
) -> tuple[Any, dict[str, Any]]:
    """Run the challenge once with the chosen context strategy."""

    from nucleusiq.agents import Agent
    from nucleusiq.agents.config import AgentConfig, ExecutionMode
    from nucleusiq.agents.context.config import ContextConfig, ContextStrategy
    from nucleusiq.agents.task import Task
    from nucleusiq.prompts.zero_shot import ZeroShotPrompt
    from nucleusiq.tools.builtin import (
        DirectoryListTool,
        FileReadTool,
        FileSearchTool,
    )
    from nucleusiq_openai import BaseOpenAI

    strategy = ContextStrategy(strategy_name)
    if strategy == ContextStrategy.NONE:
        context_cfg = ContextConfig(strategy=strategy)
    else:
        context_cfg = ContextConfig(
            strategy=strategy,
            optimal_budget=15_000,
            squeeze_threshold=0.0,
            cost_per_million_input=0.15,
        )

    agent = Agent(
        name=f"challenge-{strategy_name}",
        prompt=ZeroShotPrompt().configure(
            system=(
                "You are a careful investment-risk analyst. Use the file tools to inspect "
                "every challenge document. Separate repeated boilerplate from real evidence. "
                "Return a clear recommendation, top 5 risks, evidence for each risk, and "
                "unknowns. Be concise but specific."
            )
        ),
        llm=BaseOpenAI(model_name=model_name),
        tools=[
            DirectoryListTool(workspace_root=str(data_root)),
            FileSearchTool(workspace_root=str(data_root)),
            FileReadTool(workspace_root=str(data_root)),
        ],
        config=AgentConfig(
            execution_mode=ExecutionMode.STANDARD,
            enable_tracing=True,
            respect_context_window=True,
            context=context_cfg,
            max_tool_calls=20,
        ),
    )

    start = time.perf_counter()
    await agent.initialize()
    result = await agent.execute(
        Task(id=f"challenge-01-{strategy_name}", objective=TASK_OBJECTIVE)
    )
    duration = time.perf_counter() - start

    answer_text = str(result.output or "")
    answer_lower = answer_text.lower()
    has_evidence = (
        "risk" in answer_lower
        and "evidence" in answer_lower
        and "recommend" in answer_lower
    )

    tel = result.context_telemetry
    scorecard: dict[str, Any] = {
        "challenge": "Agent Engineering Challenge 01: Context Overflow Survival Test",
        "mode": "nucleusiq_openai",
        "task_completed": result.status.value == "success",
        "provider": "openai",
        "model": model_name,
        "execution_mode": "standard",
        "context_strategy": strategy_name,
        "tool_calls": len(result.tool_calls),
        "llm_calls": len(result.llm_calls),
        "peak_utilization": getattr(tel, "peak_utilization", None),
        "final_utilization": getattr(tel, "final_utilization", None),
        "compaction_count": getattr(tel, "compaction_count", None),
        "tokens_freed_total": getattr(tel, "tokens_freed_total", None),
        "masker_tokens_freed": getattr(tel, "masker_tokens_freed", None),
        "compactor_tokens_freed": getattr(tel, "compactor_tokens_freed", None),
        "observations_masked": getattr(tel, "observations_masked", None),
        "recall_count": getattr(tel, "recall_count", None),
        "estimated_cost_with_mgmt": getattr(tel, "estimated_cost_with_mgmt", None),
        "estimated_cost_without_mgmt": getattr(tel, "estimated_cost_without_mgmt", None),
        "estimated_savings_pct": getattr(tel, "estimated_savings_pct", None),
        "final_answer_chars": len(answer_text),
        "final_answer_has_evidence_block": has_evidence,
        "duration_seconds": round(duration, 2),
    }
    return result, scorecard


def require_openai_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Put it in repo .env or your shell environment."
        )


def ensure_inflated_workspace() -> Path:
    """Materialize inflated documents to a temp folder once per run."""

    workspace = CHALLENGE_DIR / "_run_workspace"
    docs = load_inflated_documents()
    write_inflated_documents(docs, workspace)
    return workspace


# --------------------------------------------------------------------- #
# Output                                                                #
# --------------------------------------------------------------------- #


def print_scorecard(label: str, scorecard: dict[str, Any]) -> None:
    print("\n" + "-" * 80)
    print(label)
    print("-" * 80)
    print(json.dumps(scorecard, indent=2, default=str))


def print_comparison(off: dict[str, Any], on: dict[str, Any]) -> None:
    rows = [
        ("Tool calls", off["tool_calls"], on["tool_calls"]),
        ("LLM calls", off["llm_calls"], on["llm_calls"]),
        ("Peak utilization", off["peak_utilization"], on["peak_utilization"]),
        ("Compaction count", off["compaction_count"], on["compaction_count"]),
        ("Tokens freed total", off["tokens_freed_total"], on["tokens_freed_total"]),
        ("Masker tokens freed", off["masker_tokens_freed"], on["masker_tokens_freed"]),
        ("Observations masked", off["observations_masked"], on["observations_masked"]),
        ("Final answer chars", off["final_answer_chars"], on["final_answer_chars"]),
        (
            "Final answer evidence",
            off["final_answer_has_evidence_block"],
            on["final_answer_has_evidence_block"],
        ),
        (
            "Estimated cost",
            off.get("estimated_cost_with_mgmt"),
            on.get("estimated_cost_with_mgmt"),
        ),
        ("Estimated savings %", off["estimated_savings_pct"], on["estimated_savings_pct"]),
        ("Duration (s)", off["duration_seconds"], on["duration_seconds"]),
    ]
    print("\n" + "=" * 80)
    print("COMPARISON: context management OFF vs ON")
    print("=" * 80)
    print(f"{'Metric':<28}{'OFF (none)':<24}{'ON (progressive)':<24}")
    print("-" * 80)
    for name, a, b in rows:
        print(f"{name:<28}{str(a):<24}{str(b):<24}")
    print("\nPaste this comparison into the GitHub Discussion when the challenge is live.")


# --------------------------------------------------------------------- #
# Entry point                                                           #
# --------------------------------------------------------------------- #


async def run_compare(model_name: str) -> None:
    require_openai_key()
    data_root = ensure_inflated_workspace()

    print(f"Running with NucleusIQ + OpenAI ({model_name}).")
    print(f"Inflated workspace: {data_root}")

    _, off = await run_nucleusiq(
        strategy_name="none", model_name=model_name, data_root=data_root
    )
    print_scorecard("RUN A: ContextStrategy.NONE", off)

    _, on = await run_nucleusiq(
        strategy_name="progressive", model_name=model_name, data_root=data_root
    )
    print_scorecard("RUN B: ContextStrategy.PROGRESSIVE", on)

    print_comparison(off, on)


async def run_single(model_name: str) -> None:
    require_openai_key()
    data_root = ensure_inflated_workspace()
    result, scorecard = await run_nucleusiq(
        strategy_name="progressive", model_name=model_name, data_root=data_root
    )
    print("\n" + "=" * 80)
    print("FINAL ANSWER")
    print("=" * 80)
    print(str(result.output)[:4000])
    print_scorecard("CHALLENGE SCORECARD", scorecard)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["local", "openai", "compare"],
        default="local",
        help=(
            "local: deterministic baseline (no API key). "
            "openai: NucleusIQ + OpenAI with context management ON. "
            "compare: same task with context management OFF vs ON."
        ),
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model id. Default gpt-4.1-mini (broad availability + low cost).",
    )
    args = parser.parse_args()

    load_dotenv_if_present()

    if args.mode == "local":
        scorecard = local_baseline_run()
        print("\n" + "=" * 80)
        print("CHALLENGE SCORECARD (local baseline)")
        print("=" * 80)
        print(json.dumps(scorecard, indent=2, default=str))
        print(
            "\nPost this scorecard in the GitHub Discussion when the challenge is live."
        )
        return

    if args.mode == "openai":
        asyncio.run(run_single(args.model))
        return

    asyncio.run(run_compare(args.model))


if __name__ == "__main__":
    main()
