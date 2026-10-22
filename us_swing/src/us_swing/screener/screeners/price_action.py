"""Module: MD-SCR-002.005.M08 — screeners/price_action.py
Parent SRD: SRD-SCR-002.007, SRD-SCR-016.012

PriceActionScreener: scores each symbol by how many of its enabled price action
pattern rules match on the last bar. Pattern logic lives in ``core.price_patterns``.

Score = patterns_matched / patterns_enabled.
Symbol passes if score >= threshold (default 0.2).
"""
from __future__ import annotations

import logging
from typing import Any

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import (
    PatternRule,
    evaluate_pattern,
    get_pattern,
    pattern_rules_from_config,
)
from us_swing.screener.base import ScreenerError

_log = logging.getLogger(__name__)


def _enabled_rules(config: dict[str, Any]) -> tuple[list[PatternRule], float]:
    rules, threshold = pattern_rules_from_config(config)
    return [r for r in rules if r.enabled], threshold


class PriceActionScreener:
    """MD-SCR-002.005.M08 — price action pattern screener."""

    screener_id: str = "price_action"
    screener_type: str = "price_action"
    name: str = "Price Action Screener"

    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, tuple[bool, float]]:
        """Screen symbols for price action patterns.

        Args:
            symbols: Symbols to screen.
            bars: Map of symbol → list[OHLCVBar] (oldest first).
            config: Rule-list or legacy pattern config (SRD-SCR-016.008/.009).

        Returns:
            dict mapping symbol → (passed, score). Symbols with <2 bars omitted.

        Raises:
            ScreenerError: If the threshold is outside 0–1.
            PatternRuleError: If the rules cannot be read.
        """
        rules, threshold = _enabled_rules(config)
        if not 0.0 <= threshold <= 1.0:
            raise ScreenerError(
                f"PriceActionScreener: threshold must be in [0, 1], got {threshold}"
            )

        results: dict[str, tuple[bool, float]] = {}
        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if len(sym_bars) < 2:
                continue
            arrays = BarArrays.from_bars(sym_bars)
            matched = sum(evaluate_pattern(rule, arrays) for rule in rules)
            score = matched / len(rules) if rules else 0.0
            results[sym] = (score >= threshold, round(score, 4))

        passed_count = sum(1 for p, _ in results.values() if p)
        _log.debug(
            "[Screener] Price action screened %d stock(s), %d passed", len(symbols), passed_count
        )
        return results

    def screen_detailed(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Return per-pattern match flags for each symbol (used by executor for DETAILS column).

        Returns:
            dict mapping symbol → {pattern short label: bool}.
        """
        rules, _ = _enabled_rules(config)
        details: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if len(sym_bars) < 2:
                continue
            arrays = BarArrays.from_bars(sym_bars)
            details[sym] = {
                get_pattern(rule.pattern_id).short: evaluate_pattern(rule, arrays)
                for rule in rules
            }
        return details

    def batch_features(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
    ) -> dict[str, dict[str, Any]]:
        return {}
