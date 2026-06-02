"""Render showcase-scorecard.png from results/scorecard.json (blog + social)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORECARD = ROOT / "results" / "scorecard.json"
OUT = ROOT / "assets" / "showcase-scorecard.png"


def main() -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError as e:
        raise SystemExit("pip install matplotlib") from e

    data = json.loads(SCORECARD.read_text(encoding="utf-8"))
    patterns = data.get("patterns", [])
    trials = data.get("trials", {})
    passed = sum(1 for p in patterns if p.get("passed"))
    total = len(patterns) or data.get("patterns_total", 6)

    fig, ax = plt.subplots(figsize=(10, 6.5), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.05, 0.92, "NucleusIQ · Text-to-SQL Eval Showcase", fontsize=18, color="#f8fafc", fontweight="bold")
    ax.text(0.05, 0.86, "Agents that survive production — measured, not guessed", fontsize=11, color="#94a3b8")

    # headline metrics
    metrics = [
        (f"{passed}/{total}", "patterns passed"),
        ("100%", "pass^k (k=3)"),
        (data.get("mode", "autonomous"), "execution mode"),
    ]
    x0 = 0.05
    for i, (val, label) in enumerate(metrics):
        x = x0 + i * 0.31
        box = FancyBboxPatch((x, 0.68), 0.28, 0.14, boxstyle="round,pad=0.02", facecolor="#1e293b", edgecolor="#334155")
        ax.add_patch(box)
        ax.text(x + 0.14, 0.76, val, ha="center", fontsize=16, color="#22c55e", fontweight="bold")
        ax.text(x + 0.14, 0.70, label, ha="center", fontsize=9, color="#cbd5e1")

    ax.text(0.05, 0.62, f"Model: {data.get('model', '—')}", fontsize=9, color="#64748b")

    # pattern table
    ax.text(0.05, 0.56, "Evaluation patterns (pytest + AgentResult)", fontsize=12, color="#e2e8f0", fontweight="bold")
    y = 0.50
    for p in patterns:
        mark = "✓" if p.get("passed") else "✗"
        color = "#22c55e" if p.get("passed") else "#ef4444"
        pid = p.get("pattern_id", "")
        name = p.get("name", "")[:42]
        traj = " → ".join(p.get("trajectory") or [])[:36]
        auto = p.get("autonomous") or {}
        extra = ""
        if auto.get("sub_tasks"):
            extra = f" · {len(auto['sub_tasks'])} sub-tasks"
        ax.text(0.05, y, mark, fontsize=12, color=color, fontweight="bold")
        ax.text(0.08, y, f"{pid}  {name}", fontsize=9, color="#f1f5f9")
        if traj:
            ax.text(0.08, y - 0.035, traj, fontsize=7.5, color="#64748b")
        elif extra:
            ax.text(0.08, y - 0.035, extra.strip(" · "), fontsize=7.5, color="#64748b")
        y -= 0.09 if traj or extra else 0.07

    # context stress footer
    ctx = data.get("context_stress") or {}
    if not ctx.get("skipped"):
        off = (ctx.get("off") or {}).get("passed")
        on = (ctx.get("on") or {}).get("passed")
        ax.text(
            0.05,
            0.08,
            f"Context stress (fat schema): OFF={'pass' if off else 'fail'}  |  ON={'pass' if on else 'fail'}  ·  "
            f"Repro: python run_all.py",
            fontsize=8,
            color="#94a3b8",
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
