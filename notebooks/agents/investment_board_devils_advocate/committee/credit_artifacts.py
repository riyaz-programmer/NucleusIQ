"""Bank-style credit memo, RM memo, credit analysis, and commentary for the IT equity pack."""

from __future__ import annotations

from typing import Any


def _issuer(issuers: list[dict[str, Any]], issuer_id: str) -> dict[str, Any]:
    return next(i for i in issuers if i["issuer_id"] == issuer_id)


def build_credit_analysis(issuers: list[dict[str, Any]], comparison: dict[str, Any]) -> dict[str, Any]:
    tcs = _issuer(issuers, "tcs")
    hcl = _issuer(issuers, "hcl")
    tk, hk = tcs["key_metrics"], hcl["key_metrics"]

    return {
        "section_id": "credit_analysis.root",
        "prepared_by": "Corporate Credit — IT Services",
        "analysis_date": "2026-05-21",
        "facility_analog": "Discretionary equity sleeve $500K–$1M (board mandate)",
        "recommendation_summary": "APPROVE_WITH_CONDITIONS",
        "internal_risk_grade": "BBB+ / Watchlist-lite (sector multiple risk)",
        "proposed_allocation": {
            "total_usd": 600_000,
            "tcs_pct": 0.6,
            "hcl_pct": 0.4,
            "rationale": "Barbell within band; below $1M cap until valuation refresh",
        },
        "issuer_ratios": [
            {
                "section_id": "credit_analysis.tcs.ratios",
                "issuer_id": "tcs",
                "metrics": {
                    "revenue_inr_crore_fy25": tk["revenue_inr_crore_fy2025"],
                    "revenue_yoy_pct": tk["revenue_yoy_pct"],
                    "pat_inr_crore_fy25": tk["profit_after_tax_inr_crore_fy2025"],
                    "pat_yoy_pct": tk["profit_yoy_pct"],
                    "net_margin_pct": tk["net_margin_pct_fy2025"],
                    "cash_to_assets_pct": tk["cash_to_assets_pct_fy2025"],
                    "equity_inr_crore_fy25": tcs["financials"]["balance_sheet"][1]["values"]["FY2025"],
                },
                "credit_view": "Strong cash generation; margin superior to peer set in pack.",
            },
            {
                "section_id": "credit_analysis.hcl.ratios",
                "issuer_id": "hcl",
                "metrics": {
                    "revenue_inr_crore_fy25": hk["revenue_inr_crore_fy2025"],
                    "revenue_yoy_pct": hk["revenue_yoy_pct"],
                    "pat_inr_crore_fy25": hk["profit_after_tax_inr_crore_fy2025"],
                    "pat_yoy_pct": hk["profit_yoy_pct"],
                    "net_margin_pct": hk["net_margin_pct_fy2025"],
                    "cash_to_assets_pct": hk["cash_to_assets_pct_fy2025"],
                    "equity_inr_crore_fy25": hcl["financials"]["balance_sheet"][1]["values"]["FY2025"],
                },
                "credit_view": "Faster PAT growth but lower margin; balance sheet detail on intangibles not in excerpt.",
            },
        ],
        "comparative_notes": {
            "section_id": "credit_analysis.comparative",
            "text": comparison["narrative"],
            "scale_revenue_tcs_to_hcl": comparison["scale_revenue_tcs_to_hcl"],
        },
        "covenant_analogs": [
            {
                "section_id": "credit_analysis.conditions.max_single_name",
                "condition": "No single issuer >65% of deployed sleeve without board exception",
                "status": "proposed",
            },
            {
                "section_id": "credit_analysis.conditions.valuation_refresh",
                "condition": "Chair to receive live P/E and 90-day relative performance before final $1M draw",
                "status": "open",
            },
            {
                "section_id": "credit_analysis.conditions.stop_loss_review",
                "condition": "Quarterly review if either name underperforms Nifty IT by >15% over 6 months",
                "status": "proposed",
            },
        ],
        "policy_exceptions": [
            {
                "section_id": "credit_analysis.exceptions.concentration",
                "description": "Two-name India IT concentration vs broader global tech mandate",
                "mitigation": "Cap at $600K initial vs $1M max; split 60/40",
                "status": "approved_with_conditions",
            }
        ],
        "risk_rollup": {
            "section_id": "credit_analysis.risk_rollup",
            "color": "AMBER",
            "score_obtained": 580,
            "score_max": 1000,
            "score_pct": 58.0,
            "drivers": [
                "Valuation not evidenced in pack (MISSING_INFO for live multiples)",
                "HCL cash declined YoY per FY25 extract",
                "Sector correlation — dual IT names do not diversify macro shock",
            ],
        },
    }


def build_credit_memo(issuers: list[dict[str, Any]], credit_analysis: dict[str, Any]) -> dict[str, Any]:
    tcs = _issuer(issuers, "tcs")
    hcl = _issuer(issuers, "hcl")
    alloc = credit_analysis["proposed_allocation"]

    sections = [
        {
            "section_id": "credit_memo.executive_summary",
            "title": "Executive summary",
            "text": (
                f"Credit recommends **approve with conditions** a **${alloc['total_usd']:,}** deployment "
                f"({alloc['tcs_pct']:.0%} TCS / {alloc['hcl_pct']:.0%} HCL), not the full $1M band. "
                f"FY25 consolidated data shows TCS revenue ₹{tcs['key_metrics']['revenue_inr_crore_fy2025']:,.0f} cr "
                f"(margin {tcs['key_metrics']['net_margin_pct_fy2025']}%) vs HCL "
                f"₹{hcl['key_metrics']['revenue_inr_crore_fy2025']:,.0f} cr (margin {hcl['key_metrics']['net_margin_pct_fy2025']}%). "
                "Quality is acceptable; **timing and sizing** are the debate."
            ),
        },
        {
            "section_id": "credit_memo.financial_analysis",
            "title": "Financial analysis",
            "text": (
                "TCS exhibits higher net margin and scale; HCL shows stronger PAT YoY (10.75% vs 5.85%). "
                "TCS cash and cash equivalents **fell** FY24→FY25 (₹9,016 cr to ₹8,342 cr per extract) — "
                "monitor liquidity optics despite profitability. HCL cash also down (₹9,456 cr to ₹8,245 cr). "
                "Credit spreads in pack are limited to headline P&L/BS lines; segment and goodwill detail absent."
            ),
        },
        {
            "section_id": "credit_memo.key_risks",
            "title": "Key risks",
            "text": (
                "1) **VALUATION**: No live P/E or EV/EBITDA in pack — board is asked to commit capital without market anchor. "
                "2) **MEMO_MISMATCH risk**: RM is likely to press $750K–$1M and higher HCL tilt. "
                "3) **FIN_TREND**: Mid-single-digit revenue growth — not distressed, but not high-growth compounder at any price. "
                "4) **CONCENTRATION**: India IT pair remains correlated in global slowdown scenarios."
            ),
        },
        {
            "section_id": "credit_memo.covenants_conditions",
            "title": "Conditions precedent",
            "text": (
                "Proceed only if: (a) chair signs off valuation refresh, (b) initial deployment ≤$600K, "
                "(c) single-name cap 65% unless exception documented, (d) 90-day checkpoint on relative performance."
            ),
        },
        {
            "section_id": "credit_memo.recommendation",
            "title": "Recommendation",
            "text": (
                "**Approve with conditions** at $600K split 60/40 (TCS/HCL). "
                "**Do not approve $1M today** without valuation appendix. "
                f"Internal grade: {credit_analysis['internal_risk_grade']}."
            ),
        },
    ]

    return {
        "section_id": "credit_memo.root",
        "author": "Priya N. — VP Credit",
        "date": "2026-05-20",
        "recommendation": credit_analysis["recommendation_summary"],
        "internal_risk_grade": credit_analysis["internal_risk_grade"],
        "proposed_allocation_usd": alloc["total_usd"],
        "sections": sections,
    }


def build_rm_memo(issuers: list[dict[str, Any]], credit_analysis: dict[str, Any]) -> dict[str, Any]:
    tcs = _issuer(issuers, "tcs")
    hcl = _issuer(issuers, "hcl")

    sections = [
        {
            "section_id": "rm_memo.relationship",
            "title": "Relationship & mandate",
            "text": (
                "Client relationship (board sleeve) has been active 8+ years. Mandate renewal favors "
                "**full utilization** of the $500K–$1M band to maintain benchmark tracking vs Nifty IT. "
                "Delaying deployment risks opportunity cost versus peer portfolios already overweight quality IT."
            ),
        },
        {
            "section_id": "rm_memo.commercial_rationale",
            "title": "Commercial rationale",
            "text": (
                f"RM supports **$750K–$1M** total with **55% HCL / 45% TCS** — HCL PAT growth "
                f"{hcl['key_metrics']['profit_yoy_pct']}% vs TCS {tcs['key_metrics']['profit_yoy_pct']}% "
                "demonstrates operating leverage. TCS remains core quality anchor but is priced for perfection "
                "in client conversations; HCL offers rerating optionality."
            ),
        },
        {
            "section_id": "rm_memo.response_to_credit",
            "title": "Response to credit concerns",
            "text": (
                "RM disagrees with credit's $600K cap: FY25 prints are **clean** — double-digit PAT growth at HCL, "
                "stable TCS margin ~19%. Cash movement is seasonal/working-capital per management commentary in reports "
                "(not fully extracted here). Valuation can be supplied same-day from market data — should not block board vote. "
                "Credit's 65% single-name cap is overly conservative for liquid large caps."
            ),
        },
        {
            "section_id": "rm_memo.recommendation",
            "title": "RM recommendation",
            "text": (
                "**Approve $900K** — 55% HCL / 45% TCS. Relationship strategy: **Grow**. "
                "Differs from credit on size (+$300K) and HCL overweight (+15 pts vs credit 60/40 TCS-heavy)."
            ),
        },
    ]

    return {
        "section_id": "rm_memo.root",
        "author": "James K. — Relationship Director",
        "date": "2026-05-20",
        "recommendation": "APPROVE",
        "relationship_strategy": "Grow",
        "proposed_allocation_usd": 900_000,
        "proposed_split": {"tcs": 0.45, "hcl": 0.55},
        "sections": sections,
    }


def build_commentary_thread() -> list[dict[str, Any]]:
    return [
        {
            "author": "credit_analyst",
            "role": "Credit",
            "date": "2026-05-18",
            "section_id": "commentary_thread.001",
            "text": "We should not bring $1M to board without live multiples. Proposing $600K 60/40 TCS/HCL.",
        },
        {
            "author": "rm",
            "role": "RM",
            "date": "2026-05-18",
            "section_id": "commentary_thread.002",
            "text": "Client will view $600K as under-deployment. $900K 45/55 TCS/HCL aligns with mandate and peer benchmarks.",
        },
        {
            "author": "credit_analyst",
            "role": "Credit",
            "date": "2026-05-19",
            "section_id": "commentary_thread.003",
            "text": "HCL cash down YoY in FY25 extract — RM please attach WC bridge or we keep AMBER rollup.",
        },
        {
            "author": "rm",
            "role": "RM",
            "date": "2026-05-19",
            "section_id": "commentary_thread.004",
            "text": "Cash dip is timing. TCS margin gap vs HCL is structural quality — don't underweight TCS below 40%.",
        },
        {
            "author": "credit_analyst",
            "role": "Credit",
            "date": "2026-05-20",
            "section_id": "commentary_thread.005",
            "text": "Board pack must show both views. I remain APPROVE_WITH_CONDITIONS; RM remains full APPROVE at $900K.",
        },
        {
            "author": "rm",
            "role": "RM",
            "date": "2026-05-20",
            "section_id": "commentary_thread.006",
            "text": "Chair: if you want devil's advocate, ask why credit wants to leave $400K uninvested in a 6% revenue growth sector.",
        },
        {
            "author": "board_secretariat",
            "role": "Secretariat",
            "date": "2026-05-21",
            "section_id": "commentary_thread.007",
            "text": "Pack frozen. Credit memo, RM memo, FY25 extracts, five analyst views included. Chair decision required.",
        },
    ]


def build_chair_brief(credit_memo: dict[str, Any], rm_memo: dict[str, Any]) -> str:
    return (
        f"**Credit:** {credit_memo['recommendation']} at ${credit_memo['proposed_allocation_usd']:,}. "
        f"**RM:** {rm_memo['recommendation']} at ${rm_memo['proposed_allocation_usd']:,} "
        f"({rm_memo['proposed_split']['tcs']:.0%} TCS / {rm_memo['proposed_split']['hcl']:.0%} HCL). "
        "Material disagreement on size ($300K) and tilt (TCS-heavy vs HCL-heavy). "
        "Five external analyst memos also split buy/hold/sell. Chair must resolve."
    )
