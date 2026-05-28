# Agent Engineering Challenge 01: Context Overflow Survival Test

> Can an agent finish a tool-heavy research task when tool outputs are large, noisy, repetitive, and unsafe to keep fully in the active prompt?

**Post your `result.json` here →** `https://github.com/nucleusbox/NucleusIQ/discussions/<NUMBER>` *(replace `<NUMBER>` after creating the Discussion)*

---

## What This Challenge Actually Is

It is **not** a benchmark, not a leaderboard, and not "NucleusIQ vs others."

It is a tiny public contract with three locked parts:

| Part | File | Status |
|------|------|--------|
| The task | [`TASK.md`](TASK.md) | Locked. Do not edit. |
| The dataset | [`data/`](data/) | Locked. Do not edit. |
| The scorecard schema | [`SCORECARD_SPEC.md`](SCORECARD_SPEC.md) | Locked. Do not edit. |

Anyone can implement the task with any framework and produce a `result.json` that matches the schema. The maintainer's reference submission lives under [`submissions/nucleusiq_openai/`](submissions/nucleusiq_openai/).

The "challenge" is the **contract**. The code is just one submission.

---

## Folder Map

```
agent_engineering_challenge/
├── README.md                     ← this file (the only README)
├── TASK.md                       ← the task (locked)
├── SCORECARD_SPEC.md             ← required output schema (locked)
├── data/                         ← dataset, locked
│   └── *.txt                     (5 files; see Dataset section below)
└── submissions/
    ├── _template/run.py          ← copy this to start a submission
    └── nucleusiq_openai/         ← maintainer's reference submission
        ├── run.py                ← produces result.json
        ├── run_compare.py        ← NucleusIQ-only OFF-vs-ON demo
        └── result.json           ← latest reference scorecard
```

The top level holds only the **contract** + this README. All runnable code lives under `submissions/`.

---

## Three Ways To Engage

### 1. See how it works (NucleusIQ side-by-side demo)

Runs the same task twice — once with context management OFF, once with it ON — and prints a comparison table.

```bash
python notebooks/agents/agent_engineering_challenge/submissions/nucleusiq_openai/run_compare.py --mode compare
```

### 2. Reproduce the reference submission

Runs the NucleusIQ reference and writes `result.json` next to the script.

```bash
python notebooks/agents/agent_engineering_challenge/submissions/nucleusiq_openai/run.py
```

### 3. Submit your own (see "How To Submit" below)

The runner auto-loads `.env` from the repo root. An `OPENAI_API_KEY=...` line is enough; no shell exports needed. Default model is `gpt-4.1-mini`.

---

## Dataset

All inputs live in `data/`. Each file is small, hand-authored, and intentionally noisy.

| File | Contents |
|------|----------|
| `company_overview.txt` | Business model, migration story, signal-vs-noise on growth. |
| `financial_notes.txt` | Revenue, margins, retention, conflicting CEO-vs-finance claims. |
| `risk_register.txt` | Five risks with evidence and mitigations. |
| `customer_feedback.txt` | Positive and negative customer signals, support themes. |
| `legal_contract_notes.txt` | Contract risk, compliance, single-tenant constraints. |

Each file deliberately contains:

- Real, scoreable facts the agent must surface.
- Repeated boilerplate that mimics enterprise data exports (dashboard headers, marketing blurbs, vendor metadata).
- Conflicting signals (CEO says X, finance says Y).

The runner also pads each file at run time with extra realistic noise so total context grows large enough to exercise context management. This padding is generated in code and never written to disk.

---

## How To Submit

There are **two paths** by design. Default to Path A. Path B is invite-only.

### Path A — Post your result.json in the Discussion (default)

This is how 99% of submissions should land. No PR, no permissions, low friction.

1. Run your framework on the task in `TASK.md`, against the data in `data/`.
2. Produce a `result.json` matching `SCORECARD_SPEC.md`. The `submissions/_template/run.py` shows the minimum scaffolding — you can copy it locally without forking.
3. Open the pinned Discussion linked at the top of this file.
4. Reply with your `result.json` wrapped in a fenced JSON code block plus 2–3 lines about your stack, model, and any failure mode you hit.

That's it. Discussions support markdown, threading, and reactions; they are the right home for numbers + narrative.

### Path B — Open a Pull Request (invite-only)

To keep the `submissions/` folder curated and to avoid PR spam, **the maintainer must invite a PR** based on what they saw in your Discussion post. If your Discussion entry is a good fit for permanent inclusion (clean code, clear notes, a stack we don't yet have committed), you will be asked to open a PR that adds:

- `submissions/<your_handle>_<framework>/run.py`
- `submissions/<your_handle>_<framework>/result.json`
- A short `notes` field in your `result.json` explaining anything unusual.

If you open a PR without an invite, it may be closed with a request to post in the Discussion first. This is not gatekeeping; it is to keep the signal-to-noise ratio of the folder useful for everyone who reads it.

### Rules (both paths)

- Do not modify `TASK.md`, `SCORECARD_SPEC.md`, or `data/`.
- Run from the same dataset and task statement.
- Report honest `null` for fields your framework does not expose — that itself is the most useful information the challenge produces.
- The agent should not refuse the task, hallucinate file names, or quote marketing boilerplate as evidence.

---

## Reference Run (NucleusIQ + `gpt-4.1-mini`)

| Metric | OFF (`ContextStrategy.NONE`) | ON (`ContextStrategy.PROGRESSIVE`) |
|---|---|---|
| Tool calls | 8 | 7 |
| LLM calls | 6 | 4 |
| Peak context utilization | n/a (engine off) | 1.00 |
| Compaction events | n/a | 2 |
| Tokens freed total | n/a | 7,557 |
| Estimated cost | n/a | $0.00142 |
| **Estimated savings** | — | **44.4 %** |
| **Wall-clock duration** | **233.3 s** | **21.9 s** |
| Final answer cites ≥4 of 5 files | yes | yes |
| Quoted boilerplate as evidence | no | no |

The latest reference scorecard (single run) is committed at [`submissions/nucleusiq_openai/result.json`](submissions/nucleusiq_openai/result.json).

The OFF-vs-ON toggle is **NucleusIQ-specific** (only NucleusIQ has the strategy switch). Other frameworks submit a single `result.json` per stack.

---

## What I'm Watching For

- Which frameworks survive a tight context budget on a small model.
- Which frameworks expose tool calls, LLM calls, and context utilization in a readable way.
- Which frameworks silently quote boilerplate as evidence.
- What metric is missing from the scorecard.
