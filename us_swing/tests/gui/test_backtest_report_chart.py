"""Tests for MD-GUI-031.080.M13 — gui/backtest_report_chart.py."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from us_swing.gui.backtest_report_chart import ReportChart


def _daily(n: int = 60) -> pd.DataFrame:
    days = [date(2026, 1, 2) + timedelta(days=i) for i in range(n)]
    equity = [2000.0 + 10 * i for i in range(n)]
    return pd.DataFrame({"date": days, "equity": equity,
                         "drawdown": [-0.01 * (i % 7) for i in range(n)],
                         "benchmark": [float("nan"), *[1990.0 + 5 * i for i in range(1, n)]]})


@pytest.fixture()
def chart(qtbot: Any) -> ReportChart:
    widget = ReportChart()
    qtbot.addWidget(widget)
    widget.resize(900, 360)
    widget.set_daily(_daily(), 2000.0)
    return widget


def test_index_at_maps_pixels_to_days(chart: ReportChart) -> None:
    """UT-GUI-031.081.M13.T01: x maps to the nearest day; outside the plot gives None."""
    line = chart._layout().line

    assert chart.index_at(line.left()) == 0
    assert chart.index_at(line.right()) == 59
    assert chart.index_at(line.left() + line.width() / 2) in (29, 30)
    assert chart.index_at(line.left() - 5) is None


def test_hover_lines_show_values(chart: ReportChart) -> None:
    """UT-GUI-031.081.M13.T02: The readout gives date, strategy, benchmark and drawdown."""
    assert chart.hover_lines(3) == ["05-01-2026", "Strategy   $2,030.00",
                                    "Benchmark  $2,005.00", "Drawdown   -3.0%"]
    assert chart.hover_lines(0)[2] == "Benchmark  —"


def test_mouse_moves_and_leaves(chart: ReportChart, qtbot: Any) -> None:
    """UT-GUI-031.081.M13.T03: Moving sets the hover day and paints; leaving clears it."""
    chart.show()
    qtbot.waitExposed(chart)
    line = chart._layout().line
    pos = QPointF(line.left() + 10, line.center().y())
    chart.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, pos, pos,
                                     Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                     Qt.KeyboardModifier.NoModifier))

    assert chart.hover == chart.index_at(pos.x())
    assert not chart.grab().isNull()
    chart.leaveEvent(QEvent(QEvent.Type.Leave))
    assert chart.hover is None


def test_empty_chart_paints_message(qtbot: Any) -> None:
    """UT-GUI-031.080.M13.T01: Fewer than 2 days paints the empty message and no hover."""
    widget = ReportChart()
    qtbot.addWidget(widget)
    widget.set_daily(_daily(1))

    assert widget.index_at(100) is None
    assert not widget.grab().isNull()
