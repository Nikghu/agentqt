"""
Module: MD-GUI-032.001.M01 / MD-GUI-032.002.M02 / MD-GUI-032.003.M03 — Strategies views tests
Parent SRD: SRD-GUI-032.001 – SRD-GUI-032.008
"""
from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QSettings
from pytestqt.qtbot import QtBot

# QWebEngineWidgets DLL is unavailable in the test environment — stub it.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

import us_swing.data  # noqa: E402,F401  — load data before db (db ↔ data import cycle)
import us_swing.gui.strategies_pane as sp  # noqa: E402
from us_swing.execution.trade_cycle import StrategyPnlSummary  # noqa: E402
from us_swing.gui import strategies_views as sv  # noqa: E402
from us_swing.gui.strategy_store import StrategyConfig  # noqa: E402


def _cfg(name: str, mode: str = "auto", run_state: str = "STOPPED") -> StrategyConfig:
    cfg = StrategyConfig(name=name, mode=mode, capital_max=25, start_time="09:35",
                         end_time="15:45", start_date="2026-06-01", end_date="2026-12-31",
                         days=["Monday"], entry_condition="", exit_condition="")
    cfg.run_state = run_state
    return cfg


def _configs() -> list[StrategyConfig]:
    return [_cfg("Pullback", mode="disabled"), _cfg("Breakout_SE"),
            _cfg("Breakout_LE", run_state="RUNNING")]


def _demo() -> MagicMock:
    demo = MagicMock()
    demo.get_strategies_with_open_cycles.return_value = set()
    demo.get_open_symbols_for_strategy.return_value = []
    demo.get_strategy_pnl.side_effect = lambda name, _since: (
        StrategyPnlSummary(total=412.6, trades=14, wins=8, win_rate=0.57)
        if name == "Breakout_LE" else StrategyPnlSummary()
    )
    demo.get_viewing_uid.return_value = None
    demo.cycle_query.open_cycles_for_strategy.return_value = ()
    demo.cycle_query.closed_between.return_value = ()
    demo._strategy_engine = None
    return demo


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "exec.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def save() -> Iterator[MagicMock]:
    with patch.object(sp, "save_strategies") as save_mock:
        yield save_mock


def _pane(qtbot: QtBot, settings: QSettings,
          configs: list[StrategyConfig] | None = None) -> sp.StrategiesPane:
    with patch.object(sp, "load_strategies", return_value=configs or _configs()):
        pane = sp.StrategiesPane(_demo(), settings=settings)
    qtbot.addWidget(pane)
    return pane


# ── Tabs ─────────────────────────────────────────────────────────────────────

def test_tab_order() -> None:
    """UT-GUI-032.001.M01.T01: Strategies is the first Execution tab."""
    from us_swing.gui.execution_panel import _TAB_NAMES

    assert _TAB_NAMES == ("Strategies", "Active trades", "Closed today")


# ── Row data and table ───────────────────────────────────────────────────────

def test_group_of() -> None:
    """UT-GUI-032.003.M02.T01: Live → Running, mode disabled → Disabled, else Stopped."""
    assert sv.group_of("RUNNING", "auto") == sv.RUNNING
    assert sv.group_of("STOPPED", "disabled") == sv.DISABLED
    assert sv.group_of("STOPPED", "manual") == sv.STOPPED
    assert sv.group_of("SQUARING_OFF", "disabled") == sv.RUNNING


def test_table_rows_and_order(qtbot: QtBot) -> None:
    """UT-GUI-032.004.M02.T01: One row per strategy, Running first, Disabled last."""
    demo = _demo()
    rows = sv.strategy_rows(_configs(), lambda c: c.run_state,
                            lambda n: demo.get_strategy_pnl(n, None), lambda _n: 0)
    table = sv.StrategyTable(stash=MagicMock())
    qtbot.addWidget(table)
    table.fill(rows)

    assert table.names() == ["Breakout_LE", "Breakout_SE", "Pullback"]
    first = table.topLevelItem(0)
    assert first is not None
    assert first.text(sv.COL_TOTAL) == "+$412.60"
    assert rows[0].win_rate == pytest.approx(0.57)


def test_pill_without_dot() -> None:
    """UT-GUI-032.008.M02.T01: Status pill is the status word only."""
    assert sv.pill_text("SQUARING_OFF") == "SQUARING OFF"
    assert "●" not in sv.pill_text("RUNNING")


# ── Pane ─────────────────────────────────────────────────────────────────────

def test_running_label_and_find(qtbot: QtBot, settings: QSettings) -> None:
    """UT-GUI-032.002.M03.T01: Running count and Find filter both views."""
    pane = _pane(qtbot, settings)
    assert pane.running_lbl.text() == "1 of 3 running"

    pane.find_edit.setText("break")

    assert sorted(pane.groups.names()) == ["Breakout_LE", "Breakout_SE"]
    assert sorted(pane.table.names()) == ["Breakout_LE", "Breakout_SE"]


def test_find_no_match(qtbot: QtBot, settings: QSettings) -> None:
    """UT-GUI-032.002.M03.T02: Find with no match shows no rows, keeps the pick."""
    pane = _pane(qtbot, settings)
    picked = pane._selected

    pane.find_edit.setText("zzz")

    assert pane.groups.names() == [] and pane.table.names() == []
    assert pane._selected == picked


def test_grouped_view(qtbot: QtBot, settings: QSettings) -> None:
    """UT-GUI-032.003.M03.T01: Group headers with counts; a click fills the detail."""
    pane = _pane(qtbot, settings)

    assert pane.view == sp.GROUPED
    assert pane.groups.group_counts == {sv.RUNNING: 1, sv.STOPPED: 1, sv.DISABLED: 1}
    pane.groups.picked.emit("Pullback")
    assert pane.title_lbl.text() == "Pullback"


def test_inline_detail_opens_and_closes(qtbot: QtBot, settings: QSettings) -> None:
    """UT-GUI-032.005.M03.T01: Row click opens the detail under it; second click closes."""
    pane = _pane(qtbot, settings)
    pane.set_view(sp.TABLE)

    pane.table.row_clicked.emit("Breakout_SE")
    assert pane.table.open_name == "Breakout_SE"
    assert pane.title_lbl.text() == "Breakout_SE"

    pane.table.row_clicked.emit("Breakout_SE")
    assert pane.table.open_name is None
    assert not sip.isdeleted(pane.detail)
    assert pane.detail.parent() is pane


def test_bulk_stop(qtbot: QtBot, settings: QSettings, save: MagicMock) -> None:
    """UT-GUI-032.006.M03.T01: Bulk Stop stops only the checked running strategy."""
    pane = _pane(qtbot, settings)
    pane.set_view(sp.TABLE)
    for name in ("Breakout_LE", "Breakout_SE"):
        pane.table._checks[name].setChecked(True)

    assert not pane.bulk_bar.isHidden()
    assert pane.bulk_lbl.text() == "2 selected"
    pane._bulk_run(start=False)

    states = {c.name: c.run_state for c in pane._configs}
    assert states == {"Pullback": "STOPPED", "Breakout_SE": "STOPPED",
                      "Breakout_LE": "STOPPED"}
    save.assert_called_once()


def test_bulk_start_skips_disabled(qtbot: QtBot, settings: QSettings, save: MagicMock) -> None:
    """UT-GUI-032.006.M03.T02: Bulk Start skips disabled and running strategies."""
    pane = _pane(qtbot, settings)
    pane.set_view(sp.TABLE)
    for box in pane.table._checks.values():
        box.setChecked(True)

    pane._bulk_run(start=True)

    states = {c.name: c.run_state for c in pane._configs}
    assert states == {"Pullback": "STOPPED", "Breakout_SE": "RUNNING",
                      "Breakout_LE": "RUNNING"}
    save.assert_called_once()


def test_row_button_keeps_open_detail(
    qtbot: QtBot, settings: QSettings, save: MagicMock,
) -> None:
    """UT-GUI-032.005.M03.T02: A row's Start acts on that row; the open detail stays."""
    pane = _pane(qtbot, settings)
    pane.set_view(sp.TABLE)
    pane.table.row_clicked.emit("Breakout_LE")

    pane.table.run_clicked.emit("Breakout_SE")

    assert pane._configs[1].run_state == "RUNNING"
    assert pane._selected == "Breakout_LE"
    assert pane.table.open_name == "Breakout_LE"
    assert pane.title_lbl.text() == "Breakout_LE"


def test_view_kept(qtbot: QtBot, settings: QSettings) -> None:
    """UT-GUI-032.007.M03.T01: Switching views keeps the pick; the view is restored."""
    pane = _pane(qtbot, settings)
    pane.groups.picked.emit("Pullback")

    pane.set_view(sp.TABLE)

    assert pane._selected == "Pullback"
    assert pane.table.open_name == "Pullback"
    assert _pane(qtbot, settings).view == sp.TABLE
