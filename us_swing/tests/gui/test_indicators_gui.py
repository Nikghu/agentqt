"""
Module: MD-GUI-046.001.M01 / MD-GUI-046.003.M02 — custom indicator GUI tests
Parent SRD: SRD-GUI-046.001–.005, SRD-EXE-022.014

Trigger popup rows for custom indicators, the Settings Indicators section, and the
on-screen message when a strategy cannot start.
"""
from __future__ import annotations

import json
import re
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
from tests.execution.plugin_helpers import SWING_PLUS, frames, swing_plus_source
from us_swing.core.indicator_plugins import REGISTRY, builtin_names, check_file, plugin_dir
from us_swing.gui import indicator_project as project
from us_swing.gui import indicator_python as pysetup
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


# ── Check and New indicator (SRD-GUI-046.006–.007) ──────────────────────────

def test_check_shows_last_20_values(qtbot: QtBot, swing_plus: Path) -> None:
    """UT-GUI-046.006.M02.T01: Check shows the last 20 values."""
    spec = REGISTRY.get("SWING_PLUS")
    assert spec is not None
    dialog = sec.CheckDialog(spec, ["AAPL"], lambda _symbol: frames(120))
    qtbot.addWidget(dialog)

    dialog.start()
    qtbot.waitUntil(lambda: dialog.table.rowCount() == 20 and dialog.run_btn.isEnabled())

    headers = [dialog.table.horizontalHeaderItem(c).text()
               for c in range(dialog.table.columnCount())]
    assert headers == ["time", "value", "Swing high", "Swing low"]
    assert dialog.table.item(19, 1).text() != ""


def test_new_project_files(tmp_path: Path) -> None:
    """UT-GUI-046.007.M03.T01: New project files."""
    folder = project.create_project(1, "MY_ST", root=tmp_path)

    names = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    assert {"my_st.py", "test_my_st.py", ".vscode/settings.json",
            ".vscode/launch.json", ".vscode/tasks.json"} <= names
    assert check_file(folder / "my_st.py", builtin_names=builtin_names(),
                      candle_probe=lambda: [("AAPL", frames(120))]).ok
    task = json.loads((folder / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    assert task["tasks"][0]["args"][-3:] == ["indicator", "check",
                                             "${workspaceFolder}/my_st.py"]
    with pytest.raises(FileExistsError):
        project.create_project(1, "MY_ST", root=tmp_path)


def test_project_has_ai_guide(tmp_path: Path) -> None:
    """UT-GUI-046.008.M03.T01: New project has an AI guide with the rules and check command."""
    folder = project.create_project(1, "VWAP_CROSS", root=tmp_path)

    guide = (folder / "CLAUDE.md").read_text(encoding="utf-8")

    assert guide.startswith("# VWAP_CROSS")
    assert "indicator check vwap_cross.py" in guide
    assert "SWING" in guide and "negative `shift`" in guide and "usswing.dev" in guide
    assert "USSWING_API.md" in guide
    assert str(project.sdk_dir()) in guide
    assert "{" not in guide.replace("```", "")


def test_project_dialog_open_or_create(qtbot: QtBot) -> None:
    """UT-GUI-046.009.M02.T01: New indicator lists projects to open and can create one."""
    made = project.create_project(1, "MY_ST")
    opener = sec.ProjectDialog(1)
    qtbot.addWidget(opener)
    assert [opener.projects.item(i).text() for i in range(opener.projects.count())] == ["MY_ST"]
    assert not opener.open_btn.isEnabled()

    opener.projects.setCurrentRow(0)
    opener.open_btn.click()

    assert opener.folder == made and opener.created is False
    maker = sec.ProjectDialog(1)
    qtbot.addWidget(maker)
    maker.name.setText("MY_ST")
    maker.name.returnPressed.emit()
    assert "already exists" in maker.error.text() and maker.folder is None
    maker.name.setText("new_one")
    maker.name.returnPressed.emit()
    assert maker.created is True and maker.folder is not None
    assert (maker.folder / "new_one.py").is_file()
    assert [p.name for p in project.list_projects(1)] == ["my_st", "new_one"]


def test_project_has_api_guide_and_help(tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.010.M03.T01: Project has the API guide (text + web page); Help opens it."""
    folder = project.create_project(1, "MY_ST", root=tmp_path)

    guide = (folder / "USSWING_API.md").read_text(encoding="utf-8")
    assert all(f"## {n}." in guide for n in range(1, 10))
    assert "indicator check my_st.py" in guide
    page = (folder / "USSWING_API.html").read_text(encoding="utf-8")
    assert page.count('class="copy"') == guide.count("```") // 2
    assert '<a class="l3" href="#number-label-default-minimum-maximum-whole-number-false">' in page
    assert '<h3 id="usswing-testing-run-indicator-class-candles-values-none" class="sig">' in page
    assert '<span class="kw">return</span>' in page
    for name in ("my_st.py", "test_my_st.py"):
        assert "—" not in (folder / name).read_text(encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(project.QDesktopServices, "openUrl",
                        lambda url: opened.append(url.toLocalFile()))
    shown = project.open_api_page(tmp_path)
    assert Path(opened[0]) == shown and shown.read_text(encoding="utf-8").startswith(
        "<!doctype html>")


def _recipes() -> list[str]:
    guide = (project.create_project(9, "RECIPES") / "USSWING_API.md").read_text(encoding="utf-8")
    section = guide.split("## 8.")[1].split("## 9.")[0]
    return re.findall(r"```python\n(.*?)```", section, re.S)


def test_guide_recipes_pass_the_check(tmp_path: Path) -> None:
    """UT-GUI-046.010.M03.T02: Every ready recipe in the guide passes the import check."""
    data = {tf: f.rename(columns={"ts": "datetime"}) for tf, f in frames(160).items()}
    recipes = _recipes()
    assert len(recipes) == 4
    for number, recipe in enumerate(recipes):
        body = "\n".join("        " + line for line in recipe.splitlines()
                         if not line.startswith("import "))
        source = ("import pandas as pd\nfrom usswing import Input, Number, USSwingIndicator\n\n"
                  "class Recipe(USSwingIndicator):\n"
                  f"    indicator_name = 'RECIPE_{number}'\n"
                  "    description = 'recipe'\n    version = '1.0'\n    output_type = 'value'\n"
                  "    parameters = [Number('Candles', default=20, minimum=2, maximum=50,"
                  " whole_number=True), Input('Timeframe', options=['3m'], default='3m')]\n\n"
                  f"    def calculate(self):\n{body}\n")
        path = tmp_path / f"recipe_{number}.py"
        path.write_text(source, encoding="utf-8")
        report = check_file(path, builtin_names=builtin_names(),
                            candle_probe=lambda: [("AAPL", data)])
        assert report.ok, (number, report.reasons)


def test_opening_old_project_adds_missing_files(tmp_path: Path) -> None:
    """UT-GUI-046.011.M03.T01: Opening an old project adds missing files, keeps the user's."""
    folder = tmp_path / "1" / "projects" / "old_one"
    (folder / ".vscode").mkdir(parents=True)
    code = "# my own code\n"
    (folder / "old_one.py").write_text(code, encoding="utf-8")
    (folder / ".vscode" / "settings.json").write_text('{"editor.fontSize": 15}',
                                                       encoding="utf-8")

    added = project.ensure_project_files(folder, root=tmp_path)

    assert set(added) == {".env", "CLAUDE.md", "USSWING_API.md", "USSWING_API.html",
                          ".vscode/tasks.json",
                          ".vscode/launch.json", ".vscode/extensions.json",
                          ".vscode/settings.json"}
    assert (folder / "old_one.py").read_text(encoding="utf-8") == code
    settings = json.loads((folder / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert settings["editor.fontSize"] == 15 and "python.envFile" in settings
    assert project.ensure_project_files(folder, root=tmp_path) == []


def test_project_recommends_extensions(tmp_path: Path) -> None:
    """UT-GUI-046.012.M03.T01: The project recommends the Python and Claude Code extensions."""
    folder = project.create_project(1, "MY_ST", root=tmp_path)

    data = json.loads((folder / ".vscode" / "extensions.json").read_text(encoding="utf-8"))

    assert data == {"recommendations": ["ms-python.python", "anthropic.claude-code"]}


def test_python_setup_makes_env_and_points_projects(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.013.M04.T01: Set up Python makes the env, installs, points projects at it."""
    folder = project.create_project(1, "MY_ST", root=tmp_path)
    monkeypatch.setattr(pysetup.shutil, "which",
                        lambda name: r"C:\Python311\python.exe" if name == "python" else None)
    calls: list[list[str]] = []

    def fake_run(args: list[str], _timeout: float) -> tuple[int, str]:
        calls.append(args)
        if "venv" in args:
            python = project.env_python(tmp_path)
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
        return 0, "311\n" if "-c" in args else ""

    steps: list[str] = []
    python = pysetup.setup_python(tmp_path, run=fake_run, step=steps.append)

    assert python == project.env_python(tmp_path)
    assert calls[1] == [r"C:\Python311\python.exe", "-m", "venv",
                        str(project.python_env_dir(tmp_path))]
    assert calls[2][-3:] == ["pandas", "numpy", "pytest"] and calls[2][0] == str(python)
    settings = json.loads((folder / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert settings[project.INTERPRETER_KEY] == str(python)
    assert len(steps) == 3 and pysetup.python_ready(tmp_path)


def test_python_setup_without_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.013.M04.T02: No Python on the PC gives a plain message with the link."""
    monkeypatch.setattr(pysetup.shutil, "which", lambda _name: None)
    calls: list[list[str]] = []

    with pytest.raises(pysetup.PythonSetupError, match="python.org"):
        pysetup.setup_python(tmp_path, run=lambda args, _t: (calls.append(args), (1, ""))[1])

    assert calls == []


def test_vs_code_not_found_opens_folder(tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-046.007.M03.T02: VS Code not found."""
    opened: list[str] = []
    monkeypatch.setattr(project.shutil, "which", lambda _name: None)
    monkeypatch.setattr(project.QDesktopServices, "openUrl",
                        lambda url: opened.append(url.toLocalFile()))

    assert project.open_project(tmp_path) is False
    assert Path(opened[0]) == tmp_path


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
