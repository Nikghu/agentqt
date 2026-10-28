"""
Module: MD-BKT-001.001.M01 — backtest/store.py
Parent SRD: SRD-BKT-001.001

Parquet candle store for backtesting. 1d bars live in ``1d/<SYM>.parquet``; 3m bars in
``3m/<SYM>/<YYYY>.parquet``. Never touches ``candles.db``.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from us_swing.backtest import DEFAULT_ROOT
from us_swing.backtest.settings import STATE_FILE, DownloadState

Timeframe = Literal["1d", "3m"]

_ET = ZoneInfo("America/New_York")
_DAY_DONE = time(16, 15)
_PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]
_COLUMNS = ["ts", *_PRICE_COLUMNS]


@dataclass(frozen=True, slots=True)
class BacktestStats:
    """Summary of what the store holds.

    Attributes:
        stocks: Number of stocks with any saved bars.
        bars_1d: Total 1d bars.
        bars_3m: Total 3m bars.
        first: Earliest saved 1d date, or ``None`` when empty.
        last: Latest saved 1d date, or ``None`` when empty.
        size_bytes: Disk size of all Parquet files.
        last_delta: When the last delta fill finished, or ``None``.
    """

    stocks: int
    bars_1d: int
    bars_3m: int
    first: date | None
    last: date | None
    size_bytes: int
    last_delta: datetime | None


class BacktestStore:
    """Read, merge-save and summarise backtest candles under ``root``."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def save(self, symbol: str, tf: Timeframe, df: pd.DataFrame, now: datetime) -> int:
        """Merge ``df`` into the saved bars for ``symbol`` and replace the file(s) atomically.

        Bars of today's US/Eastern date are dropped when ``now`` is before 16:15 ET.

        Args:
            symbol: Stock ticker.
            tf: ``"1d"`` or ``"3m"``.
            df: Bars with columns ``ts, open, high, low, close, volume``.
            now: Current time (timezone-aware).

        Returns:
            Number of bars saved from ``df``.
        """
        bars = _normalise(df, tf)
        now_et = now.astimezone(_ET)
        if now_et.time() < _DAY_DONE:
            bars = bars[_et_dates(bars["ts"], tf) != now_et.date()]
        if bars.empty:
            return 0
        if tf == "1d":
            self._merge_write(self._path_1d(symbol), bars)
        else:
            years = pd.Series([d.year for d in _et_dates(bars["ts"], tf)], index=bars.index)
            for year, part in bars.groupby(years):
                self._merge_write(self._dir_3m(symbol) / f"{year}.parquet", part)
        return len(bars)

    def read(
        self,
        symbol: str,
        tf: Timeframe,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Return saved bars for ``symbol`` in time order, optionally limited to a date range."""
        files = self._files(symbol, tf)
        if start is not None and tf == "3m":
            files = [f for f in files if int(f.stem) >= start.year]
        if end is not None and tf == "3m":
            files = [f for f in files if int(f.stem) <= end.year]
        if not files:
            return pd.DataFrame(columns=_COLUMNS)
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        days = _et_dates(df["ts"], tf)
        keep = pd.Series(True, index=df.index)
        if start is not None:
            keep &= days >= start
        if end is not None:
            keep &= days <= end
        return df[keep].sort_values("ts").reset_index(drop=True)

    def coverage(self, symbol: str, tf: Timeframe) -> tuple[date, date] | None:
        """Return the first and last saved date from Parquet metadata, or ``None``."""
        ranges = [r for f in self._files(symbol, tf) if (r := _ts_range(f)) is not None]
        if not ranges:
            return None
        first = min(r[0] for r in ranges)
        last = max(r[1] for r in ranges)
        return _et_date(first, tf), _et_date(last, tf)

    def stats(self) -> BacktestStats:
        """Summarise the store from file metadata without reading the bars."""
        symbols_1d = {p.stem for p in self._glob("1d", "*.parquet")}
        symbols_3m = {p.name for p in (self.root / "3m").glob("*") if p.is_dir()}
        files_1d = self._glob("1d", "*.parquet")
        files_3m = self._glob("3m", "*/*.parquet")
        dates = [d for sym in symbols_1d if (cov := self.coverage(sym, "1d")) for d in cov]
        return BacktestStats(
            stocks=len(symbols_1d | symbols_3m),
            bars_1d=sum(pq.read_metadata(f).num_rows for f in files_1d),
            bars_3m=sum(pq.read_metadata(f).num_rows for f in files_3m),
            first=min(dates) if dates else None,
            last=max(dates) if dates else None,
            size_bytes=sum(f.stat().st_size for f in files_1d + files_3m),
            last_delta=DownloadState.load(self.root).last_delta,
        )

    def clear(self) -> None:
        """Delete all saved candles and the download state; keep ``settings.json``."""
        for sub in ("1d", "3m"):
            shutil.rmtree(self.root / sub, ignore_errors=True)
        (self.root / STATE_FILE).unlink(missing_ok=True)

    def _path_1d(self, symbol: str) -> Path:
        return self.root / "1d" / f"{symbol}.parquet"

    def _dir_3m(self, symbol: str) -> Path:
        return self.root / "3m" / symbol

    def _files(self, symbol: str, tf: Timeframe) -> list[Path]:
        if tf == "1d":
            path = self._path_1d(symbol)
            return [path] if path.exists() else []
        return sorted(self._dir_3m(symbol).glob("*.parquet"))

    def _glob(self, sub: str, pattern: str) -> list[Path]:
        return sorted((self.root / sub).glob(pattern))

    @staticmethod
    def _merge_write(path: Path, bars: pd.DataFrame) -> None:
        if path.exists():
            bars = pd.concat([pd.read_parquet(path), bars], ignore_index=True)
        merged = (
            bars.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            pq.write_table(pa.Table.from_pandas(merged, preserve_index=False), tmp)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def _normalise(df: pd.DataFrame, tf: Timeframe) -> pd.DataFrame:
    out = df[_COLUMNS].copy()
    if tf == "1d":
        ts = pd.to_datetime(out["ts"])
        if ts.dt.tz is not None:
            ts = ts.dt.tz_localize(None)
        out["ts"] = ts.dt.normalize().astype("datetime64[ns]")
    else:
        out["ts"] = pd.to_datetime(out["ts"], utc=True).astype("datetime64[ns, UTC]")
    out[_PRICE_COLUMNS] = out[_PRICE_COLUMNS].astype("float64")
    return out


def _et_dates(ts: pd.Series, tf: Timeframe) -> pd.Series:
    days: pd.Series = ts.dt.date if tf == "1d" else ts.dt.tz_convert(_ET).dt.date
    return days


def _et_date(stamp: pd.Timestamp, tf: Timeframe) -> date:
    if tf == "3m":
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
        return stamp.tz_convert(_ET).date()
    return stamp.date()


def _ts_range(path: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    meta = pq.read_metadata(path)
    col = meta.schema.names.index("ts")
    lows: list[pd.Timestamp] = []
    highs: list[pd.Timestamp] = []
    for i in range(meta.num_row_groups):
        stats = meta.row_group(i).column(col).statistics
        if stats is None or not stats.has_min_max:
            ts = pd.read_parquet(path, columns=["ts"])["ts"]
            return (pd.Timestamp(ts.min()), pd.Timestamp(ts.max())) if len(ts) else None
        lows.append(pd.Timestamp(stats.min))
        highs.append(pd.Timestamp(stats.max))
    return (min(lows), max(highs)) if lows else None
