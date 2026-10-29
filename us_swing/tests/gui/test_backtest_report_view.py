"""Tests for MD-GUI-031.040.M04 — gui/backtest_report_view.py."""
from __future__ import annotations

import math
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = object  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.backtest.steps.report import Report, build_report  # noqa: E402
from us_swing.gui.backtest_report_view import ReportView, fmt, skips_text  # noqa: E402

_DAYS = [date(2026, 3, 2), date(2026, 3, 3), date(2026, 4, 1)]


def _report(label: str = "$1,000", pnl: tuple[float, ...] = (30.0, -10.0)) -> Report:
    ts = pd.Timestamp("2026-03-02 15:00", tz="UTC")
    trades = pd.DataFrame({
        "strategy": ["S1", "S2"][:len(pnl)], "symbol": ["AAPL", "MSFT"][:len(pnl)],
        "direction": "LONG", "entry_ts": [ts] * len(pnl), "entry_px": 10.0, "qty": 1,
        "exit_ts": [ts + pd.Timedelta(hours=1)] * len(pnl), "exit_px": 10.0,
        "exit_reason": "strategy", "costs": 0.0, "net_pnl": list(pnl), "mae": 0.0, "mfe": 0.0,
        "score": 1.0, "rank": 1,
    })
    money = pd.DataFrame({"date": _DAYS, "start_capital": 1000.0, "deployed": 0.0,
                          "margin_min": 0.0, "margin_close": 0.0, "open_value": 0.0,
                          "equity": [1030.0, 1020.0, 1000.0 + sum(pnl)]})
    log = pd.DataFrame({"ts": [ts] * 3, "symbol": "AAPL", "strategy": "S1",
                        "decision": ["entered", "entered", "strategy_limit"],
                        "margin_available": 0.0, "strategy_deployed": 0.0})
    bench = pd.Series([1005.0, 1010.0, 1012.0], index=_DAYS)
    return build_report(label, 1000.0, trades, money, log, {"AAPL": "Information Technology"},
                        bench)


@pytest.fixture()
def view(qtbot: Any) -> ReportView:
    widget = ReportView()
    qtbot.addWidget(widget)
    return widget


def test_fmt_kinds() -> None:
    """UT-GUI-031.040.M04.T01: Stat values show as $, %, ratio, days or a dash."""
    assert fmt(-12.5, "usd") == "-$12.50"
    assert fmt(0.125, "pct") == "12.5%"
    assert fmt(1.234, "ratio") == "1.23"
    assert fmt(3.0, "days") == "3 days"
    assert fmt(math.nan, "ratio") == "—"


def test_kpi_row_and_stats(view: ReportView) -> None:
    """UT-GUI-031.040.M04.T02: KPI row and all-stats table show the selected variant."""
    view.set_reports([_report()])

    assert view.kpi_values["Net P&L"].text() == "$20.00"
    assert view.kpi_values["Win rate"].text() == "50.0%"
    assert view.stats_table.rowCount() == len(_report().stats)
    assert view.skips_label.text() == "Entries taken 2 · skipped: strategy limit 1"


def test_empty_view(view: ReportView) -> None:
    """UT-GUI-031.040.M04.T03: No report shows dashes and no export."""
    view.set_reports([])

    assert view.kpi_values["Trades"].text() == "—"
    assert not view.export_btn.isEnabled()


def test_chart_gets_benchmark(view: ReportView, qtbot: Any) -> None:
    """UT-GUI-031.041.M04.T01: The chart gets equity, drawdown and benchmark per day."""
    view.set_reports([_report()])
    view.resize(1000, 900)
    view.show()
    qtbot.waitExposed(view)

    assert list(view.chart.daily["benchmark"]) == [1005.0, 1010.0, 1012.0]
    assert not view.chart.grab().isNull()


def test_month_heat_map(view: ReportView) -> None:
    """UT-GUI-031.042.M04.T01: One row per year; March and April filled and coloured."""
    view.set_reports([_report()])
    march, april = view.month_table.item(0, 3), view.month_table.item(0, 4)

    assert view.month_table.rowCount() == 1
    assert (march.text(), april.text()) == ("20", "0")  # type: ignore[union-attr]
    assert march.background().color().alpha() > 0  # type: ignore[union-attr]
    assert view.month_table.item(0, 13).text() == "20"  # type: ignore[union-attr]


def test_breakdown_group_picker(view: ReportView) -> None:
    """UT-GUI-031.043.M04.T01: Changing Group by refills the breakdown table."""
    view.set_reports([_report()])
    assert view.group_table.item(0, 0).text() == "S1"  # type: ignore[union-attr]

    view.group_pick.setCurrentIndex(view.group_pick.findData("sector"))

    groups = {view.group_table.item(r, 0).text()  # type: ignore[union-attr]
              for r in range(view.group_table.rowCount())}
    assert groups == {"Information Technology", "Unknown"}


def test_single_variant_hides_compare(view: ReportView) -> None:
    """UT-GUI-031.044.M04.T01: One variant hides the picker and the compare table."""
    view.set_reports([_report()])

    assert view.variant.isHidden()
    assert view.compare_table.isHidden()


def test_compare_two_variants(view: ReportView) -> None:
    """UT-GUI-031.044.M04.T02: Two variants fill the compare table, one row each."""
    view.set_reports([_report("A"), _report("B", (5.0,))])

    assert view.compare_table.rowCount() == 2
    assert view.compare_table.item(1, 0).text() == "B"  # type: ignore[union-attr]
    view.variant.setCurrentIndex(1)
    assert view.kpi_values["Trades"].text() == "1"


def test_export_csv(view: ReportView, tmp_path: Path) -> None:
    """UT-GUI-031.045.M04.T01: Export writes the stats and trades CSV files."""
    view.set_reports([_report("$1,000 · S1 100%/50%")])

    paths = view.export_to(tmp_path)

    assert [p.name for p in paths] == ["1_000_S1_100_50_stats.csv", "1_000_S1_100_50_trades.csv"]
    assert len(pd.read_csv(paths[1])) == 2
    assert "Sharpe" in set(pd.read_csv(paths[0])["measure"])


def test_export_error_is_logged(view: ReportView, monkeypatch: pytest.MonkeyPatch,
                                caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-031.045.M04.T02: A failed export logs a warning instead of crashing."""
    view.set_reports([_report()])
    monkeypatch.setattr("us_swing.gui.backtest_report_view.QFileDialog.getExistingDirectory",
                        lambda *_a: "C:/missing/folder/x")

    view.export_btn.click()

    assert "Could not save the report" in caplog.text


def test_skips_text_without_skips() -> None:
    """UT-GUI-031.040.M04.T04: Only entries gives no "skipped" part."""
    assert skips_text(pd.DataFrame({"decision": ["entered"], "count": [3]})) == "Entries taken 3"
