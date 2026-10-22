"""Module: MD-SCR-002.001.M04 — screeners/indicator.py
Parent SRD: SRD-SCR-002.003, SRD-SCR-015.010
"""
from __future__ import annotations

import logging
from typing import Any

from us_swing.core.indicator_rules import (
    BarArrays,
    Rule,
    RuleContext,
    evaluate_rule,
    rule_label,
    rules_from_config,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions (SRD-SCR-012.004)
# ---------------------------------------------------------------------------

class BenchmarkDataUnavailableError(Exception):
    def __init__(self, symbol: str) -> None:
        super().__init__(
            f"Benchmark data for '{symbol}' is not available in price_1d."
            " Run bootstrap_benchmark() first."
        )
        self.symbol = symbol


class InsufficientUniverseDataError(Exception):
    pass


def _compute_rs_ranks(
    symbols: list[str],
    bars: dict[str, list[Any]],
    lookback: int = 252,
) -> dict[str, float]:
    """Compute 252-day return percentile rank for each symbol (SRD-SCR-012.002/005).

    Uses pandas vectorised rank; symbols with insufficient data receive 50.0.
    """
    import pandas as pd  # lazy import — pandas is a project dependency

    returns: dict[str, float] = {}
    for sym in symbols:
        sym_bars = bars.get(sym, [])
        if len(sym_bars) >= lookback + 1:
            c_now = sym_bars[-1].close
            c_past = sym_bars[-lookback - 1].close
            if c_past > 0:
                returns[sym] = (c_now - c_past) / c_past

    if not returns:
        return {sym: 50.0 for sym in symbols}

    ranked = (pd.Series(returns).rank(pct=True) * 100.0).to_dict()
    return {sym: ranked.get(sym, 50.0) for sym in symbols}


# ---------------------------------------------------------------------------
# IndicatorScreener
# ---------------------------------------------------------------------------

class IndicatorScreener:
    """MD-SCR-002.001.M04 — rule-list indicator screener plugin.

    Evaluates the enabled rules from the config (SRD-SCR-015.010). A symbol
    passes only if every enabled rule passes; score = fraction that pass.
    """

    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, tuple[bool, float]]:
        rules, ctx = self._prepare(symbols, bars, config, strict=True)
        results: dict[str, tuple[bool, float]] = {}

        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if not sym_bars:
                continue
            if not rules:
                results[sym] = (True, 1.0)
                continue
            arrays = BarArrays.from_bars(sym_bars)
            passed = sum(evaluate_rule(r, sym, arrays, ctx)[0] for r in rules)
            results[sym] = (passed == len(rules), float(passed / len(rules)))

        return results

    def screen_detailed(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Return each enabled rule's last value per symbol, keyed by rule label.

        Values are rounded floats (``None`` when not computable) so the GUI can
        show them in the Details column (SRD-SCR-015.016).
        """
        rules, ctx = self._prepare(symbols, bars, config, strict=False)
        out: dict[str, dict[str, Any]] = {}

        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if not sym_bars:
                continue
            arrays = BarArrays.from_bars(sym_bars)
            det: dict[str, Any] = {}
            for rule in rules:
                _, value = evaluate_rule(rule, sym, arrays, ctx)
                det[rule_label(rule)] = None if value is None else round(value, 2)
            out[sym] = det
        return out

    def batch_features(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
    ) -> dict[str, dict[str, Any]]:
        return {}

    @staticmethod
    def _prepare(
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
        *,
        strict: bool,
    ) -> tuple[list[Rule], RuleContext]:
        """Read enabled rules and build the shared context (RS ranks, market caps).

        RS ranks are computed once per run, only when an RS rule is enabled
        (SRD-SCR-015.011). ``strict`` raises when the benchmark is missing.
        """
        rules = [r for r in rules_from_config(config) if r.enabled]
        market_caps: dict[str, float] = dict(config.get("market_caps") or {})

        if not any(r.indicator_id == "rs_index" for r in rules):
            return rules, RuleContext(market_caps=market_caps)

        benchmark_sym: str = config.get("benchmark_symbol", "SPY")
        bench_bars = bars.get(benchmark_sym, [])
        if not bench_bars:
            if strict:
                raise BenchmarkDataUnavailableError(benchmark_sym)
            return rules, RuleContext(market_caps=market_caps)
        return rules, RuleContext(
            rs_ranks=_compute_rs_ranks(symbols, bars),
            market_caps=market_caps,
            benchmark=BarArrays.from_bars(bench_bars),
        )
