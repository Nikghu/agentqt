"""
Module: MD-BKT-002.001.M01 — backtest/spec.py
Parent SRD: SRD-BKT-002.001

Run plan: the frozen, versioned input of a backtest run, saved as JSON with
every run. List values expand into a grid of variants (SRD-BKT-002.003).
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

SCHEMA = 1
MAX_VARIANTS = 64
UNIVERSE_MODES = ("sp500", "sector", "names")
WHEN_FULL = ("first_signal", "highest_score")


def _floats(value: Any, default: tuple[float, ...]) -> tuple[float, ...]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return tuple(float(v) for v in value)
    return (float(value),)


def _one_or_list(values: tuple[float, ...]) -> float | list[float]:
    return values[0] if len(values) == 1 else list(values)


def _strs(value: Any) -> tuple[str, ...]:
    return tuple(str(v) for v in value or ())


@dataclass(frozen=True)
class Period:
    """First and last session of the run."""

    start: date
    end: date


@dataclass(frozen=True)
class UniverseSpec:
    """Which stocks: all S&P 500, some sectors or a name list, then add/remove."""

    mode: str = "sp500"
    sectors: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    add: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScreenerSpec:
    """Screener preset replayed in Step 1; ``top_n`` 0 means all passing stocks."""

    preset_id: str = ""
    top_n: int = 0
    ai_ranking: bool = False


@dataclass(frozen=True)
class StrategySpec:
    """A live strategy and its money split; lists expand into variants."""

    id: str
    allocation_pct: tuple[float, ...] = (100.0,)
    per_trade_pct: tuple[float, ...] = (100.0,)


@dataclass(frozen=True)
class AccountSpec:
    """The one shared account (D1)."""

    capital: tuple[float, ...] = (10_000.0,)
    grow_with_pnl: bool = False
    max_daily_loss_pct: float = 2.0
    when_full: str = "first_signal"


@dataclass(frozen=True)
class CostSpec:
    """Commission per order in dollars and slippage in basis points."""

    per_order: float = 1.0
    slippage_bps: float = 5.0


@dataclass(frozen=True)
class Variant:
    """One point of the variant grid: capital plus (id, allocation %, per-trade %)."""

    capital: float
    strategies: tuple[tuple[str, float, float], ...]


@dataclass(frozen=True)
class RunPlan:
    """Full backtest input (Engine_plan §4)."""

    name: str
    period: Period
    universe: UniverseSpec = field(default_factory=UniverseSpec)
    screener: ScreenerSpec = field(default_factory=ScreenerSpec)
    strategies: tuple[StrategySpec, ...] = ()
    account: AccountSpec = field(default_factory=AccountSpec)
    costs: CostSpec = field(default_factory=CostSpec)
    schema: int = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON form; single list values are written as numbers."""
        u, s, a, c = self.universe, self.screener, self.account, self.costs
        return {
            "schema": self.schema,
            "name": self.name,
            "period": {"from": self.period.start.isoformat(),
                       "to": self.period.end.isoformat()},
            "universe": {"mode": u.mode, "sectors": list(u.sectors), "names": list(u.names),
                         "add": list(u.add), "remove": list(u.remove)},
            "screener": {"preset_id": s.preset_id, "top_n": s.top_n,
                         "ai_ranking": s.ai_ranking},
            "strategies": [
                {"id": st.id, "allocation_pct": _one_or_list(st.allocation_pct),
                 "per_trade_pct": _one_or_list(st.per_trade_pct)}
                for st in self.strategies
            ],
            "account": {"capital": _one_or_list(a.capital), "grow_with_pnl": a.grow_with_pnl,
                        "max_daily_loss_pct": a.max_daily_loss_pct, "when_full": a.when_full},
            "costs": {"per_order": c.per_order, "slippage_bps": c.slippage_bps},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunPlan:
        """Build a plan from its JSON form; unknown keys are ignored.

        Raises:
            KeyError, TypeError, ValueError: when ``period`` is missing or malformed.
        """
        period = data["period"]
        u = data.get("universe") or {}
        s = data.get("screener") or {}
        a = data.get("account") or {}
        c = data.get("costs") or {}
        account, costs = AccountSpec(), CostSpec()
        return cls(
            schema=int(data.get("schema", SCHEMA)),
            name=str(data.get("name", "")),
            period=Period(date.fromisoformat(period["from"]), date.fromisoformat(period["to"])),
            universe=UniverseSpec(
                mode=str(u.get("mode", "sp500")), sectors=_strs(u.get("sectors")),
                names=_strs(u.get("names")), add=_strs(u.get("add")),
                remove=_strs(u.get("remove")),
            ),
            screener=ScreenerSpec(
                preset_id=str(s.get("preset_id", "")), top_n=int(s.get("top_n", 0)),
                ai_ranking=bool(s.get("ai_ranking", False)),
            ),
            strategies=tuple(
                StrategySpec(
                    id=str(st["id"]),
                    allocation_pct=_floats(st.get("allocation_pct"), (100.0,)),
                    per_trade_pct=_floats(st.get("per_trade_pct"), (100.0,)),
                )
                for st in data.get("strategies") or ()
            ),
            account=AccountSpec(
                capital=_floats(a.get("capital"), account.capital),
                grow_with_pnl=bool(a.get("grow_with_pnl", account.grow_with_pnl)),
                max_daily_loss_pct=float(a.get("max_daily_loss_pct",
                                               account.max_daily_loss_pct)),
                when_full=str(a.get("when_full", account.when_full)),
            ),
            costs=CostSpec(
                per_order=float(c.get("per_order", costs.per_order)),
                slippage_bps=float(c.get("slippage_bps", costs.slippage_bps)),
            ),
        )

    def to_json(self) -> str:
        """Return the plan as indented JSON text."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> RunPlan:
        """Parse a plan from JSON text."""
        return cls.from_dict(json.loads(text))

    def variant_count(self) -> int:
        """Number of variants the list values expand into."""
        count = len(self.account.capital)
        for st in self.strategies:
            count *= len(st.allocation_pct) * len(st.per_trade_pct)
        return count

    def variants(self) -> list[Variant]:
        """Expand capital × each strategy's allocation × per-trade lists (SRD-BKT-002.003)."""
        per_strategy = [
            [(st.id, alloc, per) for alloc in st.allocation_pct for per in st.per_trade_pct]
            for st in self.strategies
        ]
        return [
            Variant(capital, tuple(combo))
            for capital in self.account.capital
            for combo in itertools.product(*per_strategy)
        ]

    def validate(self) -> list[str]:
        """Return plain error messages; an empty list means the plan is valid."""
        errors: list[str] = []
        u, a = self.universe, self.account
        if self.schema != SCHEMA:
            errors.append(f"Plan version {self.schema} is not supported")
        if self.period.start > self.period.end:
            errors.append("Start date is after the end date")
        if u.mode not in UNIVERSE_MODES:
            errors.append(f"Unknown stock list type: {u.mode}")
        if u.mode == "sector" and not u.sectors:
            errors.append("Pick at least one sector")
        if u.mode == "names" and not u.names:
            errors.append("Type at least one stock name")
        if not self.screener.preset_id:
            errors.append("Pick a screener preset")
        if self.screener.top_n < 0:
            errors.append("Stocks per day cannot be negative")
        if not a.capital or any(v <= 0 for v in a.capital):
            errors.append("Capital must be more than zero")
        for st in self.strategies:
            if any(not 0 < v <= 100 for v in st.allocation_pct + st.per_trade_pct):
                errors.append(f"Strategy {st.id}: percentages must be between 0 and 100")
        if a.max_daily_loss_pct < 0:
            errors.append("Daily loss stop cannot be negative")
        if a.when_full not in WHEN_FULL:
            errors.append(f"Unknown rule when money is short: {a.when_full}")
        if self.costs.per_order < 0 or self.costs.slippage_bps < 0:
            errors.append("Costs cannot be negative")
        if self.variant_count() > MAX_VARIANTS:
            errors.append(
                f"{self.variant_count()} variants is more than the limit of {MAX_VARIANTS}"
            )
        return errors
