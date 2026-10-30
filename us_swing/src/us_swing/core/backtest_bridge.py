"""
Module: MD-BKT-002.011.M08 — core/backtest_bridge.py
Parent SRD: SRD-BKT-002.011, SRD-BKT-002.029, SRD-MCP-007.002

Bridge from the backtest engine to screener presets, live strategies and
the S&P 500 universe, so ``backtest`` never imports another tool directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from us_swing.screener.executor import PresetExecutor
from us_swing.screener.manager import PresetManager
from us_swing.screener.preset import Preset
from us_swing.universe.store import Sp500Record, load_sp500


@dataclass(frozen=True)
class PresetInfo:
    """What the backtest builder shows for a preset."""

    id: str
    name: str
    timeframe: str
    ai: bool


def load_universe() -> list[Sp500Record]:
    """Return the saved S&P 500 records (refreshed when stale)."""
    return load_sp500()


def list_presets(user_id: str) -> list[PresetInfo]:
    """Return admin presets and the user's presets, by name, without duplicates."""
    mgr = PresetManager()
    found: dict[str, Preset] = {p.id: p for p in mgr.list_admin_presets()}
    for p in mgr.list_user_presets(user_id):
        found.setdefault(p.id, p)
    return sorted(
        (PresetInfo(p.id, p.name, p.timeframe, p.enable_llm_ranking) for p in found.values()),
        key=lambda info: info.name.lower(),
    )


def load_strategies() -> list[dict[str, Any]]:
    """Return the live strategies (``StrategyConfig`` fields) as plain dicts."""
    import us_swing.data  # noqa: F401, PLC0415 — avoids the db/data import cycle
    from us_swing.gui.strategy_store import load_strategies as _load  # noqa: PLC0415

    return [asdict(cfg) for cfg in _load()]


def default_user_id() -> str:
    """The app's first saved user, as the app uses at start; "1" before any user exists."""
    from us_swing.gui.user_store import load_users  # noqa: PLC0415 — same cycle as above

    users = load_users()
    return str(users[0].user_id) if users else "1"


def load_preset_dict(preset_id: str, user_id: str) -> dict[str, Any]:
    """Return a preset as a plain dict (picklable for worker processes).

    Raises:
        PresetNotFoundError, PresetAccessDenied: as ``PresetManager.load_preset``.
    """
    return PresetManager().load_preset(preset_id, user_id).to_dict()


def screen_day(
    preset_dict: dict[str, Any],
    symbols: list[str],
    bars: dict[str, list[Any]],
    market_caps: dict[str, float],
) -> dict[str, tuple[bool, float]]:
    """Run the preset's rule stages (no AI, nothing saved) on one day's bars."""
    preset = Preset.from_dict(preset_dict)
    combined = PresetExecutor(max_workers=1).screen(preset, symbols, bars, market_caps)
    return {
        sym: (bool(d.get("passed", False)), float(d.get("score", 0.0)))
        for sym, d in combined.items()
    }
