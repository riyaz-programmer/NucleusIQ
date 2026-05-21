# Pack contents inventory (v0.2)

After **Phase A** in the showcase notebook (or `committee.pack_builder.write_pack()`), `data/02_output/investment_committee_pack.json` includes:

## Bank-style artifacts (added v0.2)

| Block | section_id root | Purpose |
|-------|-----------------|--------|
| **credit_analysis** | `credit_analysis.root` | Ratios per issuer, conditions, policy exceptions, AMBER risk rollup |
| **credit_memo** | `credit_memo.root` | **APPROVE_WITH_CONDITIONS** — $600K, 60% TCS / 40% HCL |
| **rm_memo** | `rm_memo.root` | **APPROVE** — $900K, 45% TCS / 55% HCL (disagrees with credit) |
| **commentary_thread** | `commentary_thread.001` … `007` | Credit ↔ RM email-style thread |

### Credit memo sections

- `credit_memo.executive_summary`
- `credit_memo.financial_analysis`
- `credit_memo.key_risks`
- `credit_memo.covenants_conditions`
- `credit_memo.recommendation`

### RM memo sections

- `rm_memo.relationship`
- `rm_memo.commercial_rationale`
- `rm_memo.response_to_credit`
- `rm_memo.recommendation`

## Other pack blocks

| Block | Notes |
|-------|--------|
| **issuers** | TCS + HCL FY25 P&L/BS extracts |
| **comparison** | Side-by-side revenue/margin |
| **analyst_memos** | Five board analysts (A–E) |
| **chair_brief** | Secretariat summary of credit vs RM split |

## Intentional tension (for devil's advocate)

| Party | $ | TCS / HCL |
|-------|---|-----------|
| Credit | $600K | 60% / 40% |
| RM | $900K | 45% / 55% |
| Analyst A | $750K buy | 75% / 25% |
| Analyst B | $650K buy | 35% / 65% |

Agent tools: `summarize_credit_and_rm`, `list_commentary_thread`, `get_pack_section`, …
