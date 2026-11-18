"""
Module: MD-SCR-017.017.M34 — Accumulation / Distribution Settings Tips
Parent SRD: SRD-SCR-017.017
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from us_swing.screener.screeners.acc_dist import ACCUMULATION, OWN_MOVE


@dataclass(frozen=True, slots=True)
class Tip:
    """Tip panel text for one setting. ``example`` may hold <b> tags."""

    title: str
    text: str
    example: str


@dataclass(frozen=True, slots=True)
class TabSpec:
    """One settings tab: its name, column headings and rows of two setting keys."""

    name: str
    rows: tuple[tuple[str, str | None], ...]
    heads: tuple[str, str] | None = None
    summary: bool = False


LABELS: dict[str, str] = {
    "mode": "Mode",
    "move_rule": "Move rule",
    "lookback": "Lookback (days)",
    "volume_period": "Volume average (days)",
    "move_factor": "Move factor",
    "min_move_pct": "Minimum move",
    "high_factor": "High volume ≥",
    "low_factor": "Low volume ≤",
    "min_rally_days": "Minimum rally days",
    "min_drop_days": "Minimum drop days",
    "min_ud_ratio": "Up/down ratio ≥ (Acc)",
    "max_ud_ratio": "Up/down ratio ≤ (Dist)",
    "location_filter": "Use Range Zone",
    "close_position": "Use Close Zone",
    "range_period": "Range period",
    "close_zone_pct": "Close Zone",
    "zone_pct": "Range Zone",
    "min_score": "Minimum score",
}

TABS: tuple[TabSpec, ...] = (
    TabSpec("Basics", (("mode", "move_rule"), ("lookback", "volume_period"),
                       ("move_factor", "min_move_pct"))),
    TabSpec("Volume & Pattern", (("high_factor", "low_factor"),
                                 ("min_rally_days", "min_drop_days"),
                                 ("min_ud_ratio", "max_ud_ratio"))),
    TabSpec("Range Zone & Close Zone", (("location_filter", "close_position"),
                                        ("range_period", "close_zone_pct"), ("zone_pct", None)),
            heads=("Range Zone", "Close Zone")),
    TabSpec("Result", (("min_score", None),), summary=True),
)


def _acc(cfg: dict[str, Any]) -> bool:
    return bool(cfg["mode"] == ACCUMULATION)


def tab_intro(index: int, cfg: dict[str, Any]) -> str:
    """One line under the tab strip saying what the tab is for."""
    acc = _acc(cfg)
    return (
        "What to look for, over how many days, and which days count.",
        "Heavy rallies and light drops, and how strongly buyers must lead." if acc
        else "Heavy drops and light rallies, and how strongly sellers must lead.",
        "Range Zone: where the stock sits in its range. Close Zone: where a heavy "
        + ("rally" if acc else "drop") + " closes in its day.",
        "How well a stock must fit to make the list.",
    )[index]


def _money(value: float) -> str:
    return f"${value:.2f}"


def _mode(c: dict[str, Any]) -> Tip:
    if _acc(c):
        return Tip("Look for buying",
                   "Rallies on heavy volume and drops on light volume, near the range low.",
                   "Use after a long fall, to spot a <b>base</b> forming.")
    return Tip("Look for selling",
               "Drops on heavy volume and rallies on light volume, near the range high.",
               "Use after a long rise, to spot a <b>top</b> forming.")


def _ratio_acc(c: dict[str, Any]) -> Tip:
    if not _acc(c):
        return Tip("Not used now", "Only used in Accumulation mode.",
                   "Switch Mode to <b>Accumulation</b> in Basics to use it.")
    verdict = "passes" if 1.5 >= c["min_ud_ratio"] else "fails"
    return Tip("Buyers heavier",
               "Volume on rally days ÷ volume on drop days must be at least this.",
               f"Rally days 3.0M, drop days 2.0M → 1.50 <b>{verdict}</b>. "
               "1.3 is normal, 1.5 strict.")


def _ratio_dist(c: dict[str, Any]) -> Tip:
    if _acc(c):
        return Tip("Not used now", "Only used in Distribution mode.",
                   "Switch Mode to <b>Distribution</b> in Basics to use it.")
    verdict = "passes" if 0.75 <= c["max_ud_ratio"] else "fails"
    return Tip("Sellers heavier",
               "Volume on rally days ÷ volume on drop days must be at most this.",
               f"Rally days 1.5M, drop days 2.0M → 0.75 <b>{verdict}</b>. "
               "0.8 is normal, 0.7 strict.")


def _range_zone(c: dict[str, Any]) -> Tip:
    acc, zone = _acc(c), c["zone_pct"] / 100.0
    edge = 80 + 20 * zone if acc else 100 - 20 * zone
    return Tip("How near the low" if acc else "How near the high",
               f"Today's close must be in this {'bottom' if acc else 'top'} part of the range.",
               f"Range $80–$100 → close must be <b>{'≤' if acc else '≥'} {_money(edge)}</b>. "
               "25% = at the edge, 35–40% = wider.")


def _close_zone(c: dict[str, Any]) -> Tip:
    acc, zone = _acc(c), c["close_zone_pct"] / 100.0
    edge = 50 - 2 * zone if acc else 48 + 2 * zone
    move = "rally" if acc else "drop"
    return Tip("Close near the high" if acc else "Close near the low",
               f"A heavy {move} must close in this {'top' if acc else 'bottom'} part of its day.",
               f"Day $48–$50 → close must be <b>{'≥' if acc else '≤'} {_money(edge)}</b>. "
               "30% is a good start.")


_TIPS: dict[str, Callable[[dict[str, Any]], Tip]] = {
    "mode": _mode,
    "move_rule": lambda c: Tip(
        "Which days count",
        "Stock's own move judges each stock by its own normal daily move. "
        "Fixed % uses one number for every stock.",
        "Keep <b>Stock's own move</b>. Use Fixed % only to repeat old results."),
    "lookback": lambda c: Tip(
        "Days judged", "How many recent days are checked for the pattern.",
        f"Swing: 20. Longer base or top: 40–60. Now: last <b>{c['lookback']}</b> days."),
    "volume_period": lambda c: Tip(
        "Normal volume",
        "Each day is compared with the average volume of this many days before it.",
        f"Needs <b>{c['lookback'] + c['volume_period'] + 1}</b> days of data per stock. "
        "Keep it equal to or longer than Lookback."),
    "move_factor": lambda c: Tip(
        "Move size", "A day counts if it moves this many times the stock's normal daily move.",
        f"A stock that moves 2% a day needs a <b>{2 * c['move_factor']:.2f}%</b> move. "
        "0.5× is a good start."),
    "min_move_pct": lambda c: Tip(
        "Fixed move", "Used only with Fixed %. A day counts if it moves at least this %.",
        f"Every stock needs a <b>{c['min_move_pct']:.2f}%</b> move. "
        "Calm stocks: 0.5%; fast stocks need 1–1.5%."),
    "high_factor": lambda c: Tip(
        "Heavy buying day" if _acc(c) else "Heavy selling day",
        f"A {'rally' if _acc(c) else 'drop'} on volume above this counts as strong "
        f"{'buying' if _acc(c) else 'selling'}.",
        f"Normal 2.0M shares → heavy is <b>{2 * c['high_factor']:.1f}M</b> or more. "
        "1.5× keeps only big days."),
    "low_factor": lambda c: Tip(
        "Quiet drop" if _acc(c) else "Quiet rally",
        f"A {'drop' if _acc(c) else 'rally'} on volume below this shows no real "
        f"{'selling' if _acc(c) else 'buying'}.",
        f"Normal 2.0M shares → light is <b>{2 * c['low_factor']:.1f}M</b> or less. "
        "0.8× is stricter."),
    "min_rally_days": lambda c: Tip(
        "Enough rallies", "Fewer rally days than this and the stock is skipped.",
        f"Use 3 for 20 days, 5 for 40 days. Now: <b>{c['min_rally_days']}</b>."),
    "min_drop_days": lambda c: Tip(
        "Enough drops", "Fewer drop days than this and the stock is skipped.",
        f"Use 3 for 20 days, 5 for 40 days. Now: <b>{c['min_drop_days']}</b>."),
    "min_ud_ratio": _ratio_acc,
    "max_ud_ratio": _ratio_dist,
    "location_filter": lambda c: Tip(
        "Near the low" if _acc(c) else "Near the high",
        f"When ticked, the stock must close near the {'bottom' if _acc(c) else 'top'} "
        "of its recent range.",
        "Untick to find the pattern <b>anywhere</b> in the range."),
    "range_period": lambda c: Tip(
        "Range length", "The highest high and lowest low of this many days make the range.",
        f"Swing: 60–90. Position: 126. Now: <b>{c['range_period']}</b> days."),
    "zone_pct": _range_zone,
    "close_position": lambda c: Tip(
        "Buyers won the day" if _acc(c) else "Sellers won the day",
        f"When ticked, a heavy {'rally' if _acc(c) else 'drop'} counts only if it closes "
        f"near the day's {'high' if _acc(c) else 'low'}.",
        "Keep it ticked: it removes <b>false</b> heavy days."),
    "close_zone_pct": _close_zone,
    "min_score": lambda c: Tip(
        "How well it fits", "Share of rally and drop days that fit the pattern, from 0 to 1.",
        f"6 of 8 rallies + 3 of 6 drops fit → 0.63 "
        f"<b>{'passes' if 0.625 >= c['min_score'] else 'fails'}</b>. 0.6 strict, 0.4 wide."),
}


def tip(key: str, cfg: dict[str, Any]) -> Tip:
    """Tip for one setting, worded for the config's mode and values."""
    return _TIPS[key](cfg)


def summary(cfg: dict[str, Any]) -> str:
    """All settings as one plain-English paragraph (with <b> tags)."""
    acc = _acc(cfg)
    heavy, light = ("rallies", "drops") if acc else ("drops", "rallies")
    parts = [
        f"Find <b>{'accumulation' if acc else 'distribution'}</b> over the last "
        f"<b>{cfg['lookback']} days</b>, against normal volume of the "
        f"<b>{cfg['volume_period']} days</b> before each day.",
        f"{heavy.capitalize()} on <b>{cfg['high_factor']:.2f}×</b> volume or more, "
        f"{light} on <b>{cfg['low_factor']:.2f}×</b> or less.",
        f"A day counts if it moves <b>{cfg['move_factor']:.2f}×</b> the stock's normal move."
        if cfg["move_rule"] == OWN_MOVE
        else f"A day counts if it moves <b>{cfg['min_move_pct']:.2f}%</b>.",
    ]
    if cfg["close_position"]:
        parts.append(f"Heavy {heavy} must close in the <b>{'top' if acc else 'bottom'} "
                     f"{cfg['close_zone_pct']:.0f}%</b> of the day.")
    parts.append(f"Rally volume at least <b>{cfg['min_ud_ratio']:.2f}×</b> drop volume."
                 if acc else
                 f"Rally volume at most <b>{cfg['max_ud_ratio']:.2f}×</b> drop volume.")
    if cfg["location_filter"]:
        parts.append(f"Close in the <b>{'bottom' if acc else 'top'} {cfg['zone_pct']:.0f}%</b> "
                     f"of the {cfg['range_period']}-day range.")
    parts.append(f"At least <b>{cfg['min_score'] * 100:.0f}%</b> of days must fit.")
    return " ".join(parts)
