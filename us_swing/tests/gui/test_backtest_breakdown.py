"""Tests for MD-GUI-031.062.M12 — gui/backtest_breakdown.py."""
from __future__ import annotations

import sys
import types
from typing import Any

import pandas as pd
import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = object  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.backtest.steps.report import Report, breakdown, with_groups  # noqa: E402
from us_swing.gui.backtest_breakdown import (  # noqa: E402
    BreakdownView,
    Row,
    group_label,
    rows,
    visible,
)
from us_swing.gui.backtest_trade_list import TradeList  # noqa: E402

_REASONS = ["stop", "strategy", "end_of_test"]


def _trades(n: int = 24) -> pd.DataFrame:
    """``n`` trades over many stocks, 09:00 to 12:00 ET (no 11:00), Monday to Thursday."""
    start = pd.Timestamp("2026-03-02 14:00", tz="UTC")
    hours = [0, 1, 3]
    entry = [start + pd.Timedelta(days=i % 4, hours=hours[i % 3]) for i in range(n)]
    pnl = [(-1) ** i * (10.0 + i) for i in range(n)]
    trades = pd.DataFrame({
        "strategy": ["S1", "S2"] * (n // 2), "symbol": [f"T{i:02d}" for i in range(n)],
        "direction": "LONG", "entry_ts": entry, "entry_px": 10.0, "qty": 1,
        "exit_ts": [t + pd.Timedelta(hours=2) for t in entry], "exit_px": 10.0,
        "exit_reason": [_REASONS[i % 3] for i in range(n)], "net_pnl": pnl,
        "score": 1.0, "rank": [1 + (i % 2) * 2 for i in range(n)],
    })
    return with_groups(trades, {})


def _report(trades: pd.DataFrame) -> Report:
    return Report("v", 1000.0, (), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), trades)


@pytest.fixture()
def view(qtbot: Any) -> BreakdownView:
    widget = BreakdownView()
    qtbot.addWidget(widget)
    widget.set_report(_report(_trades()))
    return widget


def _texts(view: BreakdownView, col: int = 0) -> list[str]:
    table = view.table
    return [table.item(r, col).text() if table.item(r, col) else ""  # type: ignore[union-attr]
            for r in range(table.rowCount())]


def test_exit_reason_names() -> None:
    """UT-GUI-031.064.M12.T01: Exit reasons read as plain words; others keep their value."""
    assert group_label("exit_reason", "stop") == "Stop loss"
    assert group_label("exit_reason", "end_of_test") == "End of test"
    assert group_label("exit_reason", "end_time") == "End time"
    assert group_label("hour", "09:00") == "09:00"


def test_natural_order_with_empty_slots() -> None:
    """UT-GUI-031.063.M12.T01: Hour and rank keep their order and show empty slots."""
    trades = _trades()
    hour = rows(breakdown(trades, "hour"), "hour")
    rank = rows(breakdown(trades, "rank"), "rank")

    assert [r.key for r in hour] == ["09:00", "10:00", "11:00", "12:00"]
    assert hour[2].trades == 0
    assert [r.key for r in rank] == ["1", "2", "3"]
    assert rank[1].trades == 0
    weekday = rows(breakdown(trades, "weekday"), "weekday")
    assert [r.key for r in weekday] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def test_named_groups_best_first() -> None:
    """UT-GUI-031.063.M12.T02: Exit reason keeps best net P&L first, with readable names."""
    out = rows(breakdown(_trades(), "exit_reason"), "exit_reason")

    assert [r.net for r in out] == sorted((r.net for r in out), reverse=True)
    assert {r.label for r in out} == {"Stop loss", "Strategy exit", "End of test"}


def test_stock_collapse_search_and_min() -> None:
    """UT-GUI-031.065.M12.T01: Long lists keep best 5 and worst 5; search and min trades filter."""
    many = [Row(f"S{i}", f"S{i}", 1 + i % 3, float(-i), 0.0, 0.0) for i in range(30)]

    collapsed = visible(many, "", 1, show_all=False)
    assert len(collapsed) == 11 and collapsed[5] is None
    assert len(visible(many, "", 1, show_all=True)) == 30
    assert [r.key for r in visible(many, "s2", 1, False) if r] == [
        "S2", *[f"S{i}" for i in range(20, 30)]]
    assert all(r is not None and r.trades >= 3 for r in visible(many, "", 3, False))


def test_table_total_low_and_empty(view: BreakdownView, qtbot: Any) -> None:
    """UT-GUI-031.064.M12.T02: Rows end with All trades; small groups marked; empty slot spans."""
    view.chips.buttons[1].click()

    names = _texts(view)
    assert names[-1] == "All trades"
    assert names[2] == "11:00" and _texts(view, 1)[2] == "No trades"
    assert view.table.columnSpan(2, 1) == 5
    assert view.table.item(0, 1).text() == "8  33%"  # type: ignore[union-attr]
    view.resize(900, 400)
    view.show()
    qtbot.waitExposed(view)
    assert not view.table.grab().isNull()


def test_single_group_chip_off(qtbot: Any) -> None:
    """UT-GUI-031.062.M12.T01: A grouping with one group is off; the view moves to the next."""
    widget = BreakdownView()
    qtbot.addWidget(widget)
    trades = _trades().assign(exit_reason="stop")
    widget.set_report(_report(trades))

    exit_chip = widget.chips.buttons[0]
    assert not exit_chip.isEnabled()
    assert exit_chip.toolTip() == "Only one exit reason in this run"
    assert widget.by == "hour"


def test_stock_tools_and_show_all(view: BreakdownView) -> None:
    """UT-GUI-031.065.M12.T02: Stock shows search and min trades; the gap row shows all."""
    view.chips.buttons[6].click()

    assert view.by == "symbol" and not view.search.isHidden()
    assert view.table.rowCount() == 12
    view._on_clicked(5, 0)
    assert view.table.rowCount() == 25
    view.search.setText("T1")
    assert view.table.rowCount() == 11


def test_row_click_filters_trade_list(view: BreakdownView, qtbot: Any) -> None:
    """UT-GUI-031.066.M12.T01: A row click narrows the Trade list; a second click clears it."""
    trades = TradeList()
    qtbot.addWidget(trades)
    trades.set_trades(view._report.trades)  # type: ignore[union-attr]
    view.group_selected.connect(trades.set_group_filter)

    view._on_clicked(0, 0)
    first = view._shown[0]
    assert first is not None
    assert trades.table.rowCount() == first.trades
    assert trades.summary.text().startswith(f"Exit reason: {first.label} · ")
    view._on_clicked(0, 0)
    assert trades.table.rowCount() == 24
    view._on_clicked(0, 0)
    view._on_clicked(view.table.rowCount() - 1, 0)
    assert trades.table.rowCount() == 24
