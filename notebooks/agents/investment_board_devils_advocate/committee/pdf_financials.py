"""Extract consolidated financial highlights from FY2025 annual report PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .paths import HCL_2025_PDF, PDF_PAGES, REPO_ROOT, TCS_2025_PDF

_CRORE = "INR crore"


def _page_text(pdf: Path, page_index: int) -> str:
    reader = PdfReader(str(pdf))
    return reader.pages[page_index].extract_text() or ""


def _parse_tcs_pl(text: str) -> dict[str, Any]:
    """Parse TCS consolidated P&L (page ~181). Amounts in ₹ crore."""
    rev = re.search(
        r"Revenue from operations\s+12\s+([\d,]+)\s+([\d,]+)",
        text,
    )
    pbt = re.search(
        r"PROFIT BEFORE EXCEPTIONAL ITEM AND TAX\s+([\d,]+)\s+([\d,]+)",
        text,
    )
    pat = re.search(r"PROFIT FOR THE YEAR\s+([\d,]+)\s+([\d,]+)", text)
    eps = re.search(
        r"Earnings per equity share.*?Basic and diluted.*?\d+\s+([\d.]+)\s+([\d.]+)",
        text,
        re.DOTALL,
    )

    def _n(s: str) -> float:
        return float(s.replace(",", ""))

    fy25, fy24 = "FY2025", "FY2024"
    return {
        "currency": _CRORE,
        "periods": [fy24, fy25],
        "income_statement": [
            {
                "line": "Revenue from operations",
                "section_id": "tcs.financials.pl.revenue",
                "values": {fy24: _n(rev.group(2)), fy25: _n(rev.group(1))},
                "source_note": "Consolidated Statement of Profit and Loss",
            },
            {
                "line": "Profit before tax (pre-exceptional)",
                "section_id": "tcs.financials.pl.pbt",
                "values": {fy24: _n(pbt.group(2)), fy25: _n(pbt.group(1))},
            },
            {
                "line": "Profit for the year",
                "section_id": "tcs.financials.pl.pat",
                "values": {fy24: _n(pat.group(2)), fy25: _n(pat.group(1))},
            },
            {
                "line": "Basic EPS (₹)",
                "section_id": "tcs.financials.pl.eps",
                "values": {fy24: _n(eps.group(2)), fy25: _n(eps.group(1))},
                "unit": "INR per share",
            },
        ],
    }


def _parse_tcs_bs(text: str) -> dict[str, Any]:
    total_assets = re.search(
        r"TOTAL ASSETS\s+([\d,]+)\s+([\d,]+)",
        text,
    )
    total_equity = re.search(
        r"Total equity\s+([\d,]+)\s+([\d,]+)",
        text,
    )
    cash = re.search(
        r"Cash and cash equivalents\s+8\(c\)\s+([\d,]+)\s+([\d,]+)",
        text,
    )

    def _n(s: str) -> float:
        return float(s.replace(",", ""))

    fy25, fy24 = "FY2025", "FY2024"
    return {
        "balance_sheet": [
            {
                "line": "Total assets",
                "section_id": "tcs.financials.bs.total_assets",
                "values": {fy24: _n(total_assets.group(2)), fy25: _n(total_assets.group(1))},
            },
            {
                "line": "Total equity",
                "section_id": "tcs.financials.bs.total_equity",
                "values": {fy24: _n(total_equity.group(2)), fy25: _n(total_equity.group(1))},
            },
            {
                "line": "Cash and cash equivalents",
                "section_id": "tcs.financials.bs.cash",
                "values": {fy24: _n(cash.group(2)), fy25: _n(cash.group(1))},
            },
        ],
    }


def _parse_hcl_pl(text: str) -> dict[str, Any]:
    """Parse HCL consolidated P&L (page ~383). Normalize ligature artifacts."""
    clean = (
        text.replace("/r_t.liga", "rt")
        .replace("/uni20B9", "₹")
        .replace("T otal", "Total")
        .replace("Y ear", "Year")
        .replace("amo/r_t.ligaization", "amortization")
    )
    rev = re.search(
        r"Revenue from operations\s+3\.19\s+([\d,\s]+)\s+([\d,\s]+)",
        clean,
    )
    pbt = re.search(r"III Profit before tax\s+([\d,\s]+)\s+([\d,\s]+)", clean)
    pat = re.search(r"V Profit for the year\s+([\d,\s]+)\s+([\d,\s]+)", clean)

    def _n(s: str) -> float:
        return float(re.sub(r"\s+", "", s).replace(",", ""))

    fy25, fy24 = "FY2025", "FY2024"
    return {
        "currency": _CRORE,
        "periods": [fy24, fy25],
        "income_statement": [
            {
                "line": "Revenue from operations",
                "section_id": "hcl.financials.pl.revenue",
                "values": {fy24: _n(rev.group(2)), fy25: _n(rev.group(1))},
            },
            {
                "line": "Profit before tax",
                "section_id": "hcl.financials.pl.pbt",
                "values": {fy24: _n(pbt.group(2)), fy25: _n(pbt.group(1))},
            },
            {
                "line": "Profit for the year",
                "section_id": "hcl.financials.pl.pat",
                "values": {fy24: _n(pat.group(2)), fy25: _n(pat.group(1))},
            },
        ],
    }


def _parse_hcl_bs(text: str) -> dict[str, Any]:
    clean = text.replace("/r_t.liga", "rt").replace("/uni20B9", "₹").replace("T otal", "Total")

    def _n(s: str) -> float:
        return float(re.sub(r"\s+", "", s).replace(",", ""))

    assets = re.search(r"TOTAL ASSETS\s+([\d,\s]+)\s+([\d,\s]+)", clean)
    equity = re.search(r"TOTAL EQUITY\s+([\d,\s]+)\s+([\d,\s]+)", clean)
    cash = re.search(
        r"Cash and cash equivalents\s+3\.10\(a\)\s+([\d,\s]+)\s+([\d,\s]+)",
        clean,
    )

    fy25, fy24 = "FY2025", "FY2024"
    return {
        "balance_sheet": [
            {
                "line": "Total assets",
                "section_id": "hcl.financials.bs.total_assets",
                "values": {fy24: _n(assets.group(2)), fy25: _n(assets.group(1))},
            },
            {
                "line": "Total equity",
                "section_id": "hcl.financials.bs.total_equity",
                "values": {fy24: _n(equity.group(2)), fy25: _n(equity.group(1))},
            },
            {
                "line": "Cash and cash equivalents",
                "section_id": "hcl.financials.bs.cash",
                "values": {fy24: _n(cash.group(2)), fy25: _n(cash.group(1))},
            },
        ],
    }


def extract_issuer(issuer_id: str) -> dict[str, Any]:
    if issuer_id == "tcs":
        pdf = TCS_2025_PDF
        pages = PDF_PAGES["tcs"]
        company_name = "Tata Consultancy Services Limited"
        ticker = "TCS (NSE/BSE)"
        report_date = "2025-04-10"
    elif issuer_id == "hcl":
        pdf = HCL_2025_PDF
        pages = PDF_PAGES["hcl"]
        company_name = "HCL Technologies Limited"
        ticker = "HCLTECH (NSE/BSE)"
        report_date = "2025-08-02"
    else:
        raise ValueError(f"Unknown issuer: {issuer_id}")

    if not pdf.is_file():
        raise FileNotFoundError(f"Missing annual report: {pdf}")

    pl_text = _page_text(pdf, pages["pl"])
    bs_text = _page_text(pdf, pages["bs"])

    financials: dict[str, Any] = {
        "extraction_method": "pypdf_verified_pages",
        "pdf_pages": {"pl": pages["pl"] + 1, "bs": pages["bs"] + 1},
    }
    if issuer_id == "tcs":
        financials.update(_parse_tcs_pl(pl_text))
        financials.update(_parse_tcs_bs(bs_text))
    else:
        financials.update(_parse_hcl_pl(pl_text))
        financials.update(_parse_hcl_bs(bs_text))

    return {
        "issuer_id": issuer_id,
        "company_name": company_name,
        "ticker": ticker,
        "company_profile": {
            "sector": "IT Services",
            "listing": "India",
            "report_fiscal_year": "FY2025",
            "report_letter_date": report_date,
        },
        "source_pdf": str(pdf.relative_to(REPO_ROOT)).replace("\\", "/"),
        "financials": financials,
    }
