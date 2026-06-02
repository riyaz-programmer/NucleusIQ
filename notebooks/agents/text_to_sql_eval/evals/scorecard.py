from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.runner import PatternResult
from links import GITHUB_SHOWCASE_URL, PUBLISHED_BLOG_URL

PKG_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PKG_ROOT / "results"


def build_scorecard(
    model: str,
    mode: str,
    patterns: list[PatternResult],
    trials: dict[str, Any],
    production_eval: dict[str, Any],
    context_demo: dict[str, Any],
) -> dict[str, Any]:
    passed = sum(1 for p in patterns if p.passed)
    return {
        "suite": "text2sql_eval",
        "framework": "NucleusIQ",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "mode": mode,
        "patterns_passed": passed,
        "patterns_total": len(patterns),
        "patterns": [asdict(p) for p in patterns],
        "trials": trials,
        "production_evaluators": production_eval,
        "context_stress": context_demo,
        "repro": "cd notebooks/agents/text_to_sql_eval && python run_all.py",
    }


def write_artifacts(card: dict[str, Any]) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / "scorecard.json"
    json_path.write_text(json.dumps(card, indent=2), encoding="utf-8")

    lines = [
        "# Text-to-SQL Eval Scorecard (NucleusIQ)",
        "",
        f"- **Generated:** {card['generated_at']}",
        f"- **Model:** `{card['model']}`",
        f"- **Mode:** `{card['mode']}` (Autonomous = planning + Critic/Refiner)",
        f"- **Patterns:** {card['patterns_passed']}/{card['patterns_total']} passed",
        "",
        "## Pattern results",
        "",
        "| ID | Name | Pass | Tools | ms | Feedback |",
        "|---|---|---|---:|---:|---|",
    ]
    for p in card["patterns"]:
        fb = ", ".join(f"{k}={v}" for k, v in list(p.get("feedback", {}).items())[:3])
        lines.append(
            f"| {p['pattern_id']} | {p['name']} | {'✅' if p['passed'] else '❌'} | "
            f"{p['tool_calls']} | {p['duration_ms']:.0f} | {fb[:50]} |"
        )

    lines += [
        "",
        "## Non-determinism",
        "",
        f"- pass@k={card['trials'].get('pass@k')} pass^k={card['trials'].get('pass^k')} "
        f"rate={card['trials'].get('pass_rate', 0):.0%}",
        "",
        "## Production-style evaluators (offline)",
        "",
    ]
    pe = card.get("production_evaluators", {})
    if pe:
        for k, v in pe.get("scores", {}).items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (not run)")

    lines += ["", "## Context stress (fat schema)", ""]
    ctx = card.get("context_stress", {})
    if ctx.get("skipped"):
        lines.append(f"- Skipped: {ctx.get('reason')}")
    else:
        for label in ("off", "on"):
            row = ctx.get(label, {})
            lines.append(
                f"- **{label.upper()}:** pass={row.get('passed')} tools={row.get('tool_calls')}"
            )

    lines += [
        "",
        f"**Blog:** {card.get('blog', PUBLISHED_BLOG_URL)}",
        "",
        f"Reproduce: `{card['repro']}`",
    ]
    md_path = RESULTS_DIR / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
