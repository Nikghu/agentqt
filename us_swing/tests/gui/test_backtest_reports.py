"""Tests for MD-GUI-031.055.M09 — gui/backtest_reports.py."""
from __future__ import annotations

import sys
import types
from datetime import date, datetime, timezone
from typing import Any

import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = object  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.backtest.results import RunRow  # noqa: E402
from us_swing.backtest.service import SavedReport  # noqa: E402
from us_swing.backtest.spec import Period, RunPlan, StrategySpec, UniverseSpec  # noqa: E402
from us_swing.gui.backtest_reports import ReportsView, plan_text  # noqa: E402


def saved_report(run_id: str = "r1", name: str = "IT run", net: float = -25.0) -> SavedReport:
    plan = RunPlan(name, Period(date(2026, 1, 2), date(2026, 10, 28)),
                   universe=UniverseSpec("sector", ("Information Technology",)),
                   strategies=(StrategySpec("ST_AUTO"),))
    run = RunRow(run_id, name, plan.to_json(), "done",
                 datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc), None, "", "my note")
    return SavedReport(run, plan, 103, net, net / 2000, -0.304)


class _FakeService:
    def __init__(self) -> None:
        self.saved = [saved_report(), saved_report("r2", "Other", 12.0)]
        self.calls: list[tuple[str, ...]] = []

    def saved_reports(self) -> list[SavedReport]:
        return self.saved

    def rename_run(self, run_id: str, name: str) -> None:
        self.calls.append(("rename", run_id, name))

    def set_note(self, run_id: str, note: str) -> None:
        self.calls.append(("note", run_id, note))

    def delete_run(self, run_id: str) -> None:
        self.calls.append(("delete", run_id))


@pytest.fixture()
def view(qtbot: Any) -> ReportsView:
    widget = ReportsView(_FakeService())  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.set_saved(widget._service.saved_reports())  # type: ignore[attr-defined]
    return widget


def test_table_and_details(view: ReportsView) -> None:
    """UT-GUI-031.055.M09.T01: Saved runs fill the table; the first run's details show."""
    assert view.table.rowCount() == 2
    assert view.table.item(0, 8).text() == "Information Technology"  # type: ignore[union-attr]
    assert view.table.item(0, 3).text() == "-1.2%"  # type: ignore[union-attr]
    assert view.table.item(0, 4).text() == "-30.4%"  # type: ignore[union-attr]
    assert view.name.text() == "IT run"
    assert view.note.toPlainText() == "my note"
    assert "Strategies: ST_AUTO 100%/100%" in view.facts.text()
    view.table.selectRow(1)
    assert view.name.text() == "Other"


def test_empty_list(view: ReportsView) -> None:
    """UT-GUI-031.055.M09.T02: No saved run disables the actions and says so."""
    view.set_saved([])

    assert not view.open_btn.isEnabled()
    assert not view.delete_btn.isEnabled()
    assert view.facts.text() == "Run a backtest to save a report"


def test_rename_note_open(view: ReportsView, qtbot: Any) -> None:
    """UT-GUI-031.055.M09.T03: Rename and Save note go to the service; Open sends the run."""
    service = view._service
    opened: list[SavedReport] = []
    view.open_requested.connect(opened.append)

    view.name.setText("New name")
    view.rename_btn.click()
    view.note.setPlainText("better")
    view.note_btn.click()
    view.open_btn.click()

    assert service.calls == [("rename", "r1", "New name"), ("note", "r1", "better")]  # type: ignore[attr-defined]
    assert opened[0].run.run_id == "r1"
    qtbot.waitUntil(lambda: not view._workers)


def test_delete_needs_confirm(view: ReportsView, monkeypatch: pytest.MonkeyPatch,
                              qtbot: Any) -> None:
    """UT-GUI-031.055.M09.T04: Delete does nothing when not confirmed, deletes when confirmed."""
    service = view._service
    answers = iter([False, True])
    monkeypatch.setattr(view, "confirm_delete", lambda _rep: next(answers))

    view.delete_btn.click()
    assert service.calls == []  # type: ignore[attr-defined]
    view.delete_btn.click()
    assert service.calls == [("delete", "r1")]  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: not view._workers)


def test_plan_text_names_mode() -> None:
    """UT-GUI-031.055.M09.T05: Plan facts list the names, capital and costs."""
    rep = saved_report()
    plan = RunPlan("x", rep.plan.period, universe=UniverseSpec("names", names=("AAPL", "MSFT")))

    text = plan_text(SavedReport(rep.run, plan, 0, 0.0, 0.0, 0.0))

    assert "Stocks: AAPL, MSFT" in text
    assert "Strategies: None" in text
    assert "Costs: $1 an order · 5 bps" in text
