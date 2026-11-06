"""Tests for MD-EXE-021.002.M01 (execution/desk_signals.py), MD-EXE-021.001.M02 (AppService
AI Desk picks) and MD-EXE-021.005.M03 (broker adapter levels)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from tests.execution.test_broker_adapter import _make_db, _StubConfig, _StubCycles
from tests.execution.test_strategy_engine import _Cfg, _make_engine
from us_swing.broker.sim import ImmediateFillModel, SimBroker
from us_swing.core import desk_contract
from us_swing.core.desk_trades import TradePick, pick_expiry, record_trade_decision
from us_swing.data.market_calendar import ET
from us_swing.execution.broker_adapter import BrokerAdapter
from us_swing.execution.desk_signals import (
    AI_DESK_STRATEGY,
    AI_DESK_TYPE,
    build_desk_signal,
    desk_signal_close,
)
from us_swing.execution.order_ingestion import OrderIngestion
from us_swing.execution.pending_signal_store import PendingSignalStore
from us_swing.execution.strategy_engine import Action, TradeSignal
from us_swing.execution.strategy_engine._engine import _EXTERNAL_TYPES
from us_swing.gui.app_service import AppService
from us_swing.gui.strategy_store import StrategyConfig

FRI = "2026-11-06"
MON_10 = datetime(2026, 11, 9, 10, 0, tzinfo=ET)


def _pick(side: str = "long", symbol: str = "AAPL") -> TradePick:
    stop, target = (97.4, 108.8) if side == "long" else (105.0, 93.6)
    return TradePick(FRI, side, symbol, 1, "breakout", 101.2, stop, target, pick_expiry(FRI))


def _cfg(**kw: Any) -> StrategyConfig:
    base = StrategyConfig(name=AI_DESK_STRATEGY, mode="paper", capital_max=10, start_time="09:30",
                          end_time="16:00", start_date="", end_date="", days=[],
                          entry_condition="", exit_condition="", strategy_type=AI_DESK_TYPE,
                          trade_type="Positional")
    return replace(base, **kw)


def _svc(qtbot: QtBot, cfg: StrategyConfig | None = None, history: tuple[Any, ...] = ()
         ) -> SimpleNamespace:
    store = PendingSignalStore()
    svc = SimpleNamespace(_pending_store=store, _active_uid=1,
                          _tc_query=SimpleNamespace(history=lambda **k: history))
    svc._ai_desk_config = lambda: cfg if cfg is not None else _cfg()
    svc.effective_capital = lambda: 100_000.0
    svc.desk_pick_qty = lambda p: AppService.desk_pick_qty(svc, p)  # type: ignore[arg-type]
    svc.send_desk_pick = lambda p: AppService.send_desk_pick(svc, p)  # type: ignore[arg-type]
    return svc


# ── strategy row (SRD-EXE-021.001) ──────────────────────────────────────────

def test_ai_desk_row_made() -> None:
    """UT-EXE-021.001.M02.T01: a missing AI Desk row is added, stopped and fed from outside."""
    saved: list[list[StrategyConfig]] = []
    AppService._ensure_ai_desk_strategy(lambda: [], saved.append)
    [[row]] = saved
    assert (row.name, row.strategy_type, row.trade_type, row.auto_trade, row.run_state) == (
        AI_DESK_STRATEGY, AI_DESK_TYPE, "Positional", False, "STOPPED")


def test_existing_row_kept() -> None:
    """UT-EXE-021.001.M02.T02: an existing AI Desk row is never changed."""
    saved: list[list[StrategyConfig]] = []
    AppService._ensure_ai_desk_strategy(lambda: [_cfg(capital_max=25, mode="live")], saved.append)
    assert saved == []


def test_ai_desk_never_evaluated(qtbot: QtBot) -> None:
    """UT-EXE-021.001.M04.T01: a RUNNING AI Desk strategy is never evaluated by the engine."""
    import pandas as pd

    from us_swing.data.models import OHLCVBar

    @dataclass
    class _DeskCfg(_Cfg):
        strategy_type: str = AI_DESK_TYPE

    assert AI_DESK_TYPE in _EXTERNAL_TYPES
    engine = _make_engine([_Cfg(name="normal"), _DeskCfg(name=AI_DESK_STRATEGY)])
    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()
    calls: list[str] = []

    async def _fake(ctx: Any, symbol: Any, candles: Any, bar: Any) -> None:
        calls.append(ctx.name)

    assert engine.router is not None
    engine.router.evaluate = _fake  # type: ignore[method-assign]
    bar = OHLCVBar(symbol="AAPL", datetime=datetime(2026, 5, 19, 10, 0, tzinfo=ET), open=149.0,
                   high=151.0, low=148.0, close=150.0, volume=1_000_000, timeframe="3m")
    df = pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0],
                       "volume": [1_000_000]})
    engine._bar_provider = lambda sym, tf: bar  # type: ignore[assignment]
    engine._candles_provider = lambda sym: {"3m": df}  # type: ignore[assignment]
    engine.on_candle_closed("AAPL")
    time.sleep(0.25)
    assert calls == ["normal"]
    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)


# ── signal (SRD-EXE-021.002) ────────────────────────────────────────────────

def test_long_signal_fields() -> None:
    """UT-EXE-021.002.M01.T01: a long pick gives one ENTRY signal for AI Desk."""
    sig = build_desk_signal(_pick(), 45, 1)
    assert (sig.action, sig.strategy_id, sig.direction, sig.entry_price, sig.stop_loss,
            sig.target, sig.qty_recommended, sig.signal_id) == (
        Action.ENTRY, AI_DESK_STRATEGY, "LONG", 101.2, 97.4, 108.8, 45,
        "desk:2026-11-06:long:AAPL")


def test_short_signal() -> None:
    """UT-EXE-021.002.M01.T02: a short pick gives a SHORT signal."""
    sig = build_desk_signal(_pick("short"), 5, 1)
    assert sig.direction == "SHORT" and ":short:" in sig.signal_id


def test_send_adds_one_signal(qtbot: QtBot) -> None:
    """UT-EXE-021.002.M02.T01: sending a pick adds one pending signal."""
    svc = _svc(qtbot)
    assert svc.send_desk_pick(_pick()) == (98, "")
    assert len(svc._pending_store.list()) == 1


def test_same_pick_twice(qtbot: QtBot) -> None:
    """UT-EXE-021.002.M02.T02: the same pick sent twice leaves one signal."""
    svc = _svc(qtbot)
    svc.send_desk_pick(_pick())
    svc.send_desk_pick(_pick())
    assert len(svc._pending_store.list()) == 1


def test_unknown_side_refused(qtbot: QtBot) -> None:
    """UT-EXE-021.002.M02.T03: a pick with an unknown side is refused."""
    svc = _svc(qtbot)
    qty, why = svc.send_desk_pick(replace(_pick(), side="flat"))
    assert qty == 0 and why
    assert svc._pending_store.list() == ()


# ── quantity (SRD-EXE-021.003) ──────────────────────────────────────────────

def test_capital_max_quantity(qtbot: QtBot) -> None:
    """UT-EXE-021.003.M02.T01: quantity comes from the AI Desk Capital Max."""
    assert _svc(qtbot).desk_pick_qty(_pick()) == 98


def test_quantity_zero(qtbot: QtBot, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-021.003.M02.T02: quantity 0 adds no signal and warns once."""
    svc = _svc(qtbot, _cfg(capital_max=0))
    with caplog.at_level(logging.WARNING):
        qty, why = svc.send_desk_pick(_pick())
    assert (qty, bool(why)) == (0, True)
    assert svc._pending_store.list() == ()
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


# ── close sweep (SRD-EXE-021.004) ───────────────────────────────────────────

def test_close_time_from_id() -> None:
    """UT-EXE-021.004.M01.T01: a desk id closes at 16:00 ET of its trading day."""
    assert desk_signal_close("desk:2026-11-06:long:AAPL") == datetime(2026, 11, 9, 16, 0, tzinfo=ET)
    assert desk_signal_close("sig-123") is None


def test_close_sweep(qtbot: QtBot) -> None:
    """UT-EXE-021.004.M02.T01: desk signals go at the close; engine signals stay."""
    svc = _svc(qtbot)
    svc.send_desk_pick(_pick())
    svc._pending_store.add(TradeSignal(action=Action.ENTRY, symbol="MSFT", strategy_id="S1",
                                       signal_id="engine-1"))
    AppService._dismiss_closed_desk_signals(svc, MON_10)  # type: ignore[arg-type]
    assert len(svc._pending_store.list()) == 2
    AppService._dismiss_closed_desk_signals(  # type: ignore[arg-type]
        svc, datetime(2026, 11, 9, 16, 0, tzinfo=ET))
    assert [s.signal_id for s in svc._pending_store.list()] == ["engine-1"]


def test_bad_desk_id_kept(qtbot: QtBot) -> None:
    """UT-EXE-021.004.M02.T02: an unreadable desk id is kept and an empty store is fine."""
    svc = _svc(qtbot)
    AppService._dismiss_closed_desk_signals(svc, MON_10)  # type: ignore[arg-type]
    svc._pending_store.add(TradeSignal(action=Action.ENTRY, symbol="X", strategy_id=AI_DESK_STRATEGY,
                                       signal_id="desk:bad"))
    AppService._dismiss_closed_desk_signals(svc, MON_10)  # type: ignore[arg-type]
    assert [s.signal_id for s in svc._pending_store.list()] == ["desk:bad"]


# ── broker adapter levels (SRD-EXE-021.005) ─────────────────────────────────

@dataclass
class _DeskStubConfig(_StubConfig):
    strategy_type: str = AI_DESK_TYPE


def _context(config: Any) -> Any:
    ingestion = OrderIngestion(ledger=_make_db(), fill_sink=lambda _f: None,
                               reject_sink=lambda _r: None, cycles=_StubCycles())
    adapter = BrokerAdapter(broker=SimBroker(ImmediateFillModel(), scheduler=lambda cb: None),
                            ingestion=ingestion, config_provider=lambda _sid: config,
                            user_id_provider=lambda: 1,
                            session_date_provider=lambda: "2026-11-09")
    sig = TradeSignal(action=Action.ENTRY, symbol="AAPL", strategy_id="X", entry_price=100.0,
                      stop_loss=97.4, target=108.8)
    from us_swing.broker.broker import OrderSide
    return adapter._build_context(sig, 10, OrderSide.BUY, True)


def test_signal_stop_and_target() -> None:
    """UT-EXE-021.005.M03.T01: an AI Desk entry keeps the signal's stop and target."""
    ctx = _context(_DeskStubConfig())
    assert (ctx.hard_stop_loss, ctx.target_price) == (97.4, 108.8)


def test_other_strategies_unchanged() -> None:
    """UT-EXE-021.005.M03.T02: other strategies still take levels from config percentages."""
    ctx = _context(_StubConfig())
    assert (ctx.hard_stop_loss, ctx.target_price) == pytest.approx((95.0, 110.0))


# ── restart (SRD-EXE-021.006) ───────────────────────────────────────────────

def _approve(home: Path) -> None:
    record_trade_decision(home, _pick(), "approve", 98, datetime(2026, 11, 7, 12, 0, tzinfo=ET))


def test_resend_on_start(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-021.006.M02.T01: an approved pick for today is sent again after a restart."""
    monkeypatch.setattr(desk_contract, "desk_home", lambda: tmp_path)
    _approve(tmp_path)
    svc = _svc(qtbot)
    AppService._resend_desk_picks(svc, MON_10)  # type: ignore[arg-type]
    assert [s.signal_id for s in svc._pending_store.list()] == ["desk:2026-11-06:long:AAPL"]


def test_no_resend(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-021.006.M02.T02: no re-send with a cycle today, after the close, or when pending."""
    monkeypatch.setattr(desk_contract, "desk_home", lambda: tmp_path)
    _approve(tmp_path)
    with_cycle = _svc(qtbot, history=(object(),))
    AppService._resend_desk_picks(with_cycle, MON_10)  # type: ignore[arg-type]
    assert with_cycle._pending_store.list() == ()
    late = _svc(qtbot)
    AppService._resend_desk_picks(late, datetime(2026, 11, 9, 16, 5, tzinfo=ET))  # type: ignore[arg-type]
    assert late._pending_store.list() == ()
    pending = _svc(qtbot)
    pending.send_desk_pick(_pick())
    pending.send_desk_pick = lambda p: pytest.fail("sent twice")
    AppService._resend_desk_picks(pending, MON_10)  # type: ignore[arg-type]


# ── logs (SRD-EXE-021.007) ──────────────────────────────────────────────────

def test_logs(qtbot: QtBot, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-021.007.M02.T01: send, refuse and sweep log lines carry the [AI Desk] prefix."""
    svc = _svc(qtbot)
    with caplog.at_level(logging.INFO, logger="us_swing.gui.app_service"):
        svc.send_desk_pick(_pick())
        AppService._dismiss_closed_desk_signals(  # type: ignore[arg-type]
            svc, datetime(2026, 11, 9, 16, 0, tzinfo=ET))
        svc._ai_desk_config = lambda: _cfg(capital_max=0)
        svc.send_desk_pick(_pick("short", "MSFT"))
    msgs = [r.getMessage() for r in caplog.records]
    assert "[AI Desk] Sent long AAPL to Execution, 98 share(s)" in msgs
    assert "[AI Desk] long AAPL was not executed by the close and was removed" in msgs
    assert "[AI Desk] short MSFT was not sent because the quantity is 0" in msgs
