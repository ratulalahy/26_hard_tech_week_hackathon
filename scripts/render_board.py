#!/usr/bin/env python3
"""Render the project board's plan section from docs/plan/tasks.csv.

Usage: scripts/render_board.py <board.html> [--updated "Tue 14:55"]
Replaces the <section id="plan">…</section> block in place and copies the board to docs/status/board.html.
"""
import csv, html, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PILL = {"done": "done", "in progress": "doing", "next": "next", "queued": "next", "blocked": "risk", "cut": "next"}
ORDER = {"in progress": 0, "next": 1, "queued": 2, "blocked": 3, "done": 4, "cut": 5}


def main() -> int:
    board = Path(sys.argv[1])
    updated = sys.argv[sys.argv.index("--updated") + 1] if "--updated" in sys.argv else None
    rows = list(csv.DictReader(open(ROOT / "docs/plan/tasks.csv", newline="")))
    counts = {s: sum(r["status"] == s for r in rows) for s in ("done", "in progress", "next", "queued")}
    e = html.escape

    def tr(r):
        when = r["done_mt"] and f"done {r['done_mt']}" or (r["start_mt"] and r["eta_mt"] and f"{r['start_mt']} → {r['eta_mt']}") or r["eta_mt"] or r["start_mt"]
        note = f'<div class="meta">{e(r["notes"])}</div>' if r["notes"] else ""
        dep = f'<div class="meta">after {e(r["depends_on"].replace(";", ", "))}</div>' if r["depends_on"] and r["status"] != "done" else ""
        return (f'<tr><td>{e(r["id"])}</td><td>{e(r["task"])}{note}</td><td>{e(r["owner"])}</td>'
                f'<td>{e(when)}{dep}</td><td>{e(r["deliverable"])}</td>'
                f'<td><span class="pill {PILL.get(r["status"], "next")}">{e(r["status"])}</span></td></tr>')

    active = [r for r in rows if r["status"] != "done"]
    done = [r for r in rows if r["status"] == "done"]
    active.sort(key=lambda r: ORDER.get(r["status"], 9))
    head = '<thead><tr><th>ID</th><th>Task</th><th>Who</th><th>When (MT)</th><th>Deliverable</th><th>Status</th></tr></thead>'
    section = (
        '<section id="plan">\n  <h2>Plan and progress</h2>\n'
        f'  <p class="meta">{counts["done"]} done · {counts["in progress"]} in progress · {counts["next"]} next · {counts["queued"]} queued. '
        'Source: <code>docs/plan/tasks.csv</code>; plan doc <code>docs/plan/2026-10-27-master-plan.md</code>. Times from the system clock.</p>\n'
        f'  <h3 style="margin-top:8px">Open</h3><div class="tbl"><table>{head}<tbody>{"".join(tr(r) for r in active)}</tbody></table></div>\n'
        f'  <details style="margin-top:10px"><summary class="meta" style="cursor:pointer">Done ({len(done)})</summary>'
        f'<div class="tbl"><table>{head}<tbody>{"".join(tr(r) for r in done)}</tbody></table></div></details>\n'
        '</section>')
    text = board.read_text()
    text, n = re.subn(r'<section id="plan">.*?</section>', section, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("plan section not found")
    if updated:
        text = re.sub(r"updated [^<]*MT", f"updated {updated} MT", text, count=1)
    board.write_text(text)
    out = ROOT / "docs/status/board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(board, out)
    print(f"rendered {len(rows)} tasks into {board} and {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
