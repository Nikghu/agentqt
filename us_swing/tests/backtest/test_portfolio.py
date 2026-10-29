"""Tests for MD-BKT-002.030.M12 — backtest/steps/portfolio.py and results.save_variant."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.backtest.results import ResultsStore
from us_swing.backtest.spec import AccountSpec, CostSpec, Period, RunPlan, ScreenerSpec, StrategySpec
from us_swing.backtest.steps import portfolio
from us_swing.backtest.steps.stocks import StepRefused
from us_swing.backtest.store import BacktestStore
from tests.backtest.conftest import LATE

D1, D2, D3 = date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 5)
ET = "America/New_York"


def _bars(day: date, changes: dict[str, tuple[float, float, float, float]] | None = None,
          price: float = 100.0) -> pd.DataFrame:
    """130 flat 3m bars at ``price``; ``changes`` maps bar start HH:MM to (o, h, l, c)."""
    starts = pd.date_range(f"{day} 09:30", periods=130, freq="3min", tz=ET)
    rows = []
    for ts in starts:
        o, h, lo, c = (changes or {}).get(ts.strftime("%H:%M"), (price,) * 4)
        rows.append((ts.tz_convert("UTC"), o, h, lo, c, 1000.0))
    return pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])


def _at(day: date, hhmm: str) -> pd.Timestamp:
    """Bar close time ``hhmm`` (US/Eastern) as UTC."""
    return pd.Timestamp(f"{day} {hhmm}", tz=ET).tz_convert("UTC")


def _sig(strategy: str, symbol: str, kind: str, day: date, start: str, end: str) -> dict[str, Any]:
    return {"strategy": strategy, "symbol": symbol, "kind": kind, "start": _at(day, start),
            "end": _at(day, end), "close_at_start": 100.0, "values": "{}", "pnl": False}


def _strategy(name: str = "S1", **kw: Any) -> dict[str, Any]:
    return {"name": name, "end_time": "15:30", "direction": "LONG", "trade_type": "Intraday",
            "stoploss_enabled": False, "stoploss_type": "fixed", "stoploss_value": 1.0,
            "target_enabled": False, "target_type": "fixed", "target_value": 2.0,
            "rex_count": 0, **kw}


def _daily(rows: list[tuple[date, str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["date", "symbol", "score"])
    frame["rank"] = frame.groupby("date")["score"].rank(ascending=False, method="first")
    return frame.astype({"rank": int})


def _run(tmp_path: Path, bars: dict[str, list[pd.DataFrame]], signals: list[dict[str, Any]],
         daily: pd.DataFrame, strategies: list[tuple[dict[str, Any], float, float]],
         capital: float = 1000.0, days: tuple[date, ...] = (D1, D2), **account: Any
         ) -> portfolio.VariantResult:
    store = BacktestStore(tmp_path / "store")
    for sym, frames in bars.items():
        store.save(sym, "3m", pd.concat(frames, ignore_index=True), LATE)
    costs = account.pop("costs", CostSpec(per_order=0.0, slippage_bps=0.0))
    plan = RunPlan(
        name="t", period=Period(days[0], days[-1]), screener=ScreenerSpec(preset_id="p"),
        strategies=tuple(StrategySpec(cfg["name"], (alloc,), (per,))
                         for cfg, alloc, per in strategies),
        account=AccountSpec(capital=(capital,), **{"max_daily_loss_pct": 0.0, **account}),
        costs=costs,
    )
    frame = pd.DataFrame(signals, columns=["strategy", "symbol", "kind", "start", "end",
                                           "close_at_start", "values", "pnl"])
    (result,) = portfolio.run_portfolio(plan, [cfg for cfg, _a, _p in strategies], daily,
                                        list(days), frame, store)
    return result


def _decisions(res: portfolio.VariantResult) -> list[tuple[str, str]]:
    return list(zip(res.day_log["symbol"], res.day_log["decision"]))


def test_entry_only_from_yesterdays_list(tmp_path: Path) -> None:
    """UT-BKT-002.030.M12.T01: Day 2 trades only the stock picked at day 1's close."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)], "MSFT": [_bars(D2)]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00"),
                _sig("S1", "MSFT", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0), (D3, "MSFT", 1.0)]), [(_strategy(), 50, 100)])

    assert list(res.trades["symbol"]) == ["AAPL"]


@pytest.mark.parametrize(("rule", "winner"), [("first_signal", "AAPL"), ("highest_score", "MSFT")])
def test_first_signal_or_highest_score(tmp_path: Path, rule: str, winner: str) -> None:
    """UT-BKT-002.030.M12.T02: When money frees up, the rule picks between two waiting stocks."""
    res = _run(tmp_path, {s: [_bars(D2)] for s in ("TSLA", "AAPL", "MSFT")},
               [_sig("S1", "TSLA", "entry", D2, "09:33", "09:33"),
                _sig("S1", "TSLA", "exit", D2, "09:57", "09:57"),
                _sig("S1", "AAPL", "entry", D2, "09:42", "10:30"),
                _sig("S1", "MSFT", "entry", D2, "09:51", "10:30")],
               _daily([(D2, "TSLA", 0.9), (D2, "AAPL", 0.5), (D2, "MSFT", 0.8)]),
               [(_strategy(), 100, 100)], when_full=rule)

    assert list(res.trades["symbol"])[:2] == ["TSLA", winner]


def test_per_trade_sizing(tmp_path: Path) -> None:
    """UT-BKT-002.031.M12.T01: Shares = floor(capital × alloc × per-trade ÷ fill)."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)]}, [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]), [(_strategy(), 50, 50)], capital=10_000)

    assert list(res.trades["qty"]) == [25]


def test_too_expensive(tmp_path: Path) -> None:
    """UT-BKT-002.031.M12.T02: Less than one share is not traded and is logged."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)]}, [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]), [(_strategy(), 50, 100)], capital=100)

    assert res.trades.empty
    assert _decisions(res) == [("AAPL", "too_expensive")]


def test_strategy_limit(tmp_path: Path) -> None:
    """UT-BKT-002.032.M12.T01: The second stock is blocked once the strategy limit is used."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)], "MSFT": [_bars(D2)]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00"),
                _sig("S1", "MSFT", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 0.9), (D2, "MSFT", 0.5)]), [(_strategy(), 50, 100)])

    assert list(res.trades["symbol"]) == ["AAPL"]
    assert ("MSFT", "strategy_limit") in _decisions(res)


def test_margin_across_two_strategies(tmp_path: Path) -> None:
    """UT-BKT-002.032.M12.T02: The second strategy's order is cut to the margin left."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)], "MSFT": [_bars(D2)]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00"),
                _sig("S2", "MSFT", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 0.9), (D2, "MSFT", 0.5)]),
               [(_strategy("S1"), 60, 100), (_strategy("S2"), 60, 100)])

    assert dict(zip(res.trades["symbol"], res.trades["qty"])) == {"AAPL": 6, "MSFT": 4}


def test_next_open_fill_with_costs(tmp_path: Path) -> None:
    """UT-BKT-002.033.M12.T01: Fills at the next open with slippage; two commissions."""
    bars = _bars(D2, {"10:00": (101, 101, 101, 101), "10:30": (102, 102, 102, 102)})
    res = _run(tmp_path, {"AAPL": [bars]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00"),
                _sig("S1", "AAPL", "exit", D2, "10:30", "10:30")],
               _daily([(D2, "AAPL", 1.0)]), [(_strategy(), 100, 100)], capital=10_000,
               costs=CostSpec(per_order=1.0, slippage_bps=10.0))
    trade = res.trades.iloc[0]

    assert trade.entry_px == pytest.approx(101 * 1.001)
    assert trade.exit_px == pytest.approx(102 * 0.999)
    assert trade.net_pnl == pytest.approx((102 * 0.999 - 101 * 1.001) * trade.qty - 2)
    assert trade.entry_ts == _at(D2, "10:00")
    assert trade.exit_reason == "strategy"


def test_rex_limit_resets_each_day(tmp_path: Path) -> None:
    """UT-BKT-002.034.M12.T01: Rex 0 = one entry per stock per day; a new day allows one more."""
    sigs = []
    for day in (D2, D3):
        sigs += [_sig("S1", "AAPL", "entry", day, "10:00", "10:03"),
                 _sig("S1", "AAPL", "exit", day, "10:30", "10:30"),
                 _sig("S1", "AAPL", "entry", day, "11:00", "11:03")]
    res = _run(tmp_path, {"AAPL": [_bars(D2), _bars(D3)]}, sigs,
               _daily([(D2, "AAPL", 1.0), (D3, "AAPL", 1.0)]), [(_strategy(), 100, 100)],
               days=(D1, D2, D3))

    assert len(res.trades) == 2
    assert _decisions(res).count(("AAPL", "rex_limit")) == 2


def test_stop_wins_in_one_bar(tmp_path: Path) -> None:
    """UT-BKT-002.035.M12.T01: Stop and target in one bar count as the stop."""
    bars = _bars(D2, {"10:06": (100, 102, 98, 100)})
    res = _run(tmp_path, {"AAPL": [bars]}, [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]),
               [(_strategy(stoploss_enabled=True, target_enabled=True, target_value=1.0),
                 100, 100)])
    trade = res.trades.iloc[0]

    assert (trade.exit_reason, trade.exit_px) == ("stop", pytest.approx(99.0))


def test_gap_through_stop(tmp_path: Path) -> None:
    """UT-BKT-002.035.M12.T02: A swing trade gapping under its stop exits at the open."""
    res = _run(tmp_path, {"AAPL": [_bars(D2), _bars(D3, price=95.0)]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]),
               [(_strategy(trade_type="Swing", stoploss_enabled=True, stoploss_value=2.0),
                 100, 100)], days=(D1, D2, D3))
    trade = res.trades.iloc[0]

    assert (trade.exit_reason, trade.exit_px) == ("stop", 95.0)


def test_short_target(tmp_path: Path) -> None:
    """UT-BKT-002.036.M12.T01: A SHORT trade's target is below the fill and wins money."""
    bars = _bars(D2, {"10:30": (99, 99, 97.5, 98)})
    res = _run(tmp_path, {"AAPL": [bars]}, [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]),
               [(_strategy(direction="SHORT", target_enabled=True), 100, 100)])
    trade = res.trades.iloc[0]

    assert (trade.direction, trade.exit_reason) == ("SHORT", "target")
    assert trade.exit_px == pytest.approx(98.0)
    assert trade.net_pnl == pytest.approx(2.0 * trade.qty)


def test_trailing_refused(tmp_path: Path) -> None:
    """UT-BKT-002.036.M12.T02: A trailing stop stops the run with a plain message."""
    with pytest.raises(StepRefused, match="trailing stop"):
        _run(tmp_path, {"AAPL": [_bars(D2)]}, [], _daily([(D2, "AAPL", 1.0)]),
             [(_strategy(stoploss_enabled=True, stoploss_type="trailing"), 100, 100)])


def test_intraday_end_time_and_swing_overnight(tmp_path: Path) -> None:
    """UT-BKT-002.037.M12.T01: Intraday closes at the 15:30 open; Swing stays to the end."""
    sig = [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")]
    daily = _daily([(D2, "AAPL", 1.0), (D3, "AAPL", 1.0)])
    bars = {"AAPL": [_bars(D2), _bars(D3)]}
    intraday = _run(tmp_path / "a", bars, sig, daily, [(_strategy(), 100, 100)],
                    days=(D1, D2, D3)).trades.iloc[0]
    swing = _run(tmp_path / "b", bars, sig, daily, [(_strategy(trade_type="Swing"), 100, 100)],
                 days=(D1, D2, D3)).trades.iloc[0]

    assert (intraday.exit_reason, intraday.exit_ts) == ("end_time", _at(D2, "15:30"))
    assert (swing.exit_reason, swing.exit_ts) == ("end_of_test", _at(D3, "16:00"))


def test_daily_loss_stop(tmp_path: Path) -> None:
    """UT-BKT-002.038.M12.T01: After a 1 % day loss, later entries that day are blocked."""
    aapl = _bars(D2, {f"{h:02d}:{m:02d}": (90, 90, 90, 90)
                      for h in range(10, 16) for m in range(0, 60, 3)
                      if (h, m) >= (10, 3) and (h, m) < (15, 30)})
    res = _run(tmp_path, {"AAPL": [aapl], "MSFT": [_bars(D2)]},
               [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00"),
                _sig("S1", "MSFT", "entry", D2, "11:00", "11:00")],
               _daily([(D2, "AAPL", 0.9), (D2, "MSFT", 0.5)]), [(_strategy(), 50, 100)],
               max_daily_loss_pct=1.0)

    assert list(res.trades["symbol"]) == ["AAPL"]
    assert ("MSFT", "daily_loss_stop") in _decisions(res)


def test_variant_rows_saved(tmp_path: Path) -> None:
    """UT-BKT-002.039.M04.T01: A variant's trades, day log and money rows are saved."""
    res = _run(tmp_path, {"AAPL": [_bars(D2)]}, [_sig("S1", "AAPL", "entry", D2, "10:00", "10:00")],
               _daily([(D2, "AAPL", 1.0)]), [(_strategy(), 100, 100)])
    store = ResultsStore(tmp_path / "results.db")
    run_id = store.start_run(RunPlan(name="t", period=Period(D1, D2)), pd.Timestamp.now(tz="UTC"))

    vid = store.save_variant(run_id, 0, res.variant, res.trades, res.day_log, res.money)

    assert len(store.read_table("trades", vid)) == 1
    assert len(store.read_table("day_log", vid)) == 1
    assert len(store.read_table("money_daily", vid)) == 2  # one row per session


def test_first_session_trades_its_list() -> None:
    """UT-BKT-002.051.M12.T01: The first session gets its own list; days without a list get none."""
    picks = portfolio.picks_by_day(_daily([(D1, "AAPL", 1.0)]), [D1, D2], 0)

    assert picks == {D1: {"AAPL": (1.0, 1)}, D2: {}}
