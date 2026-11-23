"""
Module: MD-GUI-046.001.M01 / MD-GUI-046.003.M02 — custom indicator GUI tests
Parent SRD: SRD-GUI-046.001–.005, SRD-EXE-022.014

Trigger popup rows for custom indicators, the Settings Indicators section, and the
on-screen message when a strategy cannot start.
"""
from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QSpinBox
from pytestqt.qtbot import QtBot

import us_swing.data  # noqa: F401  — load data before db (db ↔ data import cycle)
from tests.execution.plugin_helpers import SWING_PLUS, swing_plus_source
from us_swing.core.indicator_plugins import REGISTRY, builtin_names, plugin_dir
from us_swing.gui import indicators_section as sec
from us_swing.gui import strategy_store as store
from us_swing.gui.app_service import AppService
from us_swing.gui.strategy_builder_dialog import _INDICATOR_NAMES, _ConditionSelectorDialog
from us_swing.gui.strategy_store import StrategyConfig

_BROKEN = swing_plus_source(('    version = "1.0"\n', ""),
                            ('indicator_name = "SWING_PLUS"', 'indicator_name = "BAD_ONE"'))


def _load(user_id: int = 1) -> None:
    REGISTRY.load_for_user(user_id, builtins=builtin_names())


def _install(user_id: int, name: str, text: str) -> Path:
    folder = plugin_dir(user_id, REGISTRY.root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def swing_plus() -> Path:
    path = _install(1, "swing_plus.py", SWING_PLUS.read_text(encoding="utf-8"))
    _load()
    return path


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "candles.db")
    monkeypatch.setattr(store, "_engine_cache", None)
    yield
    if store._engine_cache is not None:
        store._engine_cache.dispose()


def _cfg(name: str, entry: str, run_state: str = "RUNNING") -> StrategyConfig:
    return StrategyConfig(name=name, mode="auto", capital_max=25, start_time="09:35",
                          end_time="15:45", start_date="2026-06-01", end_date="2026-12-31",
                          days=["Monday"], entry_condition=entry, exit_condition="",
                          run_state=run_state)


class _Service(QObject):
    strategies_changed = pyqtSignal()
    strategy_start_refused = pyqtSignal(str, str)

    def __init__(self, user_id: int = 1) -> None:
        super().__init__()
        self.user_id = user_id
        self.reloads = 0
        self._strategy_engine = MagicMock()

    def get_active_user(self) -> SimpleNamespace:
        return SimpleNamespace(user_id=self.user_id)

    def indicator_probe(self) -> list[Any]:
        return []

    def reload_indicators(self) -> None:
        self.reloads += 1
        _load(self.user_id)

    def reload_strategy_registry(self) -> None:
        pass

    def stop_strategies(self, names: list[str]) -> None:
        AppService.stop_strategies(self, names)  # type: ignore[arg-type]


@pytest.fixture
def popups(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Answer confirm popups with ``answer`` and keep every popup text."""
    seen: dict[str, Any] = {"answer": True, "confirm": [], "notify": []}

    def fake_confirm(_parent: Any, _title: str, text: str, **_kw: Any) -> bool:
        seen["confirm"].append(text)
        return bool(seen["answer"])

    monkeypatch.setattr(sec, "confirm", fake_confirm)
    monkeypatch.setattr(sec, "notify", lambda _p, _t, text, *_a: seen["notify"].append(text))
    return seen


def _section(qtbot: QtBot, service: _Service) -> sec.IndicatorsSection:
    section = sec.IndicatorsSection(service)  # type: ignore[arg-type]
    qtbot.addWidget(section)
    return section


def _rows(section: sec.IndicatorsSection) -> list[list[str]]:
    table = section.table
    return [[table.item(r, c).text() for c in range(3)] for r in range(table.rowCount())]


# ── Trigger popup (SRD-GUI-046.001–.002) ──────────────────────────────────────

def _popup(qtbot: QtBot) -> _ConditionSelectorDialog:
    dlg = _ConditionSelectorDialog("Condition 1")
    qtbot.addWidget(dlg)
    return dlg


def test_plugin_listed_after_builtins(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.001.M01.T01: Plugin listed after built-ins."""
    combo = _popup(qtbot)._ind_combo
    items = [combo.itemText(i) for i in range(combo.count())]

    assert items == [*_INDICATOR_NAMES, "SWING_PLUS"]
    assert items[-2] == "BOSS_ST"


def test_refused_plugin_not_listed(qtbot: QtBot) -> None:
    """UT-GUI-046.001.M01.T02: Refused plugin not listed."""
    _install(1, "bad_one.py", _BROKEN)
    _load()
    assert not REGISTRY.statuses()[0].ok

    combo = _popup(qtbot)._ind_combo

    assert "BAD_ONE" not in [combo.itemText(i) for i in range(combo.count())]


def test_rows_follow_parameters(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.002.M01.T01: Rows follow ``parameters``."""
    dlg = _popup(qtbot)
    dlg._ind_combo.setCurrentText("SWING_PLUS")

    assert list(dlg._inputs) == ["Symbol Type", "Candles", "Price Swing", "Window", "Timeframe"]
    candles = dlg._inputs["Candles"]
    assert isinstance(candles, QSpinBox)
    assert (candles.minimum(), candles.maximum(), candles.value()) == (1, 500, 20)


def test_dropdowns_and_expression(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.002.M01.T02: Dropdowns and expression."""
    dlg = _popup(qtbot)
    dlg._ind_combo.setCurrentText("SWING_PLUS")
    built: list[str] = []
    dlg.condition_built.connect(built.append)

    swing = dlg._inputs["Price Swing"]
    assert isinstance(swing, QComboBox)
    assert [swing.itemText(i) for i in range(swing.count())] == ["High", "Low", "Range"]
    assert swing.currentText() == "High"
    dlg._on_add()

    assert built == ["SWING_PLUS('Spot', 20, 'High', 'Previous', '3m')"]


def test_number_box_keeps_limits(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.002.M01.T03: Number box keeps limits."""
    dlg = _popup(qtbot)
    dlg._ind_combo.setCurrentText("SWING_PLUS")
    candles = dlg._inputs["Candles"]
    assert isinstance(candles, QSpinBox)

    candles.setValue(0)
    low = candles.value()
    candles.setValue(900)

    assert (low, candles.value()) == (1, 500)


# ── Settings Indicators section (SRD-GUI-046.003–.005) ───────────────────────

def test_list_shows_status(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.003.M02.T01: List shows status."""
    _install(1, "bad_one.py", _BROKEN)
    _load()

    section = _section(qtbot, _Service())

    assert _rows(section) == [["bad_one", "", "Refused"], ["SWING_PLUS", "1.0", "Loaded"]]
    assert "version" in section.table.item(0, 3).text()


def test_other_users_indicators_hidden(qtbot: QtBot) -> None:
    """UT-GUI-046.003.M02.T02: Other user's indicators hidden."""
    _install(2, "swing_plus.py", SWING_PLUS.read_text(encoding="utf-8"))
    service = _Service(user_id=1)
    service.reload_indicators()

    assert _rows(_section(qtbot, service)) == []


def test_import_good_file(qtbot: QtBot, tmp_path: Path, popups: dict[str, Any],
                          monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.004.M02.T01: Import a good file."""
    source = tmp_path / "swing_plus.py"
    shutil.copyfile(SWING_PLUS, source)
    section = _section(qtbot, _Service())
    monkeypatch.setattr(section, "_pick_import_file", lambda: str(source))

    section.import_btn.click()

    assert (plugin_dir(1, REGISTRY.root) / "swing_plus.py").read_bytes() == source.read_bytes()
    assert _rows(section) == [["SWING_PLUS", "1.0", "Loaded"]]
    assert "runs Python code" in popups["confirm"][0]


def test_import_bad_file(qtbot: QtBot, tmp_path: Path, popups: dict[str, Any],
                         monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.004.M02.T02: Import a bad file."""
    source = tmp_path / "bad_one.py"
    source.write_text(_BROKEN, encoding="utf-8")
    service = _Service()
    section = _section(qtbot, service)
    monkeypatch.setattr(section, "_pick_import_file", lambda: str(source))

    section.import_btn.click()

    assert "version" in popups["notify"][0]
    assert not plugin_dir(1, REGISTRY.root).exists()
    assert service.reloads == 0


def test_import_warning_no(qtbot: QtBot, tmp_path: Path, popups: dict[str, Any],
                           monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.004.M02.T03: Warning answered No."""
    source = tmp_path / "swing_plus.py"
    shutil.copyfile(SWING_PLUS, source)
    checked: list[Path] = []
    monkeypatch.setattr(sec, "check_file", lambda path, **_kw: checked.append(path))
    popups["answer"] = False
    section = _section(qtbot, _Service())
    monkeypatch.setattr(section, "_pick_import_file", lambda: str(source))

    section.import_btn.click()

    assert checked == []
    assert not plugin_dir(1, REGISTRY.root).exists()


def test_export_and_reload(qtbot: QtBot, tmp_path: Path, swing_plus: Path,
                           monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.005.M02.T01: Export and Reload."""
    service = _Service()
    section = _section(qtbot, service)
    section.table.selectRow(0)
    target = tmp_path / "copy.py"
    monkeypatch.setattr(section, "_pick_export_file", lambda _name: str(target))

    section.export_btn.click()
    section.reload_btn.click()

    assert target.read_bytes() == swing_plus.read_bytes()
    assert service.reloads == 1
    assert REGISTRY.names() == {"SWING_PLUS"}


def test_remove_used_indicator(qtbot: QtBot, swing_plus: Path, db: None,
                               popups: dict[str, Any]) -> None:
    """UT-GUI-046.005.M02.T02: Remove a used indicator."""
    store.save_strategies([_cfg("WTrend_X", "SWING_PLUS('Spot', 20, 'High', 'Previous', "
                                            "'3m') > Number(1)"),
                           _cfg("Other", "Number(1) > Number(0)")])
    service = _Service()
    section = _section(qtbot, service)
    section.table.selectRow(0)

    section.remove_btn.click()

    assert "WTrend_X" in popups["confirm"][0] and "Other" not in popups["confirm"][0]
    states = {c.name: c.run_state for c in store.load_strategies()}
    assert states == {"WTrend_X": "STOPPED", "Other": "RUNNING"}
    assert not swing_plus.exists()
    assert REGISTRY.names() == frozenset()


def test_remove_answered_no(qtbot: QtBot, swing_plus: Path, db: None,
                            popups: dict[str, Any]) -> None:
    """UT-GUI-046.005.M02.T03: Remove answered No."""
    store.save_strategies([_cfg("WTrend_X", "SWING_PLUS('Spot', 20, 'High', 'Previous', "
                                            "'3m') > Number(1)")])
    popups["answer"] = False
    section = _section(qtbot, _Service())
    section.table.selectRow(0)

    section.remove_btn.click()

    assert swing_plus.exists()
    assert store.load_strategies()[0].run_state == "RUNNING"


# ── Refused start message (SRD-EXE-022.014) ──────────────────────────────────

def test_refused_start_reaches_screen(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-022.014.M05.T03: A refused start reloads the list and shows one popup."""
    import us_swing.gui.strategies_pane as sp

    service = _Service()
    changed: list[bool] = []
    service.strategies_changed.connect(lambda: changed.append(True))
    shown: list[str] = []
    monkeypatch.setattr(sp, "notify", lambda _p, _t, text, *_a: shown.append(text))
    pane = SimpleNamespace(_refused=[])
    pane._show_refused = lambda: sp.StrategiesPane._show_refused(pane)  # type: ignore[arg-type]
    service.strategy_start_refused.connect(
        lambda name, msg: sp.StrategiesPane._on_start_refused(pane, name, msg))  # type: ignore[arg-type]

    AppService._on_start_refused(service, "A", "A cannot start: indicator X is not installed")  # type: ignore[arg-type]
    AppService._on_start_refused(service, "B", "B cannot start: indicator X is not installed")  # type: ignore[arg-type]
    qtbot.waitUntil(lambda: bool(shown))

    assert changed == [True, True]
    assert shown == ["A cannot start: indicator X is not installed\n"
                     "B cannot start: indicator X is not installed"]
