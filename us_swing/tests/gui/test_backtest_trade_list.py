"""Tests for MD-GUI-031.053.M07 — trade list and MD-GUI-031.054.M08 — screener and margin use."""
from __future__ import annotations

import sys
import types
from datetime import date
from typing import Any

import pandas as pd
import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = object  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui.backtest_trade_list import TradeList, keep, numbered  # noqa: E402
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


def test_table_and_click(qtbot: Any) -> None:
    """UT-GUI-031.053.M07.T03: Table shows the screenshot columns; a click sends the trade."""
    view = TradeList()
    qtbot.addWidget(view)
    view.set_trades(_trades())
    seen: list[pd.Series] = []
    view.trade_clicked.connect(seen.append)

    assert view.table.rowCount() == 3
    assert view.table.item(0, 1).text() == "LONG"  # type: ignore[union-attr]
    assert view.table.item(0, 4).text() == "2026-03-03 10:00:00"  # type: ignore[union-attr]
    assert view.table.item(0, 9).text() == "+100.00%"  # type: ignore[union-attr]
    view.chips.buttons[4].click()  # SHORT
    assert view.table.rowCount() == 1
    assert view.summary.text() == "1 of 3 trades · net P&L -$2.00"
    view.table.cellClicked.emit(0, 0)
    assert seen[0]["symbol"] == "MSFT"


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

    assert use.days == ["2026-03-03", "2026-03-04"]
    assert use.low == [800.0, 0.0]
    assert use.high == [200.0, 1000.0]
    assert use.facts == ("Money deployed on 1 of 2 days · average deployed peak $800 · "
                         "lowest margin $200")
    assert not panel.grab().isNull()
    panel.set_use(margin_use(money.iloc[0:0]))
    assert not panel.grab().isNull()
