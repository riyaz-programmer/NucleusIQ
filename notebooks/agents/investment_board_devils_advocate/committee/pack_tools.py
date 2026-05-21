"""Tools for devil's advocate agent over a frozen investment committee pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nucleusiq.tools.decorators import tool

from .paths import PACK_OUTPUT


def load_pack(path: Path | None = None) -> dict[str, Any]:
    p = path or PACK_OUTPUT
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _index_pack(pack: dict[str, Any]) -> dict[str, Any]:
    idx: dict[str, Any] = {}

    for memo in pack.get("analyst_memos", []):
        idx[memo["section_id"]] = memo

    if comp := pack.get("comparison"):
        idx[comp.get("section_id", "comparison")] = comp

    if ca := pack.get("credit_analysis"):
        idx[ca.get("section_id", "credit_analysis.root")] = ca
        for key in ("comparative_notes", "risk_rollup"):
            if block := ca.get(key):
                sid = block.get("section_id") if isinstance(block, dict) else None
                if sid:
                    idx[sid] = block
        for row in ca.get("issuer_ratios", []):
            idx[row["section_id"]] = row
        for row in ca.get("covenant_analogs", []) + ca.get("policy_exceptions", []):
            idx[row["section_id"]] = row

    for root_key in ("credit_memo", "rm_memo"):
        doc = pack.get(root_key)
        if not doc:
            continue
        idx[doc.get("section_id", root_key)] = doc
        for sec in doc.get("sections", []):
            idx[sec["section_id"]] = sec

    for entry in pack.get("commentary_thread", []):
        idx[entry["section_id"]] = entry

    for issuer in pack.get("issuers", []):
        fin = issuer.get("financials", {})
        for block in ("income_statement", "balance_sheet"):
            for row in fin.get(block, []):
                idx[row["section_id"]] = row
        idx[f"{issuer['issuer_id']}.key_metrics"] = issuer.get("key_metrics")
    return idx


class PackContext:
    def __init__(self, pack_path: Path | None = None) -> None:
        self.pack = load_pack(pack_path)
        self.index = _index_pack(self.pack)


def make_pack_tools(ctx: PackContext) -> list:
    @tool
    def summarize_credit_and_rm() -> str:
        """Summary of credit memo vs RM memo — recommendations, amounts, and tension."""
        cm = ctx.pack.get("credit_memo", {})
        rm = ctx.pack.get("rm_memo", {})
        lines = [
            "=== CREDIT MEMO ===",
            f"Recommendation: {cm.get('recommendation')} | Grade: {cm.get('internal_risk_grade')}",
            f"Proposed: ${cm.get('proposed_allocation_usd', 0):,}",
            f"Author: {cm.get('author')} | section_id root: {cm.get('section_id')}",
            "",
            "=== RM MEMO ===",
            f"Recommendation: {rm.get('recommendation')} | Strategy: {rm.get('relationship_strategy')}",
            f"Proposed: ${rm.get('proposed_allocation_usd', 0):,} split TCS {rm.get('proposed_split', {}).get('tcs', 0):.0%} / HCL {rm.get('proposed_split', {}).get('hcl', 0):.0%}",
            f"Author: {rm.get('author')} | section_id root: {rm.get('section_id')}",
            "",
            "=== CREDIT ANALYSIS ROLLUP ===",
        ]
        rollup = ctx.pack.get("credit_analysis", {}).get("risk_rollup", {})
        lines.append(
            f"Color: {rollup.get('color')} | Score: {rollup.get('score_pct')}% | section_id: {rollup.get('section_id')}"
        )
        lines.append("")
        lines.append(
            "Use get_pack_section('credit_memo.recommendation') etc. for full text."
        )
        return "\n".join(lines)

    @tool
    def list_commentary_thread() -> str:
        """Ordered credit vs RM commentary before the board meeting."""
        lines = []
        for c in ctx.pack.get("commentary_thread", []):
            lines.append(f"[{c['date']}] {c['role']}: {c['text']}  ({c['section_id']})")
        return "\n".join(lines) if lines else "No commentary thread."

    @tool
    def list_analyst_stances() -> str:
        """List each board analyst's stance and USD target."""
        lines = []
        for m in ctx.pack["analyst_memos"]:
            lines.append(
                f"{m['analyst_id']}: {m['stance'].upper()} "
                f"target=${m['target_position_usd']:,} — {m['display_name']}"
            )
        return "\n".join(lines)

    @tool
    def get_pack_section(section_id: str) -> str:
        """Return JSON for a pack section_id (financial line, analyst memo, or comparison)."""
        if section_id in ctx.index:
            return json.dumps(ctx.index[section_id], indent=2)
        matches = [k for k in ctx.index if section_id in k]
        if not matches:
            return f"No section_id matching '{section_id}'. Try list_pack_sections."
        return json.dumps({k: ctx.index[k] for k in matches[:8]}, indent=2)

    @tool
    def list_pack_sections(prefix: str = "") -> str:
        """List available section_id keys; optional prefix filter (e.g. tcs. or analyst_memos.)."""
        keys = sorted(ctx.index.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return "\n".join(keys[:60]) + (
            f"\n... ({len(keys)} total)" if len(keys) > 60 else ""
        )

    @tool
    def search_pack(keyword: str) -> str:
        """Search pack JSON text for a keyword (case-insensitive)."""
        blob = json.dumps(ctx.pack).lower()
        kw = keyword.lower()
        if kw not in blob:
            return f"No matches for '{keyword}'."
        hits = [k for k in ctx.index if kw in json.dumps(ctx.index[k]).lower()]
        return "Matching section_ids:\n" + "\n".join(hits[:25])

    return [
        summarize_credit_and_rm,
        list_commentary_thread,
        list_analyst_stances,
        get_pack_section,
        list_pack_sections,
        search_pack,
    ]
