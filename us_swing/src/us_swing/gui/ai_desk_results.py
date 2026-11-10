"""
Module: MD-GUI-034.037.M25 — gui/ai_desk_results.py
Parent SRD: SRD-GUI-034.037
Also: SRD-GUI-034.038 (pick table)
Also: SRD-GUI-034.066 — total tiles and icon cards (console look)

The live AI Desk "Results" section: how the lead picks turned out on paper and in real
AI Desk trades, with breakdowns by decision, setup review grade and news tone. All numbers
come from ``core.desk_results``; this module only shows them.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import QHBoxLayout, QWidget

from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_results import PickLine, ResultsView, group_cells, results_view
from us_swing.gui.ai_desk_console import icon_card, tile_row
from us_swing.gui.ai_desk_sections import make_table, muted, section_frame
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
NO_PICKS = "No lead picks yet. Results show after the desk's first morning run with picks"
GROUP_COLUMNS = ("Group", "Picks", "Fills", "Finished", "Hit rate", "Avg R")
PICK_COLUMNS = ("Day", "Side", "Stock", "Decision", "Paper", "R", "Real P&L")


def total_tiles(view: ResultsView) -> tuple[tuple[str, str], ...]:
    """Tile titles and values for the paper and real totals."""
    t, r = view.total, view.real
    hit = "—" if t.hit_rate is None else f"{round(100 * t.hit_rate)}%"
    avg = "—" if t.avg_r is None else f"{t.avg_r:.2f}"
    return (("Paper picks", str(t.picks)), ("Filled", str(t.fills)), ("Hit rate", hit),
            ("Average R", avg), ("Real trades", f"{r.trades} · {r.wins} wins"),
            ("Real P&L", f"{r.pnl:.2f}"))


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
    tiles, values = tile_row(total_tiles(view))
    if view.real.pnl:
        tone = C.GREEN if view.real.pnl > 0 else C.RED
        values[-1].setStyleSheet(f"{values[-1].styleSheet()} color: {tone};")
    body.addLayout(tiles)
    groups = QHBoxLayout()
    groups.setSpacing(12)
    for title, rows in view.breakdowns.items():
        box, box_body = icon_card("chart-line", title)
        box_body.addWidget(make_table(GROUP_COLUMNS, [group_cells(g) for g in rows]))
        groups.addWidget(box, 1)
    body.addLayout(groups, 1)
    card, card_body = icon_card("table", "Picks")
    picks = make_table(PICK_COLUMNS, [_pick_cells(p) for p in view.picks])
    picks.setObjectName("results_picks")
    card_body.addWidget(picks, 1)
    body.addWidget(card, 2)
    return frame
