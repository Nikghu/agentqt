"""Tests for the Screener focus layout (FO-GUI-043)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from tests.gui.test_screener_views import _RESULTS, _FakeChart
from us_swing.gui import screener_panel as sp
from us_swing.gui.chart_drawings import ChartBridge
from us_swing.gui.chart_panel import _build_html
from us_swing.gui.screener_tree import FolderRow, folder_key
from us_swing.gui.screener_views import ListDetailView, ResultRow, _ListRow, rows_from_result


class _Demo(QObject):
    candle_db_status_changed = pyqtSignal(object)
    market_status_updated = pyqtSignal()
    log_message = pyqtSignal(str, str)
    sp500_updated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.universe: list[Any] = []

    def get_active_user(self) -> Any:
        return SimpleNamespace(user_id="u1")

    def get_sp500_universe(self) -> list[Any]:
        return list(self.universe)


class _Mgr:
    def __init__(self) -> None:
        self.presets = [
            SimpleNamespace(id="a", name="Momentum Breakout", trading_styles=["swing"]),
            SimpleNamespace(id="b", name="Pullback to EMA", trading_styles=[]),
            SimpleNamespace(id="c", name="Gap and Go", trading_styles=["day"]),
        ]
        self.admin = [SimpleNamespace(id="r", name="Classic Breakout", trading_styles=["swing"])]

    def list_admin_presets(self, style_filter: str | None = None) -> list[Any]:
        return list(self.admin)

    def list_user_presets(self, uid: str, style_filter: str | None = None) -> list[Any]:
        return list(self.presets)

    def load_preset(self, pid: str, uid: str) -> Any:
        name = next(p.name for p in self.presets + self.admin if p.id == pid)
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


def _folder_rows(panel: sp.ScreenerPanel) -> list[FolderRow]:
    box = panel._tree_box
    items = (box.itemAt(i) for i in range(box.count()))
    return [w for w in (it.widget() for it in items if it is not None)
            if isinstance(w, FolderRow)]


def _folders(panel: sp.ScreenerPanel) -> dict[str, tuple[str, bool]]:
    """Folder key → (count text, open) for every folder row in the tree."""
    return {r.key: (r.count_lbl.text(), bool(r.property("open"))) for r in _folder_rows(panel)}


def test_folders_by_style(make_panel):
    """UT-GUI-044.001.M02.T01: Presets grouped into style folders and Ready-made."""
    panel = make_panel()
    assert [r.key for r in _folder_rows(panel)] == ["swing", "day", "ready"]
    assert {k: v[0] for k, v in _folders(panel).items()} == {
        "swing": "2", "day": "1", "ready": "1"}
    assert folder_key(SimpleNamespace(trading_styles=["position", "day"]), admin=False) == "day"
    assert folder_key(SimpleNamespace(trading_styles=["position"]), admin=False) == "position"


def test_closed_folder_kept(make_panel):
    """UT-GUI-044.001.M02.T02: A closed folder stays closed after restart."""
    panel = make_panel()
    day = next(r for r in _folder_rows(panel) if r.key == "day")
    day.clicked.emit()
    assert _folders(panel)["day"][1] is False
    day.chevron_clicked.emit()
    assert _folders(panel)["day"][1] is True
    day.chevron_clicked.emit()
    again = make_panel()
    assert _folders(again)["day"][1] is False and _folders(again)["swing"][1] is True


def test_open_preset_in_place(make_panel):
    """UT-GUI-044.002.M02.T01: Opening a preset keeps the other open ones open."""
    panel = make_panel()
    panel._open_preset("a")
    assert panel._title_lbl.text() == "Momentum Breakout"
    assert set(panel._preset_rows) == {"b", "c", "r"}
    assert panel._open_section.isVisibleTo(panel)
    panel._open_preset("b")
    assert set(panel._preset_rows) == {"a", "c", "r"}
    assert panel._preset_rows["a"].property("open") is True
    assert panel._open_ids == ["a", "b"] and panel._selected_preset_id == "b"
    panel._preset_rows["c"].clicked.emit()
    assert panel._selected_preset_id == "c"


def test_open_reveals_closed_folder(make_panel):
    """UT-GUI-044.002.M02.T04: Opening a preset opens its closed folder."""
    panel = make_panel()
    panel._collapse_all()
    panel._open_preset("c")
    folders = _folders(panel)
    assert folders["day"][1] is True and folders["swing"][1] is False
    panel._collapse_all()
    assert _folders(panel)["day"][1] is False


def test_folder_click_during_search_not_saved(make_panel):
    """UT-GUI-044.005.M02.T03: Folder clicks during a search are not saved."""
    panel = make_panel()
    panel._search_btn.click()
    panel._preset_search.setText("gap")
    day = next(r for r in _folder_rows(panel) if r.key == "day")
    day.clicked.emit()
    assert panel._settings.value("closed_folders") is None


def test_last_open_preset_reopens(make_panel):
    """UT-GUI-044.002.M02.T02: Last open preset reopens."""
    make_panel()._open_preset("b")
    again = make_panel()
    assert again._selected_preset_id == "b"
    assert again._title_lbl.text() == "Pullback to EMA"


def test_delete_open_preset_clears(make_panel, monkeypatch):
    """UT-GUI-044.002.M02.T03: Deleting the open preset clears it."""
    monkeypatch.setattr(sp, "confirm", lambda *_a, **_k: True)
    panel = make_panel()
    panel._open_preset("a")
    panel._mgr.delete_preset = lambda pid, uid: panel._mgr.presets.pop(0)
    panel._on_delete_preset("a")
    assert panel._title_lbl.text() == "No preset open"
    assert panel._available_dates == [] and not panel._run_btn.isEnabled()
    assert not panel._open_section.isVisibleTo(panel)
    assert panel._settings.value("open_preset") is None


def test_open_row_actions(make_panel, qtbot):
    """UT-GUI-044.003.M02.T01: Open preset row shows count, Run and the ⋯ menu."""
    panel = make_panel()
    panel._open_preset("a")
    assert panel._count_lbl.text() == "3" and panel._run_btn.isEnabled()
    menu = panel._more_btn.menu()
    shown = [a.text() for a in menu.actions() if a.isVisible() and not a.isSeparator()]
    assert shown == ["Export CSV", "Quick test", "Sort by"]
    with qtbot.waitSignal(panel.quick_test_requested) as blocker:
        panel._quick_act.trigger()
    assert blocker.args == ["a"]


def test_controls_moved(make_panel):
    """UT-GUI-044.003.M02.T02: Date in the header, tags on the name row, Sort in the ⋯ menu."""
    panel = make_panel()
    assert panel._run_stepper.isHidden()
    panel._open_preset("a")
    header = panel._search_btn.parentWidget()
    assert panel._run_stepper.parentWidget() is header and not panel._run_stepper.isHidden()
    assert panel._open_row.row.indexOf(panel._type_tag) == -1
    assert panel._status_lbl.parentWidget() is panel._type_tag.parentWidget()
    assert not panel._type_tag.isHidden() and not panel._mode_badge.isHidden()
    assert not hasattr(panel, "_sort_combo")
    panel._sort_acts["rules"].trigger()
    assert panel._sort_key == "rules" and panel._sort_acts["rules"].isChecked()
    assert not panel._sort_acts["score"].isChecked()


def test_one_line_stock_row(qtbot):
    """UT-GUI-044.004.M03.T01: One-line stock row with score bar and flags."""
    row = ResultRow("NVDA", 0.85, name="NVIDIA Corp",
                    rules=rows_from_result(_RESULTS)[0].rules, flags=["Earnings in 2 days"])
    widget = _ListRow(row)
    qtbot.addWidget(widget)
    assert widget.symbol_lbl.text() == "NVDA"
    assert widget.score_bar._fill == 0.85
    assert widget.flag_lbl.text() == row.flag_text != ""


def test_stock_list_fits_rows(make_panel):
    """UT-GUI-044.004.M02.T01: Stock list sized to its rows; no run shows a hint."""
    panel = make_panel()
    panel._open_preset("a")
    assert panel._stock_list.height() >= 3 * sp.STOCK_ROW_H
    assert not panel._stock_list.isHidden() and panel._list_empty_lbl.isHidden()
    panel._open_preset("b")
    assert panel._stock_list.isHidden()
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


def test_search_box(make_panel):
    """UT-GUI-044.005.M02.T01: Search shows a box that filters and opens folders."""
    panel = make_panel()
    panel._collapse_all()
    assert panel._search_wrap.isHidden()
    panel._search_btn.click()
    assert not panel._search_wrap.isHidden()
    panel._preset_search.setText("pull")
    assert set(panel._preset_rows) == {"b"} and _folders(panel)["swing"][1] is True
    panel._search_btn.click()
    assert panel._search_wrap.isHidden() and panel._preset_search.text() == ""
    assert _folders(panel)["swing"][1] is False


def test_collapse_all(make_panel):
    """UT-GUI-044.005.M02.T02: Collapse all closes every folder."""
    panel = make_panel()
    panel._collapse_btn.click()
    assert all(not is_open for _count, is_open in _folders(panel).values())


def test_status_line(make_panel):
    """UT-GUI-044.006.M02.T01: Status line shows the last run and matches."""
    panel = make_panel()
    panel._open_preset("a")
    assert panel._status_lbl.text().startswith("3 matches")


def test_removed_parts(make_panel):
    """UT-GUI-044.007.M02.T01: Hide panel, style chips and the open card are gone."""
    panel = make_panel()
    for name in ("_pane_strip", "_style_chips", "_open_card", "_set_pane_hidden",
                 "_preset_list"):
        assert not hasattr(panel, name)


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
    assert order[3].widget() is view.tabs_bar
    assert view.tabs in order[4].widget().findChildren(type(view.tabs))


def test_chart_takes_free_height(qtbot):
    """UT-GUI-043.009.M03.T01: Chart takes the free height."""
    view = _detail(qtbot)
    stretches = [view._body.stretch(i) for i in range(view._body.count())]
    assert stretches == [0, 0, 1, 0, 0]


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
    html = _build_html([{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1}],
                       [{"time": 1, "value": 1}], "MPC", "1d", volume_height=150)
    assert 'id="volume-handle"' in html
    assert "height: 150px" in html and "bridge.set_volume_height" in html
    bridge = ChartBridge()
    got: list[int] = []
    bridge.volume_height_changed.connect(got.append)
    bridge.set_volume_height(150)
    assert got == [150]


def test_drag_tabs_taller(qtbot, tmp_path, monkeypatch):
    """UT-GUI-043.012.M03.T01: Dragging the bar up makes the tabs taller; height kept."""
    from us_swing.gui import screener_views as sv
    ini = str(tmp_path / "detail.ini")
    monkeypatch.setattr(sv, "_detail_settings",
                        lambda: QSettings(ini, QSettings.Format.IniFormat))
    view = _detail(qtbot)
    view._tabs_box.parentWidget().resize(900, 1000)
    start = view._tabs_box.height()
    view.tabs_bar.moved.emit(-100)
    view.tabs_bar.released.emit()
    assert view._tabs_box.height() == start + 100
    view.tabs_bar.moved.emit(5000)
    assert view._tabs_box.height() == sv._TABS_MIN_H
    again = _detail(qtbot)
    assert again._tabs_box.height() == start + 100


def _preview_lists(panel: sp.ScreenerPanel) -> list[Any]:
    from PyQt6.QtWidgets import QListWidget
    return [w for w in panel._tree_host.findChildren(QListWidget)
            if w is not panel._stock_list and w.isVisibleTo(panel._tree_host)]


def test_several_presets_open(make_panel):
    """UT-GUI-044.010.M02.T01: Several presets open; others show their latest run."""
    panel = make_panel(runs={"a": ["2026-11-19"], "b": ["2026-11-18"]})
    panel._open_preset("a")
    panel._open_preset("b")
    previews = _preview_lists(panel)
    assert len(previews) == 1 and previews[0].count() == 3
    assert panel._selected_preset_id == "b" and panel._run_btn.parentWidget() is panel._open_row
    previews[0].itemClicked.emit(previews[0].item(1))
    assert panel._selected_preset_id == "a"
    assert panel._list_view.selected_symbol() == panel._latest_rows("a")[1].symbol


def test_preview_names_after_universe_loads(make_panel):
    """UT-GUI-044.010.M02.T04: An open preset that is not active shows company names once the
    stock list loads after start."""
    panel = make_panel(runs={"a": ["2026-11-19"], "b": ["2026-11-18"]})
    panel._open_preset("a")
    panel._open_preset("b")
    assert all(not row.name for row in panel._latest_rows("a"))
    panel._demo.universe = [SimpleNamespace(symbol=row.symbol, name=f"{row.symbol} Inc",
                                            sector="Energy")
                            for row in panel._latest_rows("a")]
    panel._demo.sp500_updated.emit()
    rows = panel._latest_rows("a")
    assert all(row.name == f"{row.symbol} Inc" and row.sector == "Energy" for row in rows)
    assert len(_preview_lists(panel)) == 1


def test_chevron_closes_preset(make_panel):
    """UT-GUI-044.010.M02.T02: Chevron closes a preset; closing the active one moves on."""
    panel = make_panel()
    panel._open_preset("a")
    panel._open_preset("b")
    panel._open_row.chevron_clicked.emit()
    assert panel._open_ids == ["a"] and panel._selected_preset_id == "a"
    panel._open_row.chevron_clicked.emit()
    assert panel._open_ids == [] and panel._selected_preset_id is None
    assert panel._run_stepper.isHidden()
    panel._preset_rows["c"].chevron_clicked.emit()
    assert panel._open_ids == ["c"]


def test_open_presets_kept(make_panel):
    """UT-GUI-044.010.M02.T03: Open presets and the active one kept after restart."""
    panel = make_panel()
    panel._open_preset("c")
    panel._open_preset("a")
    panel._settings.setValue("open_presets", ["gone", "c", "a"])
    again = make_panel()
    assert again._open_ids == ["c", "a"] and again._selected_preset_id == "a"
    assert again._preset_rows["c"].property("open") is True


def test_drag_pane_width(make_panel):
    """UT-GUI-044.009.M02.T01: Drag the panel edge; width kept within 300–600 px."""
    panel = make_panel()
    assert panel._left_frame.width() == sp._PANE_W
    panel._pane_handle.moved.emit(60)
    panel._pane_handle.released.emit()
    assert panel._left_frame.width() == sp._PANE_W + 60
    panel._pane_handle.moved.emit(-1000)
    assert panel._left_frame.width() == sp._PANE_MIN_W and panel._pane_title.isHidden()
    panel._pane_handle.moved.emit(5000)
    assert panel._left_frame.width() == sp._PANE_MAX_W
    assert make_panel()._left_frame.width() == sp._PANE_W + 60

