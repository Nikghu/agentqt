"""Tests for MD-GUI-031.053.M07 — trade list and MD-GUI-031.054.M08 — screener and margin use."""
from __future__ import annotations

import sys
import types
from datetime import date
from typing import Any

import pandas as pd
import pytest
from PyQt6.QtCore import Qt

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = object  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui.backtest_trade_list import TradeList, events, keep, numbered  # noqa: E402
from us_swing.gui.backtest_use_charts import UsePanel, margin_use, screener_use  # noqa: E402


def _trades() -> pd.DataFrame:
    ts = pd.Timestamp("2026-03-03 15:00", tz="UTC")
    return pd.DataFrame({
        "strategy": ["S1", "S1", "S2"], "symbol": ["MSFT", "AAPL", "NVDA"],
        "direction": ["SHORT", "LONG", "LONG"],
        "entry_ts": [ts + pd.Timedelta(hours=1), ts, ts + pd.Timedelta(days=1)],
        "entry_px": [20.0, 10.0, 50.0], "qty": [1, 3, 2],
        "exit_ts": [ts + pd.Timedelta(hours=2), ts + pd.Timedelta(minutes=90),
                    ts + pd.Timedelta(days=1, hours=3)],
        "exit_px": [22.0, 20.0, 50.0], "exit_reason": ["stop", "strategy", "end_time"],
        "net_pnl": [-2.0, 30.0, 0.0],
    })


def test_numbered_adds_columns() -> None:
    """UT-GUI-031.053.M07.T01: Trades get #, P&L %, hours and ET day in entry order."""
    out = numbered(_trades())

    assert list(out["symbol"]) == ["AAPL", "MSFT", "NVDA"]
    assert list(out["number"]) == [1, 2, 3]
    assert out["pnl_pct"].iloc[0] == pytest.approx(100.0)
    assert out["hours"].iloc[0] == pytest.approx(1.5)
    assert out["day"].iloc[2] == date(2026, 3, 4)


def test_filters() -> None:
    """UT-GUI-031.053.M07.T02: Wins, Losses, LONG and SHORT keep the right rows; 0 is a loss."""
    out = numbered(_trades())

    assert list(keep(out, "wins")["symbol"]) == ["AAPL"]
    assert list(keep(out, "losses")["symbol"]) == ["MSFT", "NVDA"]
    assert list(keep(out, "SHORT")["symbol"]) == ["MSFT"]
    assert len(keep(out, "all")) == 3


def _text(view: TradeList, row: int, col: int) -> str:
    return view.table.item(row, col).text()  # type: ignore[union-attr]


def test_table_and_click(qtbot: Any) -> None:
    """UT-GUI-031.053.M07.T03: Table shows the columns; a click sends that row's trade."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades(), 1000.0)
    seen: list[pd.Series] = []
    view.trade_clicked.connect(seen.append)

    assert view.table.rowCount() == 6
    assert _text(view, 0, 2) == "LONG"
    assert _text(view, 0, 6) == "03-03-2026 10:00:00"
    view.chips.buttons[4].click()  # SHORT
    assert view.table.rowCount() == 2
    assert view.summary.text() == "1 of 3 trades · net P&L -$2.00"
    view.table.cellClicked.emit(1, 0)
    assert seen[0]["symbol"] == "MSFT"
    assert seen[0]["number"] == 2


def test_entry_exit_rows_in_time_order(qtbot: Any) -> None:
    """UT-GUI-031.089.M07.T01: Entry and Exit rows in time order; Available after each row."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades(), 1000.0)
    headers = [view.table.horizontalHeaderItem(c).text()  # type: ignore[union-attr]
               for c in range(view.table.columnCount())]

    assert headers[:8] == ["Trade #", "Trade", "Type", "Symbol", "Sector", "Strategy", "Time",
                           "Price"]
    assert [(_text(view, r, 3), _text(view, r, 1)) for r in range(6)] == [
        ("AAPL", "Entry"), ("MSFT", "Entry"), ("AAPL", "Exit"), ("MSFT", "Exit"),
        ("NVDA", "Entry"), ("NVDA", "Exit")]
    assert [_text(view, r, 14) for r in range(6)] == [
        "$970.00", "$950.00", "$980.00", "$1,000.00", "$900.00", "$1,000.00"]
    assert _text(view, 0, 7) == "10.00"
    assert _text(view, 2, 7) == "20.00"
    assert [_text(view, 0, c) for c in (9, 10, 11, 12, 15, 16)] == [""] * 6
    assert [_text(view, 2, c) for c in (9, 10, 15, 16)] == ["$30.00", "+100.00%", "0.1",
                                                          "strategy"]
    assert _text(view, 0, 13) == "$30.00"
    assert numbered(_trades())["days"].iloc[0] == pytest.approx(1.5 / 24)


def test_idle_capital_shaded_red(qtbot: Any) -> None:
    """UT-GUI-031.090.M07.T01: Available above 80% of start capital is shaded red; others not."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades(), 100.0)

    shown = [_text(view, r, 14) for r in range(6)]
    red = [view.table.item(r, 14).background().style()  # type: ignore[union-attr]
           != Qt.BrushStyle.NoBrush for r in range(6)]

    assert shown == ["$70.00", "$50.00", "$80.00", "$100.00", "$0.00", "$100.00"]
    assert red == [False, False, False, True, False, True]
    view.set_trades(_trades())
    assert view.table.item(0, 14).background().style() == Qt.BrushStyle.NoBrush  # type: ignore[union-attr]


def test_exit_before_entry_at_same_time() -> None:
    """UT-GUI-031.089.M07.T02: An exit at the same time as an entry frees its money first."""
    trades = numbered(_trades().iloc[1:2])
    later = trades.assign(entry_ts=trades["exit_ts"], exit_ts=trades["exit_ts"]
                          + pd.Timedelta(hours=1), number=2)

    out = events(pd.concat([trades, later], ignore_index=True), 100.0)

    assert list(out["event"]) == ["Entry", "Exit", "Entry", "Exit"]
    assert list(out["avail"]) == [70.0, 100.0, 70.0, 100.0]


def test_available_unknown_without_capital(qtbot: Any) -> None:
    """UT-GUI-031.089.M07.T03: With no start capital, Available shows a dash."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades())

    assert _text(view, 0, 14) == "—"
    assert _text(view, 0, 13) == "$30.00"
    assert _text(view, 2, 12) == "—"


def test_cumulative_pnl_and_sector(qtbot: Any) -> None:
    """UT-GUI-031.095.M07.T01: Exit rows show cumulative P&L in $ and % of capital; Sector shown."""
    from PyQt6.QtGui import QColor

    from us_swing.gui.theme import C

    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades(), 1000.0, {"AAPL": "Information Technology"})
    headers = [view.table.horizontalHeaderItem(c).text()  # type: ignore[union-attr]
               for c in (4, 11, 12)]

    assert headers == ["Sector", "Cumulative P&L", "Cumulative P&L %"]
    assert [_text(view, r, 11) for r in range(6)] == [
        "", "", "$30.00", "$28.00", "", "$28.00"]
    assert [_text(view, r, 12) for r in (2, 3)] == ["+3.00%", "+2.80%"]
    assert view.table.item(3, 11).foreground().color() == QColor(C.GREEN)  # type: ignore[union-attr]
    assert [_text(view, r, 4) for r in (0, 1)] == ["Information Technology", "Unknown"]
    assert list(events(numbered(_trades().iloc[:1]), None)["total"]) == [0.0, -2.0]


def test_empty_trade_list(qtbot: Any) -> None:
    """UT-GUI-031.053.M07.T04: No trades shows an empty table and a zero summary."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades().iloc[0:0])

    assert view.table.rowCount() == 0
    assert view.summary.text() == "0 of 0 trades · net P&L $0.00"


def test_screener_use() -> None:
    """UT-GUI-031.054.M08.T01: Picks per session split into traded and not; empty day is 0."""
    picks = pd.DataFrame({"date": [date(2026, 3, 3)] * 2 + [date(2026, 3, 4)],
                          "symbol": ["AAPL", "TSLA", "NVDA"]})
    days = [date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)]

    use = screener_use(days, picks, _trades())

    assert use.low == [0.0, 1.0, 1.0]
    assert use.high == [0.0, 1.0, 0.0]
    assert use.facts == "3 sessions · 2 with picks · 1.0 picks a day · 2 of 3 picks traded"


def test_margin_use_and_panel(qtbot: Any) -> None:
    """UT-GUI-031.054.M08.T02: Deployed and margin per day; the panel paints; no days is safe."""
    money = pd.DataFrame({"date": [date(2026, 3, 4), date(2026, 3, 3)],
                          "start_capital": [1000.0, 1000.0], "margin_min": [1000.0, 200.0]})

    use = margin_use(money)
    panel = UsePanel(("#f00", "#0f0"), ("a", "b"), money=True)
    qtbot.addWidget(panel)
    panel.resize(500, 220)
    panel.set_use(use)

    assert use.days == ["03-03-2026", "04-03-2026"]
    assert use.low == [800.0, 0.0]
    assert use.high == [200.0, 1000.0]
    assert use.facts == ("Money deployed on 1 of 2 days · average deployed peak $800 · "
                         "lowest margin $200")
    assert not panel.grab().isNull()
    panel.set_use(margin_use(money.iloc[0:0]))
    assert not panel.grab().isNull()
