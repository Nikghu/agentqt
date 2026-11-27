"""Tests for MD-BKT-002.093.M16 — backtest/steps/sectors.py."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from us_swing.backtest.spec import SectorFilterSpec
from us_swing.backtest.steps import sectors
from us_swing.core.stock_context import SECTOR_ETFS, SECTOR_SYMBOLS

_DAYS = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
_ETFS = [sym for sym, _name in SECTOR_ETFS]


def _closes(moves: dict[str, float], jump_last: str = "") -> dict[str, pd.Series]:
    """RSP flat; each ETF moves ``moves[sym]`` % a day; ``jump_last`` doubles on the last day."""
    out = {"RSP": pd.Series(100.0, index=_DAYS)}
    for sym in _ETFS:
        values = [100 * (1 + moves.get(sym, 0.0) / 100) ** i for i in range(len(_DAYS))]
        if sym == jump_last:
            values[-1] *= 2
        out[sym] = pd.Series(values, index=_DAYS)
    return out


def test_ranks_on_previous_closes() -> None:
    """UT-BKT-002.093.M16.T01: A day's ranking uses closes before it, not the day itself."""
    closes = _closes({"XLK": 2, "XLF": 1, "XLE": -2, "XLU": -1}, jump_last="XLU")
    spec = SectorFilterSpec(enabled=True, top_n=2, range="1W")

    gate = sectors.sector_gates(closes, [_DAYS[-1]], spec)[_DAYS[-1]]

    assert gate.longs == {"Information Technology", "Financials"}
    assert gate.shorts == {"Energy", "Utilities"}


def test_must_beat_rsp() -> None:
    """UT-BKT-002.093.M16.T02: Must beat RSP keeps longs above RSP and shorts below it."""
    closes = _closes({"XLK": 2, "XLE": -2})
    on = sectors.sector_gates(closes, [_DAYS[-1]], SectorFilterSpec(True, 3, "1W", True))
    off = sectors.sector_gates(closes, [_DAYS[-1]], SectorFilterSpec(True, 3, "1W", False))

    assert on[_DAYS[-1]].longs == {"Information Technology"}
    assert on[_DAYS[-1]].shorts == {"Energy"}
    assert len(off[_DAYS[-1]].longs) == 3 and "Information Technology" in off[_DAYS[-1]].longs


def test_too_little_history_gives_no_ranking() -> None:
    """UT-BKT-002.093.M16.T03: A day with fewer closes than the range has no ranking."""
    closes = _closes({"XLK": 1})

    assert sectors.sector_gates(closes, [_DAYS[3]], SectorFilterSpec(True, 3, "1W")) == {}


def test_missing_symbols() -> None:
    """UT-BKT-002.095.M16.T01: RSP or a sector ETF with no saved data is named."""
    have = {sym: True for sym in SECTOR_SYMBOLS}

    assert sectors.missing_symbols(have) == []
    assert sectors.missing_symbols({**have, "RSP": False, "XLC": False}) == ["RSP", "XLC"]
