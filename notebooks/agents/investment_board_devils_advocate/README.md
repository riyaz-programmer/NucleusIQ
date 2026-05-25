# Investment board — devil's advocate (NucleusIQ showcase)

**Entry point:** [`notebooks/devils_advocate_showcase.ipynb`](notebooks/devils_advocate_showcase.ipynb) — run all cells in order (Phases A–D).

Demonstrates **why** teams use NucleusIQ on a realistic committee workflow: frozen board pack, T−1 pre-brief, multi-turn chair chat with memory and tools — not a one-off Gemini script.

## Why we built it

The **chair** allocates **$500K–$1M** across **TCS vs HCL** using FY2025 PDFs, **credit memo** ($600K, cautious), **RM memo** ($900K, disagrees), five **analyst memos**, and a **commentary thread**. NucleusIQ provides `@tool` grounding, **STANDARD** preload, **DIRECT** chat, **MemoryFactory**, plugins, and **CostTracker**.

| Phase | What | NucleusIQ |
|-------|------|-----------|
| **A** | Build `data/02_output/investment_committee_pack.json` | Custom `committee/` pipeline |
| **B** | Review pack | — |
| **C** | T−1 pre-brief | `Agent` + `STANDARD` + `@tool` + plugins |
| **D** | Live devil's advocate chat | `Agent` + `DIRECT` + memory |

## Run

**Prerequisites:** `research/tcs_annual_report-2025.pdf`, `research/hcl_2025_Financial_report.pdf`, `GEMINI_API_KEY` in repo `.env` (phases C & D).

```bash
pip install nucleusiq nucleusiq-gemini pypdf python-dotenv pandas jsonschema
jupyter notebook notebooks/devils_advocate_showcase.ipynb
```

**Stakeholder demo (Phase D):** ask about RM $900K vs credit $600K, then a follow-up on partial approval (proves memory).

## Layout

> **Note:** Python code lives in `committee/` (not `lib/`) because the repo root `.gitignore` ignores all `lib/` folders.

| Path | Role |
|------|------|
| `notebooks/devils_advocate_showcase.ipynb` | Guided walkthrough |
| `notebooks/nucleusiq-devils-advocate-newsletter-cover.png` | Newsletter / LinkedIn cover |
| `notebooks/NEWSLETTER.md` | LinkedIn copy (title + opening) |
| `committee/showcase_agent.py` | Agent factory (preload + chat) |
| `committee/pack_tools.py` | `@tool` pack readers |
| `committee/pack_builder.py` | Phase A pack builder |
| `schema/investment_committee_pack.schema.json` | Pack shape reference |

## Reference

- [PACK_CONTENTS.md](PACK_CONTENTS.md) — pack blocks and `section_id`s
- [SOURCES.md](SOURCES.md) — PDF paths
- [Use-case spec](../../docs/use-cases/investment-board-devils-advocate-agent.md)
