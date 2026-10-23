"""
Module: MD-GUI-004.001.M01 / MD-GUI-004.001.M02 — tests
Parent SRD: SRD-GUI-004.010, SRD-GUI-004.011, SRD-GUI-004.012

Manual picks: stocks added to Trade Execution by hand. They persist per user,
sit at the top of Filtered Stocks, and feed the engine like screened stocks.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# execution_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.data.models import FilteredStockEntry  # noqa: E402
from us_swing.gui import manual_picks_store  # noqa: E402
from us_swing.gui.app_service import AppService  # noqa: E402
from us_swing.gui.execution_watchlist import MANUAL, group_entries  # noqa: E402
from us_swing.screener.manager import PresetManager  # noqa: E402
from us_swing.screener.preset import Preset, PresetType  # noqa: E402
from us_swing.screener.storage import ScreenerResultsStorage, ScreenerRunResult  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(manual_picks_store, "_STORE_FILE", tmp_path / "manual_picks.json")
    return tmp_path


def _svc(universe: list[str]) -> Any:
    fake = SimpleNamespace(
        _active_uid=1,
        _sp500=[SimpleNamespace(symbol=s) for s in universe],
        refreshes=0,
    )

    def _refresh() -> None:
        fake.refreshes += 1

    fake._refresh_after_pick_change = _refresh
    fake._cycle_symbols = set()
    fake._filtered_symbols = []
    fake.get_latest_screener_results = lambda: AppService.get_latest_screener_results(fake)  # type: ignore[arg-type]
    fake._manual_pick_entries = lambda: AppService._manual_pick_entries(fake)  # type: ignore[arg-type]
    return fake


def test_add_pick_persists_and_refreshes() -> None:
    """UT-GUI-004.001.M01.T11: a valid symbol is saved for the user and the list refreshes."""
    svc = _svc(["AAPL", "TSLA"])

    assert AppService.add_manual_pick(svc, " tsla ") is None

    assert manual_picks_store.load_manual_picks("1") == ["TSLA"]
    assert svc.refreshes == 1


@pytest.mark.parametrize(
    ("universe", "existing", "typed", "message"),
    [
        (["AAPL"], [], "XYZ", "XYZ is not in the stock universe"),
        (["AAPL"], ["AAPL"], "aapl", "AAPL is already in your picks"),
        ([], [], "AAPL", "The stock list is still loading — try again in a moment"),
        (["AAPL"], [], "  ", "Type a stock symbol first"),
    ],
)
def test_add_pick_refused(universe: list[str], existing: list[str], typed: str, message: str) -> None:
    """UT-GUI-004.001.M01.T12: unknown, duplicate, empty or too-early symbols are refused."""
    manual_picks_store.save_manual_picks("1", existing)
    svc = _svc(universe)

    assert AppService.add_manual_pick(svc, typed) == message

    assert manual_picks_store.load_manual_picks("1") == existing
    assert svc.refreshes == 0


def test_add_pick_accepts_ibkr_form() -> None:
    """UT-GUI-004.001.M01.T13: "BRK B" is stored in universe form "BRK.B"."""
    svc = _svc(["BRK.B"])

    assert AppService.add_manual_pick(svc, "brk b") is None

    assert manual_picks_store.load_manual_picks("1") == ["BRK.B"]


@pytest.mark.parametrize(("open_trades", "kept"), [(set(), ["TSLA"]), ({"AAPL"}, ["AAPL", "TSLA"])])
def test_remove_pick(open_trades: set[str], kept: list[str]) -> None:
    """UT-GUI-004.001.M01.T14: removing a pick saves, refreshes and stops the engine trading it.

    UT-GUI-004.001.M01.T20: a removed pick with an open trade stays on the engine list.
    """
    manual_picks_store.save_manual_picks("1", ["AAPL", "TSLA"])
    svc = _svc(["AAPL", "TSLA"])
    svc._cycle_symbols = open_trades
    svc._filtered_symbols = ["AAPL", "TSLA"]

    AppService.remove_manual_pick(svc, "AAPL")

    assert manual_picks_store.load_manual_picks("1") == ["TSLA"]
    assert svc.refreshes == 1
    assert svc._filtered_symbols == kept


def test_picks_lead_feed_and_win_over_screener(home: Path) -> None:
    """UT-GUI-004.001.M01.T15: picks come first, need no assigned users, and replace a screener row."""
    base = home / ".usswing" / "screener_results"
    PresetManager(base).create_preset(
        Preset(id="p1", name="Momentum", preset_type=PresetType.COMPOSITE,
               is_admin=True, assigned_to=["1"]),
        "1", is_admin_user=True,
    )
    ScreenerResultsStorage(base).save_result(
        ScreenerRunResult(
            preset_id="p1", run_timestamp="2026-10-22T14:00:00Z", execution_mode="scheduled",
            results={"AAPL": {"passed": True, "score": 0.9}, "MSFT": {"passed": True, "score": 0.8}},
        ),
        "p1",
    )
    manual_picks_store.save_manual_picks("1", ["TSLA", "MSFT"])

    entries = AppService.get_latest_screener_results(_svc([]))

    assert [(e.symbol, e.run_type) for e in entries] == [
        ("TSLA", "pick"), ("MSFT", "pick"), ("AAPL", "scheduled"),
    ]


def test_picks_without_screener_results() -> None:
    """UT-GUI-004.001.M01.T16: picks show even when no screener has ever run."""
    manual_picks_store.save_manual_picks("1", ["TSLA"])

    entries = AppService.get_latest_screener_results(_svc([]))

    assert [e.symbol for e in entries] == ["TSLA"]


def test_pick_change_skips_screener_notification() -> None:
    """UT-GUI-004.001.M01.T17: a pick change refreshes without the "screener approved" message."""
    seen: list[bool] = []
    fake = SimpleNamespace(_notify_screener_approved=True)
    fake.notify_screener_results_updated = lambda: seen.append(fake._notify_screener_approved)

    AppService._refresh_after_pick_change(fake)  # type: ignore[arg-type]

    assert seen == [False]
    assert fake._notify_screener_approved is True


def test_ledger_records_picks_apart() -> None:
    """UT-GUI-004.001.M01.T18: picks are recorded under "Manual pick", screened rows under their preset."""
    recorded: list[tuple[str, list[str]]] = []
    fake = SimpleNamespace(
        _ensure_lifecycle_service=lambda: True,
        _lifecycle_command=SimpleNamespace(
            on_screener_results=lambda r: recorded.append((r.preset_id, sorted(r.results)))
        ),
    )
    entries = [
        FilteredStockEntry("TSLA", 0.0, [], [], "—", "pick", ""),
        FilteredStockEntry("AAPL", 0.9, [], ["1"], "Momentum", "scheduled", "2026-10-22"),
    ]

    AppService._lifecycle_record_screener(fake, entries)  # type: ignore[arg-type]

    assert recorded == [("Momentum", ["AAPL"]), ("Manual pick", ["TSLA"])]


def test_picks_pinned_on_top() -> None:
    """UT-GUI-004.001.M01.T19: picks form the first group, above every screener group."""
    groups = group_entries([
        FilteredStockEntry("AAPL", 0.9, [], ["1"], "Momentum", "scheduled", "2026-10-22"),
        FilteredStockEntry("TSLA", 0.0, [], [], "—", "pick", ""),
        FilteredStockEntry("MSFT", 0.5, [], ["1"], "Momentum", "scheduled", "2026-10-22"),
    ])

    assert groups[0][0] == MANUAL
    assert [e.symbol for e in groups[0][1]] == ["TSLA"]
