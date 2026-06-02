# Text-to-SQL Agent Evaluation Showcase

Evaluate a **production-shaped autonomous text-to-SQL agent** on the Chinook database — five evaluation patterns, three grader types, pass@k trials, production-style safety checks, and an owned scorecard. Built with **NucleusIQ Autonomous mode** (planning + Critic/Refiner + ContextEngine).

**Blog:** [`docs/blog/evaluating-text-to-sql-agents-with-nucleusiq.md`](../../../docs/blog/evaluating-text-to-sql-agents-with-nucleusiq.md)  
**LinkedIn drafts (A–D):** [`docs/marketing/linkedin-text-to-sql-showcase.md`](../../../docs/marketing/linkedin-text-to-sql-showcase.md)  
**Showcase image (blog / LinkedIn):** [`assets/showcase-scorecard.png`](assets/showcase-scorecard.png) — regenerate with `python scripts/render_showcase_image.py`  
**Build guide:** [`docs/use-cases/text-to-sql-evaluation-showcase.md`](../../../docs/use-cases/text-to-sql-evaluation-showcase.md)  
**Architecture:** [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Quick start

```bash
cd notebooks/agents/text_to_sql_eval
pip install -r requirements.txt
# ANTHROPIC_API_KEY in repo root .env

python scripts/download_chinook.py
python scripts/build_fat_db.py
python run_all.py
```

## What this covers (section map)

| Section | Implemented in |
|---------|----------------|
| Terminology (task, trial, grader, transcript, outcome) | Blog + `evals/runner.py` |
| Why evals are harder (non-determinism, propagation) | `eval_trials.py` pass@k / pass^k |
| Trajectory / response / state | `evals/extract.py`, `AgentResult` |
| Code + LLM + human graders | `evals/graders.py`, `production_evaluators.py` |
| Capability vs regression | trials tagged `regression` |
| Pattern 1–5 | `evals/runner.py` |
| Architecture | `ARCHITECTURE.md` |
| Production evaluators (offline) | `evals/production_evaluators.py` |
| Scorecard | `results/scorecard.json`, `results/report.md` |
| Context stress | `eval_context_stress()` fat DB + all-table schema question |

## Agent mode

**Default: `ExecutionMode.AUTONOMOUS`** — not Standard. Matches multi-step planning + verification agents.

Memory: **`FullHistoryMemory`** for Pattern 4 multi-turn.

## Pytest

```bash
pytest evals/test_patterns.py -v
```

Requires `ANTHROPIC_API_KEY`.
