"""Submission template for Agent Engineering Challenge 01.

How to use:
  1. Copy this folder to ../<your_handle>_<framework>/.
  2. Implement build_and_run() with your framework of choice.
  3. Run:
         python <your_handle>_<framework>/run.py
  4. The script writes result.json next to itself.

The task statement lives in ../../TASK.md.
The scorecard contract lives in ../../SCORECARD_SPEC.md.
The dataset lives in ../../data/.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHALLENGE_DIR = HERE.parents[1]
DATA_DIR = CHALLENGE_DIR / "data"
TASK_FILE = CHALLENGE_DIR / "TASK.md"
SPEC_FILE = CHALLENGE_DIR / "SCORECARD_SPEC.md"


# --------------------------------------------------------------------- #
# 1. Implement this with your framework.                                #
# --------------------------------------------------------------------- #


def build_and_run() -> dict[str, Any]:
    """Run your framework on the challenge and return raw run data.

    Required return keys (used by produce_scorecard below):
        final_answer:     str
        tool_calls:       int
        llm_calls:        int
        duration_seconds: float

    Optional but encouraged (report null if not exposed):
        estimated_input_tokens, estimated_output_tokens,
        estimated_cost_usd, peak_context_utilization,
        compaction_events, tokens_freed_total
    """

    raise NotImplementedError(
        "Replace this stub with your framework's run. "
        "Read every .txt file under DATA_DIR, solve the task in TASK_FILE, "
        "and return the dict described in the docstring."
    )


# --------------------------------------------------------------------- #
# 2. Do not edit below unless you have a good reason.                   #
# --------------------------------------------------------------------- #


def produce_scorecard(run_data: dict[str, Any]) -> dict[str, Any]:
    final_answer = (run_data.get("final_answer") or "").strip()
    lower = final_answer.lower()

    files_in_data = sorted(p.name for p in DATA_DIR.glob("*.txt"))
    cited = sum(1 for name in files_in_data if name.lower() in lower)

    boilerplate_markers = (
        "platform of choice for forward-thinking retailers",
        "automatic acknowledgement",
        "row_id, capture_time, region",
    )
    quoted_boilerplate = any(m in lower for m in boilerplate_markers)

    return {
        "framework": run_data.get("framework", "unknown"),
        "framework_version": run_data.get("framework_version", "unknown"),
        "model": run_data.get("model", "unknown"),
        "provider": run_data.get("provider", "unknown"),
        "task_completed": all(
            section in lower
            for section in ("recommend", "risk", "evidence", "unknown")
        ),
        "duration_seconds": run_data.get("duration_seconds"),
        "tool_calls": run_data.get("tool_calls"),
        "llm_calls": run_data.get("llm_calls"),
        "estimated_input_tokens": run_data.get("estimated_input_tokens"),
        "estimated_output_tokens": run_data.get("estimated_output_tokens"),
        "estimated_cost_usd": run_data.get("estimated_cost_usd"),
        "peak_context_utilization": run_data.get("peak_context_utilization"),
        "compaction_events": run_data.get("compaction_events"),
        "tokens_freed_total": run_data.get("tokens_freed_total"),
        "final_answer_has_recommendation": "recommend" in lower,
        "final_answer_has_top5_risks": "risk" in lower,
        "final_answer_has_evidence_per_risk": "evidence" in lower,
        "final_answer_has_unknowns": "unknown" in lower,
        "files_cited_in_evidence": cited,
        "boilerplate_quoted_as_evidence": quoted_boilerplate,
        "final_answer": final_answer[:4000],
        "notes": run_data.get("notes", ""),
    }


def main() -> None:
    start = time.perf_counter()
    run_data = build_and_run()
    run_data.setdefault("duration_seconds", round(time.perf_counter() - start, 2))

    scorecard = produce_scorecard(run_data)
    out = HERE / "result.json"
    out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps(scorecard, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
