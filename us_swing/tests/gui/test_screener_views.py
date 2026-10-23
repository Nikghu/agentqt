"""Tests for the screener result views (FO-GUI-022)."""
from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QWidget

from us_swing.gui.screener_views import (
    CSV_HEADER,
    CardsView,
    ListDetailView,
    ResultRow,
    RuleCheck,
    ViewSwitch,
    csv_rows,
    rows_from_result,
    sort_rows,
)

_RESULTS = {
    "JCI": {"score": 0.75, "details": {"VolBreak_x": False, "NR7_x": True},
            "ai_reasoning": "Near the 50-day MA",
            "ai_plan": {"entry": 151, "stop": 144, "target": 175}},
    "NVDA": {"score": 0.85, "details": {"VolBreak_x": False, "NR7_x": True, "RSI_x": 58.2},
             "ai_reasoning": "Support held at the 200-day MA",
             "ai_plan": {"entry": 222, "stop": 212, "target": 255}},
    "DHR": {"score": 0.2, "details": {"VolBreak_x": True}, "ai_reasoning": ""},
}


class _FakeChart(QWidget):
    instances = 0

    def __init__(self) -> None:
        super().__init__()
        _FakeChart.instances += 1
        self.shown: list[tuple[str, str | None]] = []

    def show_symbol(self, symbol: str, timeframe: str | None = None) -> None:
        self.shown.append((symbol, timeframe))


@pytest.fixture()
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "views.ini"), QSettings.Format.IniFormat)


@pytest.fixture()
def rows() -> list[ResultRow]:
    return rows_from_result(_RESULTS)


def test_view_switch_saves_and_restores(qtbot, settings):
    """UT-GUI-022.001.M01.T01: View switch saves and restores."""
    switch = ViewSwitch(settings)
    qtbot.addWidget(switch)
    assert switch.view == "list"
    with qtbot.waitSignal(switch.view_changed) as blocker:
        switch.buttons["cards"].click()
    assert blocker.args == ["cards"]
    again = ViewSwitch(settings)
    qtbot.addWidget(again)
    assert again.view == "cards"
    assert again.buttons["cards"].isChecked()


def test_view_switch_unknown_value_falls_back(qtbot, settings):
    """UT-GUI-022.001.M01.T02: Unknown saved view falls back."""
    settings.setValue("view", "grid")
    switch = ViewSwitch(settings)
    qtbot.addWidget(switch)
    assert switch.view == "list"


def test_list_loads_and_shows_first(qtbot, rows):
    """UT-GUI-022.002.M01.T01: List loads and shows first stock."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows)
    assert view.list.count() == 3
    assert view.selected_symbol() == "NVDA"
    assert view.symbol_lbl.text() == "NVDA"
    assert "Rank 1 of 3" in view.meta_lbl.text()
    assert view.tiles["entry"].text() == "$222.00"
    assert view.tiles["rr"].text() == "3.3 R"
    assert view.reasoning_lbl.text() == "Support held at the 200-day MA"


def test_selection_updates_detail_and_chart(qtbot, rows):
    """UT-GUI-022.002.M01.T02: Selection updates detail and chart."""
    _FakeChart.instances = 0
    view = ListDetailView(_FakeChart)
    qtbot.addWidget(view)
    view.load(rows, "1d")
    view.list.setCurrentRow(1)
    assert view.symbol_lbl.text() == "JCI"
    chart = view._chart
    assert isinstance(chart, _FakeChart)
    assert chart.shown[-1] == ("JCI", "1d")
    assert _FakeChart.instances == 1


def test_missing_plan_shows_dashes(qtbot, rows):
    """UT-GUI-022.002.M01.T03: Missing plan shows dashes."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows)
    view.list.setCurrentRow(2)
    assert view.symbol_lbl.text() == "DHR"
    assert [view.tiles[k].text() for k in ("entry", "stop", "target", "rr")] == ["—"] * 4


def test_detail_buttons_emit_symbol(qtbot, rows):
    """UT-GUI-022.002.M01.T04: Detail buttons emit symbol."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows)
    with qtbot.waitSignal(view.chart_requested) as chart:
        view.chart_btn.click()
    with qtbot.waitSignal(view.watchlist_requested) as watch:
        view.watch_btn.click()
    assert chart.args == ["NVDA"]
    assert watch.args == ["NVDA"]


def test_cards_one_per_stock_with_actions(qtbot, rows):
    """UT-GUI-022.003.M01.T01: One card per stock with actions."""
    view = CardsView()
    qtbot.addWidget(view)
    view.load(rows)
    assert len(view.cards) == 3
    first = view.cards[0]
    assert (first.rank_lbl.text(), first.symbol_lbl.text(), first.tier_lbl.text()) == (
        "#1", "NVDA", "Strong")
    with qtbot.waitSignal(view.chart_requested) as blocker:
        view.cards[1].chart_btn.click()
    assert blocker.args == ["JCI"]


def test_cards_cleared_by_empty_load(qtbot, rows):
    """UT-GUI-022.003.M01.T02: Empty rows clear cards."""
    view = CardsView()
    qtbot.addWidget(view)
    view.load(rows)
    view.load([])
    assert view.cards == []


def test_rows_built_from_result_meta(rows):
    """UT-GUI-022.004.M01.T01: Rows built from result meta."""
    assert [r.symbol for r in rows] == ["NVDA", "JCI", "DHR"]
    assert [r.rank for r in rows] == [1, 2, 3]
    nvda = rows[0]
    assert nvda.rules == [RuleCheck("VolBreak", False), RuleCheck("NR7", True),
                          RuleCheck("RSI", None, "58.20")]
    assert (nvda.entry, nvda.stop, nvda.target) == (222.0, 212.0, 255.0)
    assert [r.tier for r in rows] == ["Strong", "Strong", "Weak"]
    assert ResultRow("X", 0.55).tier == "Watch"


def test_rr_and_sort():
    """UT-GUI-022.005.M01.T01: R:R and sort."""
    good = ResultRow("A", 0.5, rank=1, entry=222, stop=212, target=255,
                     rules=[RuleCheck("x", True)])
    short = ResultRow("B", 0.9, rank=2, entry=100, stop=110, target=80,
                      rules=[RuleCheck("x", True), RuleCheck("y", True)])
    none = ResultRow("C", 0.7, rank=3)
    assert good.rr == pytest.approx(3.3)
    assert short.rr is None
    assert none.rr is None
    assert [r.symbol for r in sort_rows([none, short, good], "rr")] == ["A", "B", "C"]
    assert [r.symbol for r in sort_rows([none, good, short], "rules")] == ["B", "A", "C"]
    assert [r.symbol for r in sort_rows([none, short, good], "score")] == ["A", "B", "C"]


def test_csv_rows_carry_plan(rows):
    """UT-GUI-022.006.M01.T01: CSV rows carry the plan."""
    lines = csv_rows([rows[0], rows[2]])
    assert lines[0] == CSV_HEADER
    assert lines[0][-4:] == ["Entry", "Stop", "Target", "R:R"]
    assert lines[1][-4:] == ["222.00", "212.00", "255.00", "3.30"]
    assert lines[2][-4:] == ["", "", "", ""]
