"""Five analyst memos for the investment committee pack."""

from __future__ import annotations

from typing import Any


def build_analyst_memos(
    issuers: list[dict[str, Any]], comparison: dict[str, Any]
) -> list[dict[str, Any]]:
    tcs = next(i for i in issuers if i["issuer_id"] == "tcs")
    hcl = next(i for i in issuers if i["issuer_id"] == "hcl")
    tk, hk = tcs["key_metrics"], hcl["key_metrics"]

    return [
        {
            "analyst_id": "A",
            "display_name": "Analyst A — TCS quality",
            "stance": "buy",
            "conviction": "high",
            "target_position_usd": 750_000,
            "allocation_preference": {"tcs": 0.75, "hcl": 0.25},
            "section_id": "analyst_memos.A",
            "thesis": (
                f"Deploy ~$750K with TCS overweight: FY2025 revenue ₹{tk['revenue_inr_crore_fy2025']:,.0f} cr "
                f"({tk['revenue_yoy_pct']}% YoY) and net margin {tk['net_margin_pct_fy2025']}%. "
                "Scale, cash generation, and EPS visibility support a core holding."
            ),
            "key_risks": [
                "USD revenue mix — FX and client IT budget cycles",
                "Talent cost inflation vs pricing on large deals",
            ],
        },
        {
            "analyst_id": "B",
            "display_name": "Analyst B — HCL growth",
            "stance": "buy",
            "conviction": "medium",
            "target_position_usd": 650_000,
            "allocation_preference": {"tcs": 0.35, "hcl": 0.65},
            "section_id": "analyst_memos.B",
            "thesis": (
                f"Favor HCL for relative growth: revenue ₹{hk['revenue_inr_crore_fy2025']:,.0f} cr "
                f"({hk['revenue_yoy_pct']}% YoY) vs TCS {tk['revenue_yoy_pct']}%. "
                f"PAT growth {hk['profit_yoy_pct']}% signals operating leverage."
            ),
            "key_risks": [
                "Goodwill/intangibles weight on balance sheet",
                "Integration execution on services mix shift",
            ],
        },
        {
            "analyst_id": "C",
            "display_name": "Analyst C — Balanced barbell",
            "stance": "hold",
            "conviction": "medium",
            "target_position_usd": 500_000,
            "allocation_preference": {"tcs": 0.5, "hcl": 0.5},
            "section_id": "analyst_memos.C",
            "thesis": (
                f"Split $500K–$1M band 50/50: {comparison['narrative']} "
                "Diversifies single-name India IT risk while staying in liquid large caps."
            ),
            "key_risks": [
                "Correlation remains high in sector drawdowns",
                "Opportunity cost if only one name rerates",
            ],
        },
        {
            "analyst_id": "D",
            "display_name": "Analyst D — Valuation skeptic",
            "stance": "sell",
            "conviction": "medium",
            "target_position_usd": 0,
            "allocation_preference": {"tcs": 0.0, "hcl": 0.0},
            "section_id": "analyst_memos.D",
            "thesis": (
                "Pass at current multiples: both names trade as crowded quality IT. "
                f"TCS margin {tk['net_margin_pct_fy2025']}% vs HCL {hk['net_margin_pct_fy2025']}% "
                "does not justify full $1M deployment without a pullback or clearer catalyst."
            ),
            "key_risks": [
                "Missing live market P/E in pack — valuation debate incomplete",
                "FY2025 reports backward-looking; forward guide not in excerpt",
            ],
        },
        {
            "analyst_id": "E",
            "display_name": "Analyst E — Macro underweight",
            "stance": "sell",
            "conviction": "low",
            "target_position_usd": 250_000,
            "allocation_preference": {"tcs": 0.2, "hcl": 0.1},
            "section_id": "analyst_memos.E",
            "thesis": (
                "Cap IT at ~$250K: global discretionary spend uncertainty warrants underweight. "
                "Prefer cash until macro visibility improves."
            ),
            "key_risks": [
                "Underweight risks missing continued India IT earnings momentum",
                "Sector momentum can override macro for 6–12 months",
            ],
        },
    ]
