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
    outcome_text,
    plan_outcome,
    plan_start_index,
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
        self.bars: list[dict] = []
        self.plans: list[tuple[tuple[float, float, float] | None, int | None]] = []

    def show_symbol(self, symbol: str, timeframe: str | None = None) -> None:
        self.shown.append((symbol, timeframe))

    @property
    def candles(self) -> list[dict]:
        return self.bars

    def set_plan(self, plan: tuple[float, float, float] | None,
                 start: int | None = None) -> None:
        self.plans.append((plan, start))


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


_ACC_DIST = {"PGR": {"score": 1.0, "details": {"RallyVol": 1.34, "DropVol": 1.67, "UD": 0.77}}}


def test_numeric_details_get_plain_names():
    """UT-GUI-022.013.M01.T01: Acc / Dist numbers show plain names, units and tooltips."""
    row = rows_from_result(_ACC_DIST)[0]
    assert [(r.name, r.value) for r in row.rules] == [
        ("Rally volume", "1.34×"), ("Drop volume", "1.67×"), ("Up/down ratio", "0.77")]
    assert all(r.passed is None and r.tip for r in row.rules)
    assert row.rule_count == 0 and row.rules_text == ""


def test_numbers_only_show_details_heading(qtbot):
    """UT-GUI-022.013.M01.T02: A stock with only numbers shows "DETAILS", not "0 OF 3"."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows_from_result(_ACC_DIST))
    assert view.rules_head.text() == "DETAILS"
    mixed = rows_from_result({"X": {"score": 0.5, "details": {"UD": 0.9, "NR7_x": True}}})[0]
    assert mixed.rule_count == 1 and mixed.rules_text == "1/1"


def test_list_row_and_plan_details(qtbot):
    """UT-GUI-022.011.M01.T01: Company name, rules count and risk / reward lines."""
    rows = rows_from_result(_RESULTS, {"NVDA": "NVIDIA Corp"})
    assert rows[0].name == "NVIDIA Corp" and rows[1].name == ""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows)
    assert view.meta_lbl.text().startswith("NVIDIA Corp · rank 1 of 3")
    assert view.rules_head.text() == "RULES · 1 OF 2"  # RSI is a number, not a rule
    assert view.risk_lbl.text() == "Risk $10.00 per share"
    assert view.reward_lbl.text() == "Reward $33.00 per share"
    assert not view.rr_bar.isHidden() and abs(view.rr_bar.risk_share - 10 / 43) < 1e-9
    view.list.setCurrentRow(2)
    assert view.rr_bar.isHidden()
    assert view.risk_lbl.text() == "No trade plan from the AI for this stock"


def _bar(day: str, low: float, high: float, close: float | None = None,
         open_: float | None = None) -> dict:
    when = datetime.datetime.fromisoformat(day).replace(tzinfo=datetime.timezone.utc)
    mid = (low + high) / 2
    return {"time": int(when.timestamp()), "open": mid if open_ is None else open_,
            "high": high, "low": low, "close": mid if close is None else close, "volume": 1}


_WEEKS = [_bar(d, 99, 101, 100) for d in (
    "2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05",
    "2026-10-23", "2026-10-26", "2026-11-02", "2026-11-03", "2026-11-04")]


def _day(index: int | None) -> str | None:
    if index is None:
        return None
    return datetime.datetime.fromtimestamp(
        _WEEKS[index]["time"], tz=datetime.timezone.utc).date().isoformat()


def test_plan_starts_at_next_candle():
    """UT-GUI-022.011.M01.T02: Zone starts at the next candle after the last completed session."""
    assert _day(plan_start_index("2026-05-03T05:25:46Z", _WEEKS)) == "2026-05-04"
    assert _day(plan_start_index("2026-10-26T13:00:43Z", _WEEKS)) == "2026-10-26"
    assert _day(plan_start_index("2026-11-03T23:00:00Z", _WEEKS)) == "2026-11-04"


def test_plan_start_none_without_next_candle():
    """UT-GUI-022.011.M01.T03: No candle after the run, or no run time, gives None."""
    assert plan_start_index("2026-11-04T22:00:00Z", _WEEKS) is None
    assert plan_start_index(None, _WEEKS) is None


def test_plan_outcome_target_and_stop():
    """UT-GUI-022.011.M01.T04: Entered, then Target or Stop decides."""
    pullback = [_bar("2026-10-23", 94, 96, 95), _bar("2026-10-26", 92, 95),
                _bar("2026-10-27", 93, 97), _bar("2026-10-28", 96, 101)]
    assert plan_outcome(pullback, 1, 92.5, 90, 100) == ("target", datetime.date(2026, 10, 28))
    breakout = [_bar("2026-10-23", 98, 100, 99), _bar("2026-10-26", 99, 101.5),
                _bar("2026-10-27", 95, 100)]
    assert plan_outcome(breakout, 1, 100.75, 95.8, 112) == ("stop", datetime.date(2026, 10, 27))
    assert outcome_text(("target", datetime.date(2026, 10, 28))) == "Target hit 28 Oct"
    assert outcome_text(("stop", datetime.date(2026, 10, 27))) == "Stop hit 27 Oct"


def test_plan_outcome_not_entered_or_open():
    """UT-GUI-022.011.M01.T05: Never reaches entry, or entered with no hit yet."""
    bars = [_bar("2026-10-23", 94, 96, 95), _bar("2026-10-26", 93, 96)]
    assert plan_outcome(bars, 1, 92.5, 90, 100) == ("not_entered", None)
    bars.append(_bar("2026-10-27", 92, 95))
    assert plan_outcome(bars, 1, 92.5, 90, 100) == ("open", None)
    assert outcome_text(("open", None)) == "Open"
    assert outcome_text(("not_entered", None)) == "Not entered"


def test_plan_outcome_both_in_one_candle_and_gap():
    """UT-GUI-022.011.M01.T06: Target and Stop in one candle count as Stop; a gap enters."""
    wide = [_bar("2026-10-23", 94, 96, 95), _bar("2026-10-26", 89, 101)]
    assert plan_outcome(wide, 1, 92.5, 90, 100) == ("stop", datetime.date(2026, 10, 26))
    gap = [_bar("2026-10-23", 94, 96, 95), _bar("2026-10-26", 91, 92, open_=92)]
    assert plan_outcome(gap, 1, 92.5, 90, 100) == ("open", None)


def test_detail_draws_plan_and_tag(qtbot):
    """UT-GUI-022.011.M01.T07: Detail draws the plan from the start candle and shows the tag."""
    view = ListDetailView(_FakeChart)
    qtbot.addWidget(view)
    plan_rows = rows_from_result(_RESULTS)
    view._show_chart("NVDA")
    chart = view._chart
    assert isinstance(chart, _FakeChart)
    chart.bars = [_bar("2026-10-23", 225, 230, 228), _bar("2026-10-26", 220, 226),
                  _bar("2026-10-27", 224, 256)]
    view.load(plan_rows, "1d", "2026-10-26T13:00:00Z")
    assert chart.plans[-1] == ((222.0, 212.0, 255.0), chart.bars[1]["time"])
    assert view.outcome_lbl.text() == "Target hit 27 Oct" and not view.outcome_lbl.isHidden()
    view.list.setCurrentRow(2)
    assert chart.plans[-1] == (None, None)
    assert view.outcome_lbl.isHidden()


_CONTEXT_RESULT = {
    "COF": {
        "score": 0.6,
        "ai_context": {"earnings_date": "2026-11-21", "earnings_days": 3, "earnings_level": "red",
                       "sector": "Technology", "sector_rank": 2, "sector_count": 11,
                       "sector_move_pct": 3.4, "sector_level": "green", "market": "risk-on"},
        "ai_flags": ["Earnings in 3 days"],
    },
}


def test_context_chips_flags_and_count(qtbot):
    """UT-GUI-022.017.M01.T01: Chips, flags and ⚑ count."""
    row = rows_from_result(_CONTEXT_RESULT)[0]
    assert row.flags == ["Earnings in 3 days"]
    assert [(c.text, c.level) for c in row.chips] == [
        ("Earnings in 3 days · 21 Nov", "red"),
        ("Technology #2 of 11 · +3.4% vs RSP", "green"),
        ("Market risk-on", "green"),
    ]
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load([row])
    assert view.list.itemWidget(view.list.item(0)).flag_lbl.text() == "⚑ 1"
    assert [view._chips_box.itemAt(i).widget().accessibleName() for i in range(3)] == [
        c.text for c in row.chips]
    assert not view.flags_head.isHidden()
    assert view._flags_box.itemAt(0).widget().text() == "Earnings in 3 days"


def test_old_result_without_context(qtbot):
    """UT-GUI-022.017.M01.T02: Old result without context."""
    row = rows_from_result({"NVDA": {"score": 0.8}})[0]
    assert row.chips == [] and row.flags == []
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load([row])
    assert view.list.itemWidget(view.list.item(0)).flag_lbl.text() == ""
    assert view._chips_box.count() == 0
    assert view.flags_head.isHidden()


_NEWS_RESULT = {
    "COF": {
        "score": 0.6,
        "ai_context": {"news_tone": -0.6, "news_level": "red", "market": "",
                       "news": [{"title": "Probe opened", "source": "Reuters",
                                 "published": "2026-11-17T12:00:00Z", "url": "https://r.test/1"},
                                {"title": "Fine expected", "source": "WSJ",
                                 "published": "2026-11-16T09:00:00Z", "url": "https://w.test/2"}]},
        "ai_flags": ["Negative news", "Research: share offering"],
        "ai_research": {"summary": "Offering priced at a discount.", "risk": "share offering",
                        "sources": ["https://www.reuters.com/a", "https://sec.gov/b"]},
    },
}


def test_news_chip_list_and_research_box(qtbot):
    """UT-GUI-022.019.M01.T01: News chip, News list and Web research box."""
    row = rows_from_result(_NEWS_RESULT)[0]
    assert [(c.text, c.level) for c in row.chips] == [("News tone -0.6 · 2 headlines", "red")]
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load([row])
    assert not view.news_head.isHidden()
    texts = [view._news_box.itemAt(i).widget().text() for i in range(view._news_box.count())]
    assert len(texts) == 2 and "Probe opened" in texts[0] and "Reuters" in texts[0]
    assert not view.research_box.isHidden()
    assert view.research_lbl.text() == "Offering priced at a discount."
    links = view.research_links.text()
    assert "reuters.com" in links and "sec.gov" in links and view.research_links.openExternalLinks()


def test_no_news_or_research_hidden(qtbot):
    """UT-GUI-022.019.M01.T02: Nothing to show."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows_from_result({"NVDA": {"score": 0.8}}))
    assert view.news_head.isHidden() and view.research_box.isHidden()


_COMPANY_RESULT = {"NVDA": {
    "score": 0.8,
    "ai_context": {
        "eps_surprise_pct": -3.5, "surprise_level": "red",
        "revenue_growth_pct": 62.0, "margin_pct": 55.0, "pe": 48.0, "debt_to_equity": 0.4,
        "short_pct": 24.0, "days_to_cover": 1.3, "short_level": "red",
        "analyst_changes": [
            {"day": "2026-11-14", "firm": "Morgan Stanley", "action": "down",
             "grade": "Equal Weight", "target": 150.0},
            {"day": "2026-11-10", "firm": "Jefferies", "action": "main", "grade": "Buy",
             "target": None},
        ],
        "analyst_target_pct": 14.0, "analyst_level": "red",
    },
    "ai_review": {"bull": ["Trend above 200-day"], "bear": ["Earnings in 3 days", "2 downgrades"],
                  "verdict": "Wait", "confidence": "medium", "summary": "Let earnings pass"},
}}


def test_company_tags_and_sections(qtbot):
    """UT-GUI-022.021.M01.T01: Company tags and sections."""
    row = rows_from_result(_COMPANY_RESULT)[0]
    assert [(c.text, c.level) for c in row.chips] == [
        ("EPS miss -3.5%", "red"), ("P/E 48 · Rev +62%", ""),
        ("Short 24% of float", "red"), ("Analysts 0 up · 1 down", "red"),
    ]
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load([row])
    assert not view.fundamentals_lbl.isHidden()
    assert view.fundamentals_lbl.text().startswith("Revenue growth +62%")
    assert "short 24.0% of float" in view.fundamentals_lbl.text()
    lines = [view._analysts_box.itemAt(i).widget().text()
             for i in range(view._analysts_box.count())]
    assert lines == ["14 Nov · Morgan Stanley · downgrade to Equal Weight · target 150",
                     "10 Nov · Jefferies · kept at Buy", "Average target +14% vs price"]
    assert not view.review_box.isHidden()
    assert "Trend above 200-day" in view.review_bull_lbl.text()
    assert "2 downgrades" in view.review_bear_lbl.text()
    assert view.review_verdict_lbl.text() == (
        "Verdict: Wait (medium) — Let earnings pass  ·  differs from the ranking (#1)")


def test_no_company_or_review_hidden(qtbot):
    """UT-GUI-022.021.M01.T02: Nothing to show."""
    view = ListDetailView()
    qtbot.addWidget(view)
    view.load(rows_from_result({"NVDA": {"score": 0.8}}))
    assert view.fundamentals_lbl.isHidden() and view.analysts_head.isHidden()
    assert view.review_box.isHidden()
