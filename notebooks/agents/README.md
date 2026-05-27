# NucleusIQ Agent Examples

End-to-end notebooks demonstrating how to build autonomous agents with NucleusIQ.

## Examples

| Notebook | Domain | What it shows |
|----------|--------|--------------|
| [PE Due Diligence](pe_due_diligence.ipynb) | Private Equity | 8 multi-step financial analyses — WACC, DCF, LBO IRR, merger math. Compares Standard vs Autonomous modes with external validation. |
| [TCS Research Analyst](research_analyst_tcs.ipynb) | Equity research (India IT) | **Full framework showcase**: Gemini + custom `@tool` (PDF + web), Pydantic structured output, plugins (limits + retry), SlidingWindowMemory, CostTracker, streaming, pandas visualization, feature proof dashboard. |

### Investment board devil's advocate (**active**)

Chair allocates **$500K–$1M** across **TCS vs HCL** using **FY2025 reports only** (`research/hcl_2025_…`, `research/tcs_annual_report-2025.pdf`) + **five analyst memos**. Agent plays devil's advocate.

| Resource | Purpose |
|----------|---------|
| [devils_advocate_showcase.ipynb](investment_board_devils_advocate/notebooks/devils_advocate_showcase.ipynb) | **Start here** — one notebook: data prep + chat |

## How to Run

1. **Install dependencies**:
   ```bash
   pip install nucleusiq nucleusiq-openai
   # For the TCS Gemini showcase notebook:
   pip install nucleusiq nucleusiq-gemini pypdf requests python-dotenv
   ```

2. **Set your API key**:
   ```bash
   export OPENAI_API_KEY=sk-...
   export GEMINI_API_KEY=...   # TCS research notebook
   ```

3. **Open the notebook**:
   ```bash
   jupyter notebook notebooks/agents/pe_due_diligence.ipynb
   jupyter notebook notebooks/agents/research_analyst_tcs.ipynb
   ```

## Adding New Examples

Each example notebook should follow this structure:

1. **Introduction** — What problem are we solving?
2. **Setup** — Imports and environment
3. **Tools** — Define domain-specific tools
4. **Tasks** — Define the scenarios with ground truth
5. **Standard Mode** — Run as baseline
6. **Autonomous Mode** — Run with validation plugins
7. **Results** — Compare and analyze
8. **Key Takeaways** — What we learned

Place new notebooks directly in this folder:

```
notebooks/
  agents/
    pe_due_diligence.ipynb
    research_analyst_tcs.ipynb
    investment_board_devils_advocate/notebooks/devils_advocate_showcase.ipynb
    data/tcs/                          # optional: TCS annual report PDFs
    README.md
```
