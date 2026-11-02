"""Tests for MD-BKT-002.083.M15 — backtest/html_report.py and BacktestService.export_html."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from us_swing.backtest import html_report
from us_swing.backtest.steps import report
from us_swing.backtest.store import BacktestStore
from tests.backtest.test_report import _SECTORS, _log, _money, _trades
from tests.backtest.test_saved_reports import _saved_run
from tests.backtest.test_service import _service as _rsi_service


def _page(trades: pd.DataFrame | None = None, bench: bool = True) -> str:
    frame = _trades() if trades is None else trades
    days = pd.Series(range(4), index=list(_money()["date"]), dtype=float)
    rep = report.build_report("v", 1000.0, frame, _money(), _log(), _SECTORS,
                              benchmark=1000.0 + days * 5 if bench else None)
    return html_report.render("Run", "2026-11-02 10:00", [("Stocks", "S&P 500")], [rep])


def _section(page: str, title: str) -> str:
    """HTML from heading ``title`` up to the next heading."""
    start = page.index(f"<h3>{title}</h3>")
    end = page.find("<h3>", start + 1)
    return page[start:end if end > 0 else None]


def test_export_saved_run(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.083.M15.T01: A saved run becomes one offline HTML page with setup, chart and trades."""
    svc, results = _rsi_service(store, tmp_path)
    run_id = _saved_run(results, "Mine")
    path = tmp_path / "out.html"

    assert svc.export_html(run_id, path) == path

    page = path.read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE html>")
    assert "<h1>Mine</h1>" in page
    assert "Period" in page and "Daily loss stop" in page
    assert page.count("<svg") == 2
    for title in ("Edge per trade", "Luck check", "Trade quality", "Every trade, in exit order",
                  "Best trades", "Worst trades", "All trades", "All measures"):
        assert f"<h3>{title}</h3>" in page
    assert _section(page, "All trades").count("<tr>") == len(_trades()) + 1


def test_export_unknown_run(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.083.M15.T02: An unknown run id raises and writes no file."""
    svc, _results = _rsi_service(store, tmp_path)
    path = tmp_path / "out.html"

    with pytest.raises(ValueError, match="No saved run"):
        svc.export_html("nope", path)
    assert not path.exists()


def test_render_escapes_and_empty() -> None:
    """UT-BKT-002.083.M15.T03: Names are escaped; no variant and no trade say so."""
    page = html_report.render("<b>x</b>", "2026-11-02 10:00", [("Stocks", "A&B")], [])

    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x</b>" not in page
    assert "A&amp;B" in page
    assert "This run has no results" in page
    assert html_report.fmt(math.nan, "usd") == "—"
    assert html_report.fmt(-12.5, "usd") == "-$12.50"
    assert html_report.fmt(0.123, "pct") == "12.3%"
    assert html_report.fmt(575.0, "hours") == "24 d"


def test_trade_groups() -> None:
    """UT-BKT-002.083.M15.T04: Hold, exit and strategy tables count trades and add their P&L."""
    page = _page()

    hold = _section(page, "By hold time")
    assert ('Same day</td><td class="n">4</td><td class="n">50%</td>'
            '<td class="n">$0.00</td>') in hold
    exits = _section(page, "By exit")
    assert "Exit rule</td><td class=\"n\">2</td>" in exits
    assert "End time</td><td class=\"n\">2</td>" in exits
    assert "+$40.00" in exits and "-$40.00" in exits
    strategies = _section(page, "By strategy")
    assert "S1</td><td class=\"n\">3</td>" in strategies and "S2</td><td class=\"n\">1</td>" in strategies


def test_page_stays_offline() -> None:
    """UT-BKT-002.083.M15.T05: One inline script; no src, href, link or web address."""
    page = _page()

    assert page.count("<script>") == 1 and page.count("<script") == 1
    assert "src=" not in page and "href=" not in page and "<link" not in page
    assert "http" not in page.replace('xmlns="http://www.w3.org/2000/svg"', "")


def test_open_at_end_and_hold_days() -> None:
    """UT-BKT-002.083.M15.T06: A trade closed at test end is tagged and its hold is in days."""
    trades = _trades()
    trades.loc[3, "exit_reason"] = "end_of_test"
    trades.loc[3, "exit_ts"] = trades.loc[3, "entry_ts"] + pd.Timedelta(days=2)

    rows = _section(_page(trades), "All trades")

    assert rows.count('class="tag open">Open at end') == 1
    assert '<td class="n">2 d</td>' in rows


def test_no_trades_no_benchmark() -> None:
    """UT-BKT-002.083.M15.T07: No trades says so; a missing benchmark draws no line or legend."""
    page = _page(_trades().iloc[0:0], bench=False)

    assert "No trades" in page
    assert "Benchmark" not in page
    assert page.count("<polyline") == 1


def test_best_and_worst_with_few_trades() -> None:
    """UT-BKT-002.083.M15.T08: Best lists only winners and worst only losers."""
    page = _page()

    best, worst = _section(page, "Best trades"), _section(page, "Worst trades")
    assert best.count("<tr>") == 2 and "+$30.00" in best and "+$10.00" in best
    assert worst.count("<tr>") == 2 and worst.count("-$20.00") == 2


def test_dates_day_first() -> None:
    """UT-BKT-002.083.M15.T09: Trade dates show as DD-MM-YYYY and short dates as DD-MM."""
    page = _page()

    assert '<td class="n">06-03-2025</td>' in _section(page, "All trades")
    assert "03-03 → 03-03" in _section(page, "Best trades")
    assert "2025-03-06" not in page
