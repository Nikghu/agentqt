"""
Module: MD-GUI-034.037.M25 — gui/ai_desk_results.py
Parent SRD: SRD-GUI-034.037
Also: SRD-GUI-034.038 (pick table)

The live AI Desk "Results" section: how the lead picks turned out on paper and in real
AI Desk trades, with breakdowns by decision, setup review grade and news tone. All numbers
come from ``core.desk_results``; this module only shows them.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_results import PickLine, ResultsView, group_cells, results_view
from us_swing.gui.ai_desk_sections import heading, make_table, muted, section_frame

NY = ZoneInfo("America/New_York")
NO_PICKS = "No lead picks yet. Results show after the desk's first evening with picks"
GROUP_COLUMNS = ("Group", "Picks", "Fills", "Finished", "Hit rate", "Avg R")
PICK_COLUMNS = ("Day", "Side", "Stock", "Decision", "Paper", "R", "Real P&L")


def summary_text(view: ResultsView) -> str:
    """One line of paper and real totals."""
    t, r = view.total, view.real
    hit = "—" if t.hit_rate is None else f"{round(100 * t.hit_rate)}%"
    avg = "—" if t.avg_r is None else f"{t.avg_r:.2f}"
    return (f"Paper: {t.picks} picks, {t.fills} filled, hit rate {hit}, average R {avg}   ·   "
            f"Real: {r.trades} trades, {r.wins} wins, P&L {r.pnl:.2f}")


def _pick_cells(p: PickLine) -> list[str]:
    return [p.day, p.side, p.symbol, p.decision, p.status.replace("_", " ") or "—",
            "—" if p.r is None else f"{p.r:.2f}",
            "" if p.real_pnl is None else f"{p.real_pnl:.2f}"]


def results_frame(name: str, home: Path | None = None,
                  clock: Callable[[], datetime] | None = None) -> QWidget:
    """Build the Results section from the desk's pick results."""
    view = results_view(home or desk_home(), (clock or (lambda: datetime.now(NY)))())
    frame, body = section_frame(name, sample=False)
    if not view.picks:
        body.addWidget(muted(NO_PICKS))
        body.addStretch(1)
        return frame
    summary = QLabel(summary_text(view))
    summary.setObjectName("results_summary")
    body.addWidget(summary)
    groups = QHBoxLayout()
    groups.setSpacing(12)
    for title, rows in view.breakdowns.items():
        col = QVBoxLayout()
        col.addWidget(heading(title))
        col.addWidget(make_table(GROUP_COLUMNS, [group_cells(g) for g in rows]))
        box = QWidget()
        box.setLayout(col)
        groups.addWidget(box, 1)
    body.addLayout(groups, 1)
    body.addWidget(heading("Picks"))
    picks = make_table(PICK_COLUMNS, [_pick_cells(p) for p in view.picks])
    picks.setObjectName("results_picks")
    body.addWidget(picks, 2)
    return frame
