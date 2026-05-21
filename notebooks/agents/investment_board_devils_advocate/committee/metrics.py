"""Compute comparison metrics from extracted issuer financials."""

from __future__ import annotations

from typing import Any


def _line(issuer: dict[str, Any], section_suffix: str) -> dict[str, float] | None:
    fin = issuer["financials"]
    for block in ("income_statement", "balance_sheet"):
        for row in fin.get(block, []):
            if row["section_id"].endswith(section_suffix):
                return row["values"]
    return None


def _yoy(values: dict[str, float]) -> float | None:
    if not values or len(values) < 2:
        return None
    keys = sorted(values.keys())
    old, new = values[keys[-2]], values[keys[-1]]
    if old == 0:
        return None
    return round(100.0 * (new - old) / old, 2)


def build_key_metrics(issuer: dict[str, Any]) -> dict[str, Any]:
    rev = _line(issuer, ".revenue")
    pat = _line(issuer, ".pat")
    assets = _line(issuer, ".total_assets")
    cash = _line(issuer, ".cash")

    rev_yoy = _yoy(rev) if rev else None
    pat_yoy = _yoy(pat) if pat else None
    fy = "FY2025"
    rev_fy = rev.get(fy) if rev else None
    pat_fy = pat.get(fy) if pat else None
    net_margin = round(100.0 * pat_fy / rev_fy, 2) if rev_fy and pat_fy else None
    cash_pct_assets = (
        round(100.0 * cash.get(fy, 0) / assets.get(fy, 1), 2)
        if cash and assets and assets.get(fy)
        else None
    )

    return {
        "revenue_inr_crore_fy2025": rev_fy,
        "revenue_yoy_pct": rev_yoy,
        "profit_after_tax_inr_crore_fy2025": pat_fy,
        "profit_yoy_pct": pat_yoy,
        "net_margin_pct_fy2025": net_margin,
        "cash_to_assets_pct_fy2025": cash_pct_assets,
        "formulas": {
            "revenue_yoy_pct": "(rev_fy25 - rev_fy24) / rev_fy24 * 100",
            "net_margin_pct": "PAT / revenue * 100",
            "cash_to_assets_pct": "cash / total_assets * 100",
        },
    }


def build_comparison(issuers: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for issuer in issuers:
        km = issuer["key_metrics"]
        rows.append(
            {
                "issuer_id": issuer["issuer_id"],
                "company_name": issuer["company_name"],
                "revenue_inr_crore": km["revenue_inr_crore_fy2025"],
                "revenue_yoy_pct": km["revenue_yoy_pct"],
                "net_margin_pct": km["net_margin_pct_fy2025"],
                "pat_inr_crore": km["profit_after_tax_inr_crore_fy2025"],
            }
        )
    tcs = next(i for i in issuers if i["issuer_id"] == "tcs")
    hcl = next(i for i in issuers if i["issuer_id"] == "hcl")
    tcs_rev = tcs["key_metrics"]["revenue_inr_crore_fy2025"]
    hcl_rev = hcl["key_metrics"]["revenue_inr_crore_fy2025"]
    scale_ratio = round(tcs_rev / hcl_rev, 2) if hcl_rev else None

    return {
        "section_id": "comparison.fy2025_summary",
        "narrative": (
            f"TCS revenue (~₹{tcs_rev:,.0f} cr) is ~{scale_ratio}x HCL (~₹{hcl_rev:,.0f} cr) on FY2025 "
            "consolidated statements. Margins and growth differ — see issuer key_metrics."
        ),
        "scale_revenue_tcs_to_hcl": scale_ratio,
        "rows": rows,
    }
