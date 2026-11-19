"""Tests for the Screener focus layout (FO-GUI-043)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtCore import QObject, QSettings, Qt, pyqtSignal

from tests.gui.test_screener_views import _RESULTS, _FakeChart
from us_swing.gui import screener_panel as sp
from us_swing.gui.screener_views import ListDetailView, ResultRow, _ListRow, rows_from_result


class _Demo(QObject):
    candle_db_status_changed = pyqtSignal(object)
    market_status_updated = pyqtSignal()
    log_message = pyqtSignal(str, str)

    def get_active_user(self) -> Any:
        return SimpleNamespace(user_id="u1")

    def get_sp500_universe(self) -> list[Any]:
        return []


class _Mgr:
    def __init__(self) -> None:
        self.presets = [
            SimpleNamespace(id="a", name="Momentum Breakout", style="swing"),
            SimpleNamespace(id="b", name="Pullback to EMA", style="swing"),
        ]

    def list_admin_presets(self, style_filter: str | None = None) -> list[Any]:
        return [p for p in self.presets if style_filter in (None, p.style)]

    def list_user_presets(self, uid: str, style_filter: str | None = None) -> list[Any]:
        return []

    def load_preset(self, pid: str, uid: str) -> Any:
        name = next(p.name for p in self.presets if p.id == pid)
        return SimpleNamespace(id=pid, name=name, timeframe="1d", preset_type="weighted",
                               enable_llm_ranking=False, screeners=[], groups=[])


class _Storage:
    def __init__(self, runs: dict[str, list[str]]) -> None:
        self.runs = runs

    def list_results(self, pid: str, limit: int | None = None) -> list[str]:
        return self.runs.get(pid, [])[:limit]

    def load_result(self, pid: str, date: str) -> Any:
        return SimpleNamespace(results=_RESULTS, run_timestamp="2026-11-19T14:42:00Z",
                               execution_mode="manual", ai_transcript=[], preset_id=pid,
                               candle_date=date)


@pytest.fixture()
def make_panel(qtbot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    ini = str(tmp_path / "screener.ini")
    monkeypatch.setattr(sp, "_view_settings",
                        lambda: QSettings(ini, QSettings.Format.IniFormat))
    monkeypatch.setattr(sp, "_in_auto_run_window", lambda: False)
    monkeypatch.setattr(sp.ScreenerPanel, "_make_chart", lambda self: _FakeChart())

    def build(runs: dict[str, list[str]] | None = None) -> sp.ScreenerPanel:
        def backend(self: sp.ScreenerPanel) -> None:
            self._mgr = _Mgr()
            self._storage = _Storage({"a": ["2026-11-19"]} if runs is None else runs)

        monkeypatch.setattr(sp.ScreenerPanel, "_init_backend", backend)
        panel = sp.ScreenerPanel(_Demo())  # type: ignore[arg-type]
        qtbot.addWidget(panel)
        return panel

    return build


def _row_hidden(panel: sp.ScreenerPanel) -> dict[str, bool]:
    rows = {}
    for i in range(panel._preset_list.count()):
        item = panel._preset_list.item(i)
        pid = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if item is not None and pid:
            rows[pid] = item.isHidden()
    return rows


def test_folded_row_opens_and_folds_current(make_panel):
    """UT-GUI-043.001.M01.T01: Folded row opens and folds the current one."""
    panel = make_panel()
    panel._open_preset("a")
    assert panel._title_lbl.text() == "Momentum Breakout"
    assert _row_hidden(panel) == {"a": True, "b": False}
    panel._open_preset("b")
    assert panel._title_lbl.text() == "Pullback to EMA"
    assert _row_hidden(panel) == {"a": False, "b": True}


def test_last_open_preset_reopens(make_panel):
    """UT-GUI-043.001.M01.T02: Last open preset reopens."""
    make_panel()._open_preset("b")
    again = make_panel()
    assert again._selected_preset_id == "b"
    assert again._title_lbl.text() == "Pullback to EMA"


def test_more_menu_holds_run_actions(make_panel, qtbot):
    """UT-GUI-043.002.M01.T01: ⋯ menu holds the run actions."""
    panel = make_panel()
    panel._open_preset("a")
    menu = panel._more_btn.menu()
    assert [a.text() for a in menu.actions() if a.isVisible()] == ["Export CSV", "Quick test"]
    assert panel._export_act.isEnabled()
    with qtbot.waitSignal(panel.quick_test_requested) as blocker:
        panel._quick_act.trigger()
    assert blocker.args == ["a"]


def test_two_line_stock_row(qtbot):
    """UT-GUI-043.003.M02.T01: Two-line stock row."""
    row = ResultRow("NVDA", 0.85, name="NVIDIA Corp",
                    rules=rows_from_result(_RESULTS)[0].rules, flags=["Earnings in 2 days"])
    widget = _ListRow(row)
    qtbot.addWidget(widget)
    assert widget.symbol_lbl.text() == "NVDA"
    assert widget.score_lbl.text() == "0.85"
    assert widget.rules_lbl.text() == row.rules_text
    assert widget.flag_lbl.text() == row.flag_text != ""


def test_preset_with_no_run(make_panel):
    """UT-GUI-043.003.M01.T01: Preset with no run."""
    panel = make_panel(runs={})
    panel._open_preset("a")
    assert panel._list_stack.currentWidget() is panel._list_empty_lbl
    assert panel._list_empty_lbl.text() == "No runs yet — press Run now"


def test_detached_list_still_drives_detail(qtbot):
    """UT-GUI-043.003.M02.T02: Detached list still drives the detail."""
    view = ListDetailView()
    qtbot.addWidget(view)
    stock_list = view.detach_list()
    qtbot.addWidget(stock_list)
    view.load(rows_from_result(_RESULTS))
    stock_list.setCurrentRow(1)
    assert view.symbol_lbl.text() == "JCI"
    assert view.layout().indexOf(stock_list) == -1


def test_delete_open_preset_clears_card(make_panel, monkeypatch):
    """UT-GUI-043.001.M01.T03: Deleting the open preset clears the card."""
    monkeypatch.setattr(sp, "confirm", lambda *_a, **_k: True)
    panel = make_panel()
    panel._open_preset("a")
    panel._mgr.delete_preset = lambda pid, uid: panel._mgr.presets.pop(0)
    panel._on_delete_preset("a")
    assert panel._title_lbl.text() == "No preset open"
    assert panel._available_dates == [] and not panel._run_btn.isEnabled()
    assert panel._list_empty_lbl.text() == "No preset open"
    assert panel._settings.value("open_preset") is None


def test_search_filters_folded_rows(make_panel):
    """UT-GUI-043.004.M01.T01: Search filters folded rows."""
    panel = make_panel()
    panel._open_preset("a")
    panel._preset_search.setText("pull")
    assert _row_hidden(panel) == {"b": False}
    assert panel._title_lbl.text() == "Momentum Breakout"
    panel._preset_search.setText("momentum")
    header = panel._preset_list.item(0)
    assert header is not None and header.isHidden()


def test_hide_panel_is_saved(make_panel):
    """UT-GUI-043.005.M01.T01: Hide panel saved."""
    make_panel()._set_pane_hidden(True)
    again = make_panel()
    assert again._pane_full.isHidden() and not again._pane_strip.isHidden()
    assert again._left_frame.width() == sp._PANE_STRIP_W


def test_toolbar_and_cards_gone(make_panel):
    """UT-GUI-043.006.M01.T01: Toolbar and Cards gone."""
    panel = make_panel()
    panel._open_preset("a")
    for name in ("_view_switch", "_cards_view", "_tx_pill", "_export_btn", "_quick_btn"):
        assert not hasattr(panel, name)
    assert [panel._views.widget(i) for i in range(panel._views.count())] == [
        panel._empty_lbl, panel._list_view]
    assert panel._views.currentWidget() is panel._list_view
    assert panel._stock_list.count() == 3


_NAMES = {"NVDA": "NVIDIA Corp", "JCI": "Johnson Controls", "DHR": "Danaher"}
_SECTORS = {"NVDA": "Information Technology", "JCI": "Industrials", "DHR": "Health Care"}


def _detail(qtbot: Any) -> ListDetailView:
    view = ListDetailView(_FakeChart)
    qtbot.addWidget(view)
    stock_list = view.detach_list()
    qtbot.addWidget(stock_list)
    view.load(rows_from_result(_RESULTS, _NAMES, _SECTORS))
    return view


def test_header_line_and_next_stock(qtbot):
    """UT-GUI-043.007.M03.T01: Header line and next stock."""
    view = _detail(qtbot)
    meta = view.meta_lbl.text()
    assert meta.startswith("NVIDIA Corp · Information Technology · rank 1 of 3")
    assert "AI score 0.85" in meta
    view.next_btn.click()
    assert view.selected_symbol() == "JCI" and view.symbol_lbl.text() == "JCI"


def test_prev_next_stop_at_ends(qtbot):
    """UT-GUI-043.007.M03.T02: Previous and next stop at the ends."""
    view = _detail(qtbot)
    assert not view.prev_btn.isEnabled() and view.next_btn.isEnabled()
    view.list.setCurrentRow(2)
    assert view.prev_btn.isEnabled() and not view.next_btn.isEnabled()
    view.next_btn.click()
    assert view.selected_symbol() == "DHR"


def test_plan_strip_over_chart(qtbot):
    """UT-GUI-043.008.M03.T01: Plan strip over the chart."""
    view = _detail(qtbot)
    body = view._body
    order = [body.itemAt(i) for i in range(body.count())]
    assert order[0].layout() is not None
    assert order[1].widget().objectName() == "detail_plan"
    assert order[2].widget() is view.chart_slot
    assert view.tabs in order[3].widget().findChildren(type(view.tabs))


def test_chart_takes_free_height(qtbot):
    """UT-GUI-043.009.M03.T01: Chart takes the free height."""
    view = _detail(qtbot)
    stretches = [view._body.stretch(i) for i in range(view._body.count())]
    assert stretches == [0, 0, 1, 0]


def test_tabs_show_one_section(qtbot):
    """UT-GUI-043.010.M03.T01: Tabs show one section."""
    view = _detail(qtbot)
    titles = [view.tabs.tabText(i) for i in range(view.tabs.count())]
    assert titles == ["AI reasoning", "Rules 1/2", "News", "Fundamentals", "Bull vs bear"]
    assert view._pages.currentIndex() == 0
    view.tabs.setCurrentIndex(1)
    page = view._pages.currentWidget().widget()
    assert view.rules_head.parent() is page


def test_empty_tabs_greyed(qtbot):
    """UT-GUI-043.010.M03.T02: Empty tabs greyed."""
    view = _detail(qtbot)
    view.tabs.setTabEnabled(2, True)
    view.tabs.setCurrentIndex(2)
    view.list.setCurrentRow(1)
    assert [view.tabs.isTabEnabled(i) for i in range(5)] == [True, True, False, False, False]
    assert view.tabs.currentIndex() == 0 and view._pages.currentIndex() == 0


def test_volume_strip_drag_height():
    """UT-GUI-043.011.M04.T01: Volume strip can be dragged and keeps its height."""
    from us_swing.gui.chart_drawings import ChartBridge
    from us_swing.gui.chart_panel import _build_html

    html = _build_html([{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1}],
                       [{"time": 1, "value": 1}], "MPC", "1d", volume_height=150)
    assert 'id="volume-handle"' in html
    assert "height: 150px" in html and "bridge.set_volume_height" in html
    bridge = ChartBridge()
    got: list[int] = []
    bridge.volume_height_changed.connect(got.append)
    bridge.set_volume_height(150)
    assert got == [150]
