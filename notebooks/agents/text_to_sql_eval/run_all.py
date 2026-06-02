#!/usr/bin/env python
"""Run full text-to-SQL evaluation showcase and write scorecard."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from agent.env import load_env  # noqa: E402
from agent.build_agent import make_llm  # noqa: E402
from evals import graders as g  # noqa: E402
from evals.runner import (  # noqa: E402
    DEFAULT_MODE,
    eval_context_stress,
    eval_pattern_1a,
    eval_pattern_1b,
    eval_pattern_2,
    eval_pattern_3,
    eval_pattern_4,
    eval_pattern_5,
    eval_production_style,
    eval_trials,
)
from evals.scorecard import build_scorecard, write_artifacts  # noqa: E402


async def main() -> int:
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (check repo .env)")
        return 1

    db = PKG_ROOT / "data" / "chinook.sqlite"
    if not db.is_file():
        from scripts.download_chinook import download

        download()

    fat = PKG_ROOT / "data" / "chinook_fat.sqlite"
    if not fat.is_file():
        import subprocess

        subprocess.run([sys.executable, "scripts/build_fat_db.py"], check=True, cwd=PKG_ROOT)

    llm = make_llm()
    model = llm.model_name
    mode = DEFAULT_MODE.value
    print(f"Model: {model}  Mode: {mode}\n")

    patterns = []
    for fn, label in [
        (eval_pattern_1a, "P1a custom/code"),
        (eval_pattern_1b, "P1b custom/LLM judge"),
        (eval_pattern_2, "P2 single-step"),
        (eval_pattern_3, "P3 full turn"),
        (eval_pattern_4, "P4 multi-turn"),
        (eval_pattern_5, "P5 safety+state"),
    ]:
        print(f"Running {label}...")
        row = await fn(llm)
        patterns.append(row)
        mark = "PASS" if row.passed else "FAIL"
        print(f"  {mark} — {row.detail} ({row.tool_calls} tools, {row.duration_ms:.0f}ms)\n")

    print("Running pass@k trials (k=3, regression suite)...")
    trials = await eval_trials(
        llm,
        "How many customers are from Canada?",
        lambda r: g.answer_contains(r, "8"),
        k=3,
    )
    print(f"  pass@k={trials['pass@k']} pass^k={trials['pass^k']} rate={trials['pass_rate']:.0%}\n")

    print("Running production-style evaluators (offline)...")
    prod = await eval_production_style(llm)
    print(f"  overall_quality={prod['scores'].get('overall_quality', 0):.2f}\n")

    print("Running context stress (fat schema, heavy question)...")
    context_demo = await eval_context_stress(llm)
    if context_demo.get("skipped"):
        print(f"  Skipped: {context_demo.get('reason')}\n")
    else:
        print(f"  OFF pass={context_demo['off']['passed']} tools={context_demo['off']['tool_calls']}")
        print(f"  ON  pass={context_demo['on']['passed']} tools={context_demo['on']['tool_calls']}\n")

    card = build_scorecard(model, mode, patterns, trials, prod, context_demo)
    json_path, md_path = write_artifacts(card)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    return 0 if card["patterns_passed"] == card["patterns_total"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
