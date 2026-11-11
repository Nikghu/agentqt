"""
Module: MD-MKT-015.005.M04 — market/tuning_strategy.py
Parent SRD: SRD-MKT-015.005

Strategy side of setup tuning: the numbers a test may change, renamed copies with the
changes, and a run on the backtest engine whose strategy loader gives only the copy, so
nothing is saved as a Backtest run and the live strategy list is never written.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any, Protocol

import pandas as pd

from us_swing.market.setup_knobs import Knob
from us_swing.market.tuning_replay import Row, row_from_r

YEARS = 5
MAX_STOCKS = 30
LOW, HIGH = 0.5, 1.5
_NUMBER = re.compile(r"(?<![A-Za-z_\d.:])\d+(?:\.\d+)?(?![\d.:A-Za-z_])")
_TEXT_FIELDS = (("entry", "entry_condition"), ("exit", "exit_condition"))

Strategy = Mapping[str, Any]
Portfolio = Callable[..., Sequence[Any]]


class Service(Protocol):
    """The parts of the backtest service a tuning run uses."""

    def estimate(self, plan: Any, user_id: str) -> Any: ...

    def run_stocks(self, plan: Any, user_id: str, *, workers: int = ...,
                   record: bool = ...) -> Any: ...

    def run_signals(self, plan: Any, daily: Any, *, workers: int = ...,
                    record: bool = ...) -> pd.DataFrame: ...


ServiceMaker = Callable[[Callable[[], list[dict[str, Any]]]], Service]


def _knob(name: str, text: str) -> Knob:
    value = float(text)
    whole = "." not in text
    return Knob(name, value, value * LOW, value * HIGH, whole)


def strategy_knobs(cfg: Strategy) -> list[Knob]:
    """Target, stop and each number in the entry and exit text, with a 0.5x to 1.5x range."""
    knobs: list[Knob] = []
    for field_name in ("target_value", "stoploss_value"):
        value = float(cfg.get(field_name) or 0)
        if value > 0:
            knobs.append(Knob(field_name, value, value * LOW, value * HIGH))
    for prefix, field_name in _TEXT_FIELDS:
        for i, found in enumerate(_NUMBER.finditer(str(cfg.get(field_name) or "")), start=1):
            knobs.append(_knob(f"{prefix}#{i}", found.group()))
    return knobs


def check_strategy_changes(cfg: Strategy, changes: Mapping[str, float]) -> dict[str, float]:
    """Keep the changes that name a knob of ``cfg`` and sit inside its range."""
    known = {k.name: k for k in strategy_knobs(cfg)}
    kept: dict[str, float] = {}
    for name, value in changes.items():
        knob = known.get(name)
        if knob is None:
            continue
        value = float(round(value)) if knob.whole else float(value)
        if knob.low <= value <= knob.high and value != knob.default:
            kept[name] = value
    return kept


def _swap(text: str, index: int, value: float) -> str:
    spans = list(_NUMBER.finditer(text))
    found = spans[index - 1]
    new = (str(int(round(value))) if "." not in found.group()
           else f"{value:.6f}".rstrip("0").rstrip("."))
    return text[:found.start()] + new + text[found.end():]


def apply_changes(cfg: Strategy, changes: Mapping[str, float], label: str) -> dict[str, Any]:
    """A renamed copy of ``cfg`` with ``changes``; ``cfg`` itself is left as it is."""
    copy = dict(cfg)
    copy["name"] = f"{cfg['name']} (tune {label})"
    fields = dict(_TEXT_FIELDS)
    for name, value in changes.items():
        prefix, _, number = name.partition("#")
        if number:
            copy[fields[prefix]] = _swap(str(copy[fields[prefix]]), int(number), value)
        else:
            copy[name] = value
    return copy


def stop_problem(cfg: Strategy) -> str:
    """Why the strategy cannot be tested in R, or an empty text when it can."""
    if not cfg.get("stoploss_enabled"):
        return f"strategy {cfg.get('name')} has no stop, so its trades have no R"
    if cfg.get("stoploss_type") != "fixed":
        return f"strategy {cfg.get('name')} needs a fixed stop to be tested"
    if float(cfg.get("stoploss_value") or 0) <= 0:
        return f"strategy {cfg.get('name')} has a stop of zero"
    return ""


def pick_stocks(cfg: Strategy, asked: Sequence[str], known: Sequence[str]) -> list[str]:
    """The strategy's own include list, else up to 30 of the asked stocks that are known."""
    include = [str(s).strip().upper() for s in cfg.get("symbols_include") or [] if str(s).strip()]
    if cfg.get("symbol_mode", "all") != "all" and include:
        return include[:MAX_STOCKS]
    names = set(known)
    picked: list[str] = []
    for sym in (str(s).strip().upper() for s in asked):
        if sym in names and sym not in picked:
            picked.append(sym)
    return picked[:MAX_STOCKS]


def trade_r(trades: pd.DataFrame, stop_pct: float) -> list[float]:
    """R of each trade: net P&L over the money the stop risks."""
    if trades.empty:
        return []
    rs: list[float] = []
    for qty, price, pnl in zip(trades["qty"].astype(float), trades["entry_px"].astype(float),
                               trades["net_pnl"].astype(float), strict=True):
        risk = qty * price * stop_pct / 100
        if risk > 0:
            rs.append(round(pnl / risk, 2))
    return rs


def _years_back(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def _default_service(loader: Callable[[], list[dict[str, Any]]]) -> Service:
    from us_swing.backtest.cache import StepCache  # noqa: PLC0415 — heavy, strategy runs only
    from us_swing.backtest.results import ResultsStore  # noqa: PLC0415
    from us_swing.backtest.service import BacktestService  # noqa: PLC0415
    from us_swing.backtest.store import BacktestStore  # noqa: PLC0415
    from us_swing.core.backtest_bridge import load_preset_dict, load_universe  # noqa: PLC0415

    return BacktestService(BacktestStore(), StepCache(), ResultsStore(), load_universe,
                           load_preset_dict, loader)


def _default_portfolio(plan: Any, strategies: Sequence[Mapping[str, Any]], daily: pd.DataFrame,
                       days: Sequence[date], signals: pd.DataFrame) -> Sequence[Any]:
    from us_swing.backtest.steps.portfolio import run_portfolio  # noqa: PLC0415
    from us_swing.backtest.store import BacktestStore  # noqa: PLC0415

    return run_portfolio(plan, strategies, daily, days, signals, BacktestStore())


def _default_user() -> str:
    from us_swing.core.backtest_bridge import default_user_id  # noqa: PLC0415

    return default_user_id()


def _plan(name: str, strategy: str, stocks: Sequence[str], today: date) -> Any:
    from us_swing.backtest.spec import (  # noqa: PLC0415
        Period,
        RunPlan,
        ScreenerSpec,
        StrategySpec,
        UniverseSpec,
    )

    return RunPlan(name, Period(_years_back(today, YEARS), today),
                   UniverseSpec(mode="names", names=tuple(stocks)), ScreenerSpec(skip=True),
                   (StrategySpec(strategy),))


def run_strategy(cfg: Strategy, changes: Mapping[str, float], label: str,
                 stocks: Sequence[str], *, today: date | None = None,
                 service: ServiceMaker = _default_service,
                 portfolio: Portfolio = _default_portfolio,
                 user: Callable[[], str] = _default_user) -> Row:
    """Run one copy of ``cfg`` with ``changes`` over up to 5 years and return its row.

    Raises:
        ValueError: The stop is not fixed, the data check fails or no candles are held.
    """
    problem = stop_problem(cfg)
    if problem:
        raise ValueError(problem)
    copy = apply_changes(cfg, changes, label)
    svc = service(lambda: [dict(copy)])
    user_id = user()
    plan = _plan(f"Tune {label}", copy["name"], stocks, today or date.today())
    est = svc.estimate(plan, user_id)
    if est.errors:
        raise ValueError("; ".join(est.errors))
    if est.data_span is None:
        raise ValueError("no candles are held for these stocks")
    first, last = est.data_span
    plan = replace(plan, period=replace(plan.period, start=max(plan.period.start, first),
                                        end=min(plan.period.end, last)))
    daily = svc.run_stocks(plan, user_id, workers=0, record=False)
    found = svc.run_signals(plan, daily, workers=0, record=False)
    results = portfolio(plan, [copy], daily.frame, daily.days, found)
    trades = results[0].trades if results else pd.DataFrame()
    return row_from_r(label, changes, trade_r(trades, float(copy["stoploss_value"])))
