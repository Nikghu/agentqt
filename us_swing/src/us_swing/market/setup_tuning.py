"""
Module: MD-MKT-015.001.M01 — market/setup_tuning.py
Parent SRD: SRD-MKT-015.001
Also: SRD-MKT-015.003 (pick step), SRD-MKT-015.008 (verdict), SRD-MKT-015.009 (candidate
lesson), SRD-MKT-015.010 (report only), SRD-MKT-015.011 (default employee), SRD-MKT-015.012
(logs)

The setup tuning research skill. One ticket runs as a short chain of steps, one per desk
tick: the AI picks up to 3 variants of one desk setup or live strategy, code tests the
baseline and each variant, then the AI reads the table and writes a short verdict. Code
decides the gain, and the skill never changes a live setup or strategy.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_lessons import add_candidate
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.data.market_calendar import ET
from us_swing.market.setup_knobs import KNOBS, check_changes, knobs_text, side_of
from us_swing.market.setups import Bars
from us_swing.market.tuning_replay import Row, gain, load_bars, replay_setup, row_text, table_text
from us_swing.market.tuning_strategy import (
    check_strategy_changes,
    pick_stocks,
    run_strategy,
    stop_problem,
    strategy_knobs,
)

log = logging.getLogger(__name__)

KIND = "setup_tuning"
STEP_TOKENS = 3_000
_PICK_RULES = (
    "Rules: pick one target from the lists above, by its exact name. Give 1 to 3 variants; "
    "each changes 1 or 2 knobs to a value inside the knob's range. Pick values that test the "
    "ticket's goal. For a strategy that has no stock list, also give up to 30 S&P 500 "
    "symbols that suit it. Code runs every test; you never see or change live settings."
)
_VERDICT_RULES = (
    "Rules: in at most 4 short sentences say what the table shows, whether the done test is "
    "met, and which values (if any) the owner may want to try. Code has already decided the "
    "gain; do not change it. Never invent a number that is not in the table."
)


class Change(BaseModel):
    """One knob change in a variant."""

    model_config = ConfigDict(extra="forbid")

    knob: str = Field(min_length=1, max_length=40)
    value: float


class VariantAsk(BaseModel):
    """One variant: 1 or 2 knob changes."""

    model_config = ConfigDict(extra="forbid")

    changes: list[Change] = Field(min_length=1, max_length=2)


class TuningPlan(BaseModel):
    """The model's answer for the pick step."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1, max_length=60)
    variants: list[VariantAsk] = Field(min_length=1, max_length=3)
    stocks: list[str] = Field(default_factory=list, max_length=30)


class TuningVerdict(BaseModel):
    """The model's answer for the verdict step."""

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(min_length=10, max_length=600)


def _now() -> datetime:
    return datetime.now(ET)


def _live_strategies() -> list[dict[str, Any]]:
    from us_swing.core.backtest_bridge import load_strategies  # noqa: PLC0415 — heavy

    return load_strategies()


def _known_stocks() -> list[str]:
    from us_swing.core.backtest_bridge import load_universe  # noqa: PLC0415 — heavy

    return [r.symbol for r in load_universe()]


def _changes_text(changes: Mapping[str, float]) -> str:
    return ", ".join(f"{k} {v:g}" for k, v in changes.items())


def _failed(note: str, call: str) -> StepResult:
    return StepResult(note, call, "failed")


class SetupTuningSkill:
    """Works setup tuning tickets: pick variants, test them in code, write a verdict."""

    key = KIND
    needs: tuple[str, ...] = ()
    answer = TuningPlan
    kinds: tuple[str, ...] = (KIND,)
    step_tokens = STEP_TOKENS

    def __init__(
        self,
        clock: Callable[[], datetime] = _now,
        bars: Callable[[], Bars | None] = load_bars,
        strategies: Callable[[], list[dict[str, Any]]] = _live_strategies,
        known: Callable[[], list[str]] = _known_stocks,
        strategy_run: Callable[..., Row] = run_strategy,
    ) -> None:
        """Set the clock and data sources; injectable for tests."""
        self._clock = clock
        self._bars = bars
        self._strategies = strategies
        self._known = known
        self._strategy_run = strategy_run

    def facts(self, home: Path) -> Facts:
        """This employee works research tickets only, so events never wake it."""
        return Facts("", self._clock().date().isoformat(), False,
                     "works research tickets only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Nothing to do outside a research ticket."""
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        """Do the next step of ``ticket``: pick, one test run, or the verdict."""
        state: dict[str, Any] = json.loads(ticket.state or "{}")
        phase = state.get("phase", "pick")
        if phase == "pick":
            return self._pick(ctx, ticket)
        if phase == "run":
            return self._run(ticket, state)
        return self._verdict(ctx, ticket, state)

    # ── pick ──────────────────────────────────────────────────────────────

    def _testable(self) -> list[dict[str, Any]]:
        return [s for s in self._strategies() if not stop_problem(s)]

    def _pick_facts(self, ticket: Ticket) -> str:
        lines = [f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                 f"Done when: {ticket.done_test}", "",
                 "Desk setups and their knobs (name default (low to high)):", knobs_text(), "",
                 "Live strategies with a fixed stop and their knobs:"]
        testable = self._testable()
        for cfg in testable:
            knobs = ", ".join(f"{k.name} {k.default:g}" for k in strategy_knobs(cfg))
            lines.append(f"{cfg['name']}: entry '{cfg.get('entry_condition', '')}'; "
                         f"knobs {knobs} (each 0.5x to 1.5x)")
        if not testable:
            lines.append("(none)")
        return "\n".join([*lines, "", _PICK_RULES])

    def _target(self, name: str) -> tuple[str, str, dict[str, Any] | None] | None:
        wanted = name.strip().lower()
        setup = next((s for s in KNOBS if s.lower() == wanted), None)
        if setup:
            return setup, "setup", None
        cfg = next((s for s in self._strategies()
                    if str(s.get("name", "")).lower() == wanted), None)
        return (str(cfg["name"]), "strategy", cfg) if cfg else None

    def _pick(self, ctx: AgentContext, ticket: Ticket) -> StepResult:
        reply = ctx.ask(self._pick_facts(ticket), TuningPlan)
        if reply is None:
            return StepResult("", "pick", "go")
        found = self._target(reply.target)
        if found is None:
            return _failed(f"Target {reply.target} is not a desk setup or a live strategy",
                           "pick")
        target, kind, cfg = found
        stocks: list[str] = []
        if cfg is not None:
            problem = stop_problem(cfg)
            if problem:
                return _failed(f"Cannot test: {problem}", "pick")
            stocks = pick_stocks(cfg, reply.stocks, self._known())
            if not stocks:
                return _failed(f"Cannot test {target}: no S&P 500 stocks to run it on", "pick")
        variants = self._variants(reply.variants, target, cfg)
        if not variants:
            return _failed(f"No variant of {target} had a knob value inside its range", "pick")
        state = {"phase": "run", "target": target, "kind": kind,
                 "side": side_of(target) if kind == "setup" else str(
                     (cfg or {}).get("direction", "LONG")).lower(),
                 "variants": variants, "stocks": stocks, "rows": []}
        log.info("[Research] Ticket %d will test %d variant(s) of %s", ticket.id,
                 len(variants), target)
        listed = "; ".join(f"{v['label']} ({_changes_text(v['changes'])})" for v in variants)
        return StepResult(f"Picked {len(variants)} variant(s) for {target}: {listed}", "pick",
                          "go", state=state)

    @staticmethod
    def _variants(asks: Sequence[VariantAsk], target: str, cfg: dict[str, Any] | None
                  ) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        for ask in asks:
            changes = {c.knob: c.value for c in ask.changes}
            if len(changes) != len(ask.changes):
                continue
            kept = (check_strategy_changes(cfg, changes) if cfg is not None
                    else check_changes(target, changes))
            if kept and all(kept != v["changes"] for v in variants):
                variants.append({"label": f"v{len(variants) + 1}", "changes": kept})
        return variants

    # ── test runs ─────────────────────────────────────────────────────────

    def _run(self, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        entries = [{"label": "base", "changes": {}}, *state["variants"]]
        rows = [Row.from_dict(r) for r in state["rows"]]
        entry = entries[len(rows)]
        label, changes = str(entry["label"]), dict(entry["changes"])
        target = str(state["target"])
        call = f"run {label}"
        if state["kind"] == "setup":
            row = replay_setup(target, changes, label, self._bars())
            if row is None:
                return _failed("No S&P 500 daily candles in Backtest Data to test on", call)
        else:
            cfg = next((s for s in self._strategies() if s["name"] == target), None)
            if cfg is None:
                return _failed(f"Strategy {target} is no longer in the strategy list", call)
            try:
                row = self._strategy_run(cfg, changes, label, state["stocks"])
            except ValueError as exc:
                return _failed(f"Backtest of {target} could not run: {exc}", call)
        rows.append(row)
        done = len(rows) == len(entries)
        new_state = {**state, "rows": [r.to_dict() for r in rows],
                     "phase": "verdict" if done else "run"}
        log.info("[Research] Ticket %d %s %s: %s trades, %+.2fR", ticket.id, target, label,
                 f"{row.trades:,}", row.exp_r)
        return StepResult(row_text(row, rows[0]), call, "go", state=new_state)

    # ── verdict ───────────────────────────────────────────────────────────

    @staticmethod
    def _gain_line(best: Row | None, base: Row) -> str:
        if best is None:
            return "Gain: no (no variant beat today's values by 0.05R on 100 or more trades)"
        return (f"Gain: yes, {best.label} ({_changes_text(best.changes)}) "
                f"{best.exp_r - base.exp_r:+.2f}R on {best.trades:,} trades")

    def _verdict(self, ctx: AgentContext, ticket: Ticket, state: dict[str, Any]
                 ) -> StepResult:
        rows = [Row.from_dict(r) for r in state["rows"]]
        base, best = rows[0], gain(rows)
        gain_line = self._gain_line(best, base)
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                          f"Done when: {ticket.done_test}", "",
                          f"Results for {state['target']} over up to 5 years:",
                          table_text(rows), gain_line, "", _VERDICT_RULES])
        reply = ctx.ask(text, TuningVerdict)
        if reply is None:
            return StepResult("", "verdict", "go")
        if best is not None and state["kind"] == "setup":
            self._lesson(ctx.home, ticket, state, base, best)
        log.info("[Research] Ticket %d %s %s", ticket.id, state["target"],
                 f"found a gain: {best.label} {best.exp_r - base.exp_r:+.2f}R" if best
                 else "found no gain")
        return StepResult(f"Verdict: {reply.verdict.strip()}\n{gain_line}", "verdict", "done",
                          gain=best is not None)

    def _lesson(self, home: Path, ticket: Ticket, state: dict[str, Any], base: Row,
                best: Row) -> None:
        target, side = str(state["target"]), str(state["side"])
        text = (f"{target} {side}s with today's limits did worse than "
                f"{_changes_text(best.changes)} in the backtest "
                f"({base.exp_r:+.2f}R vs {best.exp_r:+.2f}R)")[:200]
        proof = [f"ticket {ticket.id}: {row_text(best, base)}; baseline {base.trades:,} "
                 f"trades {base.exp_r:+.2f}R"]
        try:
            add_candidate(home, text, {"setup": target, "side": side}, "worse", proof,
                          self._clock())
        except Exception:  # noqa: BLE001 — a lost lesson must not repeat the paid verdict
            log.warning("[Research] Ticket %d could not save its lesson", ticket.id)
