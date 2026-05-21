"""Repo paths for investment board devil's advocate showcase."""

from __future__ import annotations

from pathlib import Path

# notebooks/agents/investment_board_devils_advocate/committee/paths.py
PKG_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PKG_ROOT.parent
NOTEBOOKS_AGENTS = AGENTS_DIR
REPO_ROOT = AGENTS_DIR.parent.parent

RESEARCH_DIR = REPO_ROOT / "research"
DATA_DIR = PKG_ROOT / "data"
RAW_DIR = DATA_DIR / "00_raw"
INTERMEDIATE_DIR = DATA_DIR / "01_intermediate"
OUTPUT_DIR = DATA_DIR / "02_output"

TCS_2025_PDF = RESEARCH_DIR / "tcs_annual_report-2025.pdf"
HCL_2025_PDF = RESEARCH_DIR / "hcl_2025_Financial_report.pdf"

PACK_OUTPUT = OUTPUT_DIR / "investment_committee_pack.json"
OBJECTIONS_OUTPUT = OUTPUT_DIR / "objection_register.json"
PREBRIEF_OUTPUT = OUTPUT_DIR / "chair_prebrief.md"

DISCLAIMER = (
    "Educational demonstration only. Not investment, legal, or tax advice. "
    "Figures are taken from cited annual report excerpts; verify independently before any decision."
)

# Verified PDF page indices (0-based) for FY2025 consolidated statements
PDF_PAGES = {
    "tcs": {"pl": 181, "bs": 180},
    "hcl": {"pl": 383, "bs": 381},
}


def ensure_data_dirs() -> None:
    for d in (RAW_DIR, INTERMEDIATE_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
