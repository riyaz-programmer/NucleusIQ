"""Build investment_committee_pack.json from FY2025 HCL + TCS PDFs."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from . import pdf_financials
from .credit_artifacts import (
    build_chair_brief,
    build_commentary_thread,
    build_credit_analysis,
    build_credit_memo,
    build_rm_memo,
)
from .memos import build_analyst_memos
from .metrics import build_comparison, build_key_metrics
from .paths import (
    DISCLAIMER,
    PACK_OUTPUT,
    ensure_data_dirs,
)


def build_pack() -> dict[str, Any]:
    ensure_data_dirs()
    issuers = []
    for issuer_id in ("tcs", "hcl"):
        row = pdf_financials.extract_issuer(issuer_id)
        row["key_metrics"] = build_key_metrics(row)
        issuers.append(row)

    comparison = build_comparison(issuers)
    credit_analysis = build_credit_analysis(issuers, comparison)
    credit_memo = build_credit_memo(issuers, credit_analysis)
    rm_memo = build_rm_memo(issuers, credit_analysis)
    commentary_thread = build_commentary_thread()
    analyst_memos = build_analyst_memos(issuers, comparison)

    pack: dict[str, Any] = {
        "meta": {
            "position_usd_min": 500_000,
            "position_usd_max": 1_000_000,
            "meeting_date": date.today().isoformat(),
            "pack_version": "0.2.0",
            "report_fiscal_year": "FY2025",
            "decision_question": "How to allocate $500K–$1M across TCS vs HCL equity?",
            "pack_type": "investment_committee_with_bank_artifacts",
        },
        "issuers": issuers,
        "comparison": comparison,
        "credit_analysis": credit_analysis,
        "credit_memo": credit_memo,
        "rm_memo": rm_memo,
        "commentary_thread": commentary_thread,
        "analyst_memos": analyst_memos,
        "chair_brief": build_chair_brief(credit_memo, rm_memo),
        "exhibits_index": [
            {"section_id": "exhibits.tcs_pdf", "title": issuers[0]["source_pdf"]},
            {"section_id": "exhibits.hcl_pdf", "title": issuers[1]["source_pdf"]},
        ],
        "preparation_audit": {
            "pipeline": "investment_board_devils_advocate",
            "signed_off": True,
            "sources": [
                "research/hcl_2025_Financial_report.pdf",
                "research/tcs_annual_report-2025.pdf",
            ],
        },
        "disclaimer": DISCLAIMER,
    }
    return pack


def write_pack(path=None) -> dict[str, Any]:
    pack = build_pack()
    out = path or PACK_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2, ensure_ascii=False)
    return pack


if __name__ == "__main__":
    p = write_pack()
    print(f"Wrote {PACK_OUTPUT}")
    print(f"  issuers: {[i['issuer_id'] for i in p['issuers']]}")
    print(f"  analyst_memos: {len(p['analyst_memos'])}")
    print(f"  credit_memo: {p['credit_memo']['recommendation']}")
    print(
        f"  rm_memo: {p['rm_memo']['recommendation']} @ ${p['rm_memo']['proposed_allocation_usd']:,}"
    )
