"""
Module: MD-BKT-002.080.M14 — backtest/steps/recorded.py
Parent SRD: SRD-BKT-002.080, SRD-BKT-002.081

Step 1 from the screener lists the app saved (``screener_results/preset_<id>/<date>.json``)
instead of replaying the preset, so the real picks (AI picks included) are tested.
"""
from __future__ import annotations

import bisect
import json
import logging
from collections.abc import Collection, Sequence
from datetime import date, time, timedelta
from pathlib import Path

import pandas as pd

_log = logging.getLogger(__name__)

RESULTS_DIR = Path.home() / ".usswing" / "screener_results"
ET = "America/New_York"
MARKET_OPEN = time(9, 30)
COLUMNS = ["date", "symbol", "score", "rank"]
MAX_GAP_DAYS = 4  # weekend plus a holiday


def _files(preset_id: str, base: Path) -> list[Path]:
    folder = base / f"preset_{preset_id}"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def saved_days(preset_id: str, base: Path = RESULTS_DIR) -> list[date]:
    """Dates of the saved lists for a preset, oldest first."""
    out = []
    for path in _files(preset_id, base):
        try:
            out.append(date.fromisoformat(path.stem))
        except ValueError:
            continue
    return out


def trade_day(run_ts: pd.Timestamp) -> date:
    """The day a list is traded: same day before 09:30 ET, else the next day (SRD-BKT-002.081)."""
    local = run_ts.tz_convert(ET) if run_ts.tzinfo else run_ts.tz_localize(ET)
    day: date = local.date()
    return day if local.time() < MARKET_OPEN else day + timedelta(days=1)


def _read(path: Path) -> tuple[pd.Timestamp, dict[str, dict[str, object]]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stamp = pd.Timestamp(data.get("run_timestamp") or path.stem)
        return stamp, dict(data.get("results") or {})
    except (OSError, ValueError, TypeError) as exc:
        _log.warning("[Backtest] Saved screener list %s could not be read: %s", path.name, exc)
        return None


def load_lists(preset_id: str, sessions: Sequence[date], symbols: Collection[str],
               base: Path = RESULTS_DIR) -> pd.DataFrame:
    """Daily list (date, symbol, score, rank) from the saved lists (SRD-BKT-002.080).

    Each list goes to the first session on or after its trade day (at most
    ``MAX_GAP_DAYS`` later); when two lists land on one session, the newer one wins.
    Only passed stocks in ``symbols`` are kept, ranked by score.
    """
    ordered = sorted(sessions)
    chosen: dict[date, tuple[pd.Timestamp, dict[str, dict[str, object]]]] = {}
    for path in _files(preset_id, base):
        read = _read(path)
        if read is None:
            continue
        stamp, results = read
        day = trade_day(stamp)
        i = bisect.bisect_left(ordered, day)
        if i == len(ordered) or (ordered[i] - day).days > MAX_GAP_DAYS:
            continue
        session = ordered[i]
        if session not in chosen or chosen[session][0] < stamp:
            chosen[session] = (stamp, results)
    rows = []
    for session, (_stamp, results) in sorted(chosen.items()):
        picks = sorted(((float(str(r.get("score", 0.0))), sym) for sym, r in results.items()
                        if r.get("passed") and sym in symbols), key=lambda p: -p[0])
        rows += [(session, sym, score, rank) for rank, (score, sym) in enumerate(picks, 1)]
    return pd.DataFrame(rows, columns=COLUMNS)
