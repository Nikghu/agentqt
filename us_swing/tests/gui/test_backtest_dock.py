"""Tests for MD-GUI-031.050.M05 — gui/backtest_dock.py and MD-GUI-031.052.M06 — trade chart."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from us_swing.gui.backtest_dock import DockSection, Panel, PanelSpec
from us_swing.gui.backtest_trade_chart import TradeChart


def _section(qtbot: Any, path: Path) -> DockSection:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    section = DockSection("t", [[PanelSpec("a", "A", "list", QLabel("a")),
                                 PanelSpec("b", "B", "list", QLabel("b"))],
                                [PanelSpec("c", "C", "list", QLabel("c"))]], settings=settings)
    qtbot.addWidget(section)
    return section


def test_close_hides_and_is_remembered(qtbot: Any, tmp_path: Path) -> None:
    """UT-GUI-031.050.M05.T01: ✕ hides a panel, unticks its button and stays hidden next time."""
    section = _section(qtbot, tmp_path / "d.ini")
    panel = section.panels["a"].findChild(Panel)
    assert panel is not None

    panel.close_btn.click()

    assert not section.is_shown("a")
    assert not section.buttons["a"].isChecked()
    again = _section(qtbot, tmp_path / "d.ini")
    assert not again.is_shown("a")
    assert again.is_shown("b")


def test_strip_button_toggles_and_empty_row_hides(qtbot: Any, tmp_path: Path) -> None:
    """UT-GUI-031.050.M05.T02: Strip buttons turn panels on/off; a row with none left hides."""
    section = _section(qtbot, tmp_path / "d.ini")

    section.buttons["c"].setChecked(False)
    assert not section.is_shown("c")
    assert section._rows[1].isHidden()

    section.buttons["c"].setChecked(True)
    assert section.is_shown("c")
    assert not section._rows[1].isHidden()


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-03-03 14:30", periods=6, freq="15min", tz="UTC")
    return pd.DataFrame({"ts": ts, "open": [10.0, 11, 12, 11, 10, 9], "high": 12.5,
                         "low": 8.5, "close": [11.0, 12, 11, 10, 9, 10]})


def test_chart_places_markers(qtbot: Any) -> None:
    """UT-GUI-031.052.M06.T01: Entry and exit times map to their bars and the chart paints."""
    chart = TradeChart()
    qtbot.addWidget(chart)
    trades = pd.DataFrame({"direction": ["SHORT"],
                           "entry_ts": [pd.Timestamp("2026-03-03 14:50", tz="UTC")],
                           "entry_px": [11.5],
                           "exit_ts": [pd.Timestamp("2026-03-03 15:45", tz="UTC")],
                           "exit_px": [9.5]})
    chart.set_data(_bars(), trades)
    chart.resize(600, 300)

    assert chart._index(trades["entry_ts"][0]) == 1
    assert chart._index(trades["exit_ts"][0]) == 5
    assert not chart.grab().isNull()


def test_chart_without_bars_shows_message(qtbot: Any) -> None:
    """UT-GUI-031.052.M06.T02: No bars shows the message; a time before the bars has no index."""
    chart = TradeChart()
    qtbot.addWidget(chart)
    chart.set_data(_bars().iloc[0:0], pd.DataFrame(), "No 15m candles saved for X")

    assert chart.message == "No 15m candles saved for X"
    assert not chart.grab().isNull()
    chart.set_data(_bars(), pd.DataFrame())
    assert chart._index(pd.Timestamp("2026-03-03 14:00", tz="UTC")) is None
