"""Tests for MD-GUI-031.071.M10 — gui/backtest_setup.py and the C1 builder pages."""
from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import Qt

from us_swing.backtest.service import Estimate
from us_swing.gui.backtest_builder import SECTIONS, BacktestBuilder
from us_swing.gui.backtest_setup import BacktestSetupDialog, section_marks
from us_swing.gui.backtest_workspace import BacktestWorkspace
from tests.gui.test_backtest_workspace import _PRESETS, _RECORDS, _STRATEGIES
from tests.gui.test_backtest_workspace import workspace  # noqa: F401 — fixture


def _builder(qtbot: Any) -> BacktestBuilder:
    builder = BacktestBuilder()
    qtbot.addWidget(builder)
    builder.set_universe(_RECORDS)
    builder.set_presets(_PRESETS)
    builder.set_strategies(_STRATEGIES)
    return builder


def _est(missing: list[str], errors: list[str]) -> Estimate:
    return Estimate(["A"], missing, [], True, 0, 0, errors)


def test_pages_and_rows(qtbot: Any) -> None:
    """UT-GUI-031.072.M02.T01: Five pages; the Sectors row shows only in Sectors mode."""
    builder = _builder(qtbot)

    assert list(builder.pages) == [k for k, _ in SECTIONS]
    assert builder._sectors.isHidden()
    assert builder._sectors.property("row_label").isHidden()
    builder._mode.buttons[1].click()
    assert not builder._sectors.isHidden()


def test_load_plan_round_trip(qtbot: Any) -> None:
    """UT-GUI-031.074.M02.T01: A plan put back into the fields comes out the same."""
    builder = _builder(qtbot)
    builder._mode.buttons[1].click()
    builder._sectors.item(1).setCheckState(Qt.CheckState.Checked)  # type: ignore[union-attr]
    builder._preset.setCurrentIndex(1)
    builder._source.buttons[1].click()
    builder._strategies.item(1, 0).setCheckState(Qt.CheckState.Checked)  # type: ignore[union-attr]
    builder._capital.setValue(5000)
    plan = builder.plan()
    other = _builder(qtbot)

    other.load_plan(plan)

    assert other.plan() == plan


def test_section_marks() -> None:
    """UT-GUI-031.071.M10.T01: Missing candles mark Stocks; an error marks its section."""
    assert set(section_marks(None).values()) == {"✓"}
    marks = section_marks(_est(["AAPL"], ["Pick a screener preset", "Capital must be more than zero"]))

    assert (marks["stocks"], marks["screener"], marks["account"]) == ("!", "!", "!")
    assert (marks["run"], marks["strategies"]) == ("✓", "✓")


def test_menu_shows_values(qtbot: Any) -> None:
    """UT-GUI-031.071.M10.T02: Each menu item shows its value and mark."""
    builder = _builder(qtbot)
    dialog = BacktestSetupDialog(builder)
    qtbot.addWidget(dialog)

    dialog.set_check("7 missing 3m", _est(["X"], []), True)

    assert dialog.nav.count() == 5
    assert dialog._items["stocks"].name_lbl.text() == "Stocks   !"
    assert dialog._items["screener"].meta_lbl.text() == "Momentum · replay · All a day"
    builder._capital.setValue(2000)
    assert dialog._items["account"].meta_lbl.text().startswith("$2,000")


def test_cancel_restores_and_save_keeps(qtbot: Any) -> None:
    """UT-GUI-031.074.M10.T01: Cancel puts the old plan back; Save keeps the edits."""
    builder = _builder(qtbot)
    dialog = BacktestSetupDialog(builder)
    qtbot.addWidget(dialog)

    dialog.open_at("run")
    builder._name.setText("Changed")
    dialog.cancel_btn.click()
    assert builder.plan().name == "Backtest"
    assert not dialog.isVisible()

    dialog.open_at()
    builder._name.setText("Kept")
    dialog.save_btn.click()
    assert builder.plan().name == "Kept"


def test_plan_line_and_edit(workspace: BacktestWorkspace, qtbot: Any) -> None:  # noqa: F811
    """UT-GUI-031.070.M03.T01: No left builder; the plan line shows; Edit setup opens the window."""
    assert workspace.builder.isHidden()
    assert workspace.plan_fields.values["run"].text().startswith("Backtest · ")

    workspace.edit_btn.click()

    assert workspace.setup.isVisible()
    workspace.setup.reject()


def test_run_from_window(workspace: BacktestWorkspace, qtbot: Any) -> None:  # noqa: F811
    """UT-GUI-031.074.M03.T01: Run in the window closes it and starts the run."""
    workspace._start_estimate()
    qtbot.waitUntil(lambda: workspace._estimate is not None)
    workspace.setup.open_at()

    workspace.setup.run_btn.click()

    assert not workspace.setup.isVisible()
    assert workspace._runner is not None
    qtbot.waitUntil(lambda: workspace._runner is None)
    assert workspace.pills[0].property("state") == "complete"
    assert date(2026, 3, 3) in workspace._daily.days  # type: ignore[union-attr]
