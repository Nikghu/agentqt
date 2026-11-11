"""Tests for MD-GUI-038.001.M01 — app feeds for the desk watchers (gui/app_service.py)."""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from us_swing.gui import app_service
from us_swing.gui.app_service import AppService, live_symbols, trade_rows


def test_desk_stocks_in_feed() -> None:
    """UT-GUI-038.001.M01.T01: The app's symbols come first, then new desk ones, no repeats."""
    assert live_symbols(["AAA", "BBB", "CCC"], ["BBB", "DDD", "EEE", "SPY"]) == [
        "AAA", "BBB", "CCC", "DDD", "EEE", "SPY"]


def test_feed_cap() -> None:
    """UT-GUI-038.001.M01.T02: 98 app stocks and 5 desk stocks give 100; app stocks kept."""
    held = [f"H{i:02d}" for i in range(98)]
    got = live_symbols(held, ["D1", "D2", "D3", "D4", "D5"])
    assert len(got) == 100 and got[:98] == held and got[98:] == ["D1", "D2"]
    many = [f"S{i:03d}" for i in range(120)]
    assert live_symbols(many, [], held=["ZZZ"])[0] == "ZZZ"


def _snap(**kw: Any) -> SimpleNamespace:
    base = {"symbol": "AAA", "direction": "LONG", "entry_price": 50.0, "hard_stop_loss": 47.0,
            "effective_stop": None, "target_price": 56.0, "strategy_id": "s1"}
    return SimpleNamespace(**(base | kw))


def test_trade_rows() -> None:
    """UT-GUI-038.002.M01.T01: Side, entry, the stop in force and the target."""
    rows = trade_rows([_snap(effective_stop=48.5),
                       _snap(symbol="BBB", direction="SHORT", hard_stop_loss=32.0,
                             target_price=None, strategy_id=None)])
    assert [(r.symbol, r.side, r.entry, r.stop, r.target, r.strategy) for r in rows] == [
        ("AAA", "long", 50.0, 48.5, 56.0, "s1"), ("BBB", "short", 50.0, 32.0, None, "")]


def test_publish_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
                       tmp_path: Path) -> None:
    """UT-GUI-038.002.M01.T02: A failing write is logged and never raises; an unchanged list
    starts no second write."""
    def broken(*_a: object) -> None:
        raise OSError("disk is read-only")

    monkeypatch.setattr(app_service, "write_open_trades", broken)
    with caplog.at_level(logging.WARNING):
        app_service._write_trades(trade_rows([_snap()]))
    assert "[Desk] Could not share the open trades with the AI desk" in caplog.text
    started: list[object] = []

    class _Thread:
        def __init__(self, **kw: object) -> None:
            started.append(kw["args"])

        def start(self) -> None:
            return None

    monkeypatch.setattr(app_service.threading, "Thread", _Thread)
    fake = SimpleNamespace(_tc_query=SimpleNamespace(open_cycles=lambda: [_snap()]))
    AppService._publish_open_trades(fake)  # type: ignore[arg-type]
    AppService._publish_open_trades(fake)  # type: ignore[arg-type]
    assert len(started) == 1


def test_live_feed_log(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-038.003.M01.T01: Two new desk stocks in the feed are logged."""
    started: list[list[str]] = []

    class _Worker:
        def __init__(self, symbols: list[str], **_kw: object) -> None:
            started.append(symbols)
            self.candle_closed = SimpleNamespace(connect=lambda _f: None)

        def start(self) -> None:
            return None

    import us_swing.execution.live_bar_worker as lbw

    monkeypatch.setattr(lbw, "LiveBarWorker", _Worker)
    fake = SimpleNamespace(
        _filtered_symbols=["AAA"], _system_cfg=SimpleNamespace(
            ibkr_host="h", ibkr_port=1, ibkr_live_client_id=2),
        _stop_live_bar_worker=lambda: None, _desk_live_symbols=lambda: ["AAA", "PIK", "SPY"],
        live_bar_data_updated=None, _live_bar_worker=None, _cycle_symbols=frozenset())
    with caplog.at_level(logging.INFO):
        AppService._start_live_bar_worker(fake)  # type: ignore[arg-type]
    assert started == [["AAA", "PIK", "SPY"]]
    assert "[Live] Added 2 desk stock(s) to the live feed" in caplog.text
