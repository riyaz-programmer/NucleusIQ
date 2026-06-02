# Text-to-SQL Autonomous Agent — Architecture

**Published blog:** [nucleusbox.com/evaluating-text-to-sql-agents-with-nucleusiq](https://www.nucleusbox.com/evaluating-text-to-sql-agents-with-nucleusiq/)  
**Showcase image (scorecard):** [`assets/showcase-scorecard.png`](assets/showcase-scorecard.png) — run `python scripts/render_showcase_image.py` after `run_all.py`.

```
User question
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  NucleusIQ Agent (ExecutionMode.AUTONOMOUS)             │
│  ┌─────────────┐  ┌──────────┐  ┌────────┐  ┌────────┐ │
│  │ Decomposer  │→ │ Tool loop│→ │ Critic │→ │Refiner │ │
│  └─────────────┘  └──────────┘  └────────┘  └────────┘ │
│         │              │                                │
│         │         ContextEngine (mask / recall)         │
│         │              │                                │
│         ▼              ▼                                │
│  FullHistoryMemory (multi-turn)                         │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  SQL tools (@tool, read-only SQLite)                    │
│  sql_list_tables │ sql_schema │ sql_query_checker │     │
│  sql_query                                              │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  AgentResult (transcript + outcome + telemetry)         │
│  tool_calls │ output │ autonomous │ context_telemetry   │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Evaluation harness (pytest + run_all.py)               │
│  5 patterns │ pass@k │ production evaluators │ scorecard│
└─────────────────────────────────────────────────────────┘
```

## Data

- **Chinook SQLite** — sample digital media store (`Customer`, `Employee`, `Invoice`, …).
- **Known facts:** 8 customers in Canada; Jane Peacock top revenue employee.

## Modes

| Mode | Role in showcase |
|------|------------------|
| **Autonomous** | Default — planning, verification, multi-step SQL (production-style agent) |
| Standard | Optional comparison (tool loop only) |

## Memory

- **FullHistoryMemory** — Pattern 4 multi-turn: turn 2 sees turn 1 without hand-built message lists.
