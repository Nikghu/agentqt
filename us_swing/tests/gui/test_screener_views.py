"""Tests for the screener result views (FO-GUI-022)."""
from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QWidget

from us_swing.gui.screener_views import (
    CSV_HEADER,
    CardsView,
    ListDetailView,
    ResultRow,
    RuleCheck,
    RunStepper,
    SideDrawer,
    ViewSwitch,
    csv_rows,
    filter_presets,
    last_run_text,
    rows_from_result,
    run_date_text,
    run_meta_text,
    sort_rows,
    transcript_pill_text,
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
    assert "rank 1 of 3" in view.meta_lbl.text()
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


def test_theme_change_keeps_selection_without_chart_reload(qtbot, rows):
    """UT-GUI-022.002.M01.T05: Theme change keeps selection, no chart reload."""
    view = ListDetailView(_FakeChart)
    qtbot.addWidget(view)
    view.load(rows)
    view.list.setCurrentRow(1)
    chart = view._chart
    assert isinstance(chart, _FakeChart)
    shown = len(chart.shown)
    view._restyle()
    assert view.selected_symbol() == "JCI"
    assert view.symbol_lbl.text() == "JCI"
    assert len(chart.shown) == shown


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


def test_filter_presets_by_search_text():
    """UT-GUI-022.007.M01.T01: Preset filter by search text."""
    presets = [SimpleNamespace(name=n) for n in ("Price Action", "Momentum_Price", "Test")]
    assert [p.name for p in filter_presets(presets, "MOM")] == ["Momentum_Price"]
    assert len(filter_presets(presets, "")) == 3


def test_last_run_text():
    """UT-GUI-022.007.M01.T02: Last-run line."""
    today = datetime.date(2026, 10, 22)
    utc = datetime.timezone.utc
    assert last_run_text("2026-10-22T13:18:16Z", 5, today, utc) == "Today 13:18 · 5 matches"
    assert last_run_text("2026-10-21T09:00:00Z", 8, today, utc) == "Oct 21 · 8 matches"
    assert last_run_text(None, 0, today, utc) == "Not run yet"
    assert last_run_text("2026-10-21T09:00:00Z", 1, today, utc) == "Oct 21 · 1 match"


def test_csv_rows_carry_plan(rows):
    """UT-GUI-022.006.M01.T01: CSV rows carry the plan."""
    lines = csv_rows([rows[0], rows[2]])
    assert lines[0] == CSV_HEADER
    assert lines[0][-4:] == ["Entry", "Stop", "Target", "R:R"]
    assert lines[1][-4:] == ["222.00", "212.00", "255.00", "3.30"]
    assert lines[2][-4:] == ["", "", "", ""]


def test_run_meta_and_date_text():
    """UT-GUI-022.008.M01.T01: Header run line and date text."""
    utc = datetime.timezone.utc
    assert run_meta_text(5, "2026-10-22T13:18:00Z", True, utc) == (
        "5 matches · ranked by AI score · run Oct 22, 2026 at 13:18")
    assert run_meta_text(1, None, False) == "1 match · ranked by score"
    assert run_date_text("2026-10-22") == "Oct 22, 2026"
    assert run_date_text("bad") == "bad"


def test_run_stepper_moves_between_runs(qtbot):
    """UT-GUI-022.009.M01.T01: Stepper arrows and menu move between saved runs."""
    stepper = RunStepper()
    qtbot.addWidget(stepper)
    stepper.set_runs(["2026-10-22", "2026-10-21", "2026-10-20"])
    assert stepper.date_btn.text() == "Oct 22, 2026"
    assert not stepper.latest_lbl.isHidden()
    assert stepper.older_btn.isEnabled() and not stepper.newer_btn.isEnabled()
    picked: list[int] = []
    stepper.index_changed.connect(picked.append)
    stepper.older_btn.click()
    assert picked == [1] and stepper.date_btn.text() == "Oct 21, 2026"
    assert stepper.latest_lbl.isHidden() and stepper.newer_btn.isEnabled()
    menu = stepper.date_btn.menu()
    assert menu is not None and len(menu.actions()) == 3
    menu.actions()[2].trigger()
    assert picked == [1, 2] and not stepper.older_btn.isEnabled()


def test_run_stepper_without_runs(qtbot):
    """UT-GUI-022.009.M01.T02: No saved runs disables the stepper."""
    stepper = RunStepper()
    qtbot.addWidget(stepper)
    stepper.set_runs([])
    assert stepper.date_btn.text() == "—"
    assert not stepper.older_btn.isEnabled() and not stepper.newer_btn.isEnabled()
    assert not stepper.date_btn.isEnabled() and stepper.latest_lbl.isHidden()


def test_transcript_pill_text():
    """UT-GUI-022.010.M01.T01: Pill shows steps and cost."""
    turns = [SimpleNamespace(tokens_input=1000, tokens_output=0),
             SimpleNamespace(tokens_input=0, tokens_output=1000)]
    assert transcript_pill_text(turns, 0.01, 0.03) == "AI transcript · 2 steps · $0.04"
    assert transcript_pill_text([SimpleNamespace()], 0.01, 0.03) == "AI transcript · 1 step"


def test_side_drawer_opens_and_closes(qtbot):
    """UT-GUI-022.010.M01.T02: Drawer opens over the right edge; Esc closes it."""
    host = QWidget()
    host.resize(1000, 600)
    qtbot.addWidget(host)
    drawer = SideDrawer("AI transcript", QWidget(), host)
    host.show()
    drawer.open_drawer()
    assert drawer.is_open and drawer.isVisible()
    assert drawer.width() == SideDrawer.WIDTH
    closed: list[bool] = []
    drawer.closed.connect(lambda: closed.append(True))
    qtbot.keyClick(drawer, Qt.Key.Key_Escape)
    assert not drawer.is_open and closed == [True]


def test_list_row_and_plan_details(qtbot):
    """UT-GUI-022.011.M01.T01: Company name, rules count and risk / reward lines."""
    rows = rows_from_result(_RESULTS, {"NVDA": "NVIDIA Corp"})
    assert rows[0].name == "NVIDIA Corp" and rows[1].name == ""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows)
    assert view.meta_lbl.text().startswith("NVIDIA Corp · rank 1 of 3")
    assert view.rules_head.text() == "RULES · 1 OF 3"
    assert view.risk_lbl.text() == "Risk $10.00 per share"
    assert view.reward_lbl.text() == "Reward $33.00 per share"
    assert not view.rr_bar.isHidden() and abs(view.rr_bar.risk_share - 10 / 43) < 1e-9
    view.list.setCurrentRow(2)
    assert view.rr_bar.isHidden()
    assert view.risk_lbl.text() == "No trade plan from the AI for this stock"
