# Data sources — investment board devil's advocate

**Locked for v1:** FY2025 annual reports for **HCL Technologies** and **TCS** only.

| Company | File | Pages (approx.) | FY / report date |
|---------|------|-----------------|------------------|
| **HCL** | [`research/hcl_2025_Financial_report.pdf`](../../../research/hcl_2025_Financial_report.pdf) | 470 | Report dated Aug 2, 2025 (BSE 532281) |
| **TCS** | [`research/tcs_annual_report-2025.pdf`](../../../research/tcs_annual_report-2025.pdf) | 337 | Report dated May 27, 2025 (CIN L22210MH1995PLC084781) |

## Out of scope (do not ingest for this showcase)

| Excluded | Reason |
|----------|--------|
| Infosys / Wipro PDFs | User scope: HCL + TCS only |
| 2023 / 2024 reports (all four names) | User scope: **2025 reports only** for HCL and TCS |

Paths for reference only (not used):

- `research/infosys_202{3,4,5}_Financial_report.pdf`
- `research/wipro_202{3,4,5}_Financial_report.pdf`
- `research/hcl_202{3,4}_Financial_report.pdf`
- `research/tcs_annual_report-202{3,4}.pdf`

## Chair decision framing (v1)

Committee must decide how to deploy **$500K–$1M** across Indian IT:

- **TCS only**, **HCL only**, **split**, or **pass** — using **FY2025 reported financials** from the two PDFs above.

Five analyst memos argue positions; the devil's advocate agent challenges the **proposed allocation**, not the PDFs themselves.

## Notebook access

Use absolute or repo-relative paths from project root:

```python
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]  # adjust per notebook depth
HCL_2025 = ROOT / "research" / "hcl_2025_Financial_report.pdf"
TCS_2025 = ROOT / "research" / "tcs_annual_report-2025.pdf"
```

Do not copy 19–26 MB PDFs into `data/00_raw/` unless offline demo requires it; **read from `research/`**.
