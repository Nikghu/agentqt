"""
Module: MD-BKT-001.001.M01 — backtest/store.py
Parent SRD: SRD-BKT-001.001

Parquet candle store for backtesting. 1d bars live in ``1d/<SYM>.parquet``; 3m bars in
``3m/<SYM>/<YYYY>.parquet``. 15m bars (``15m/<SYM>/<YYYY>.parquet``) and 1w bars
(``1w/<SYM>.parquet``) are built from them on every save. Never touches ``candles.db``.
"""
from __future__ import annotations

import os
import shutil
import time as time_mod
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from us_swing.backtest import DEFAULT_ROOT
from us_swing.backtest.settings import STATE_FILE, DownloadState

Timeframe = Literal["1d", "3m"]
StoredTf = Literal["1d", "3m", "15m", "1w"]

_YEARLY: tuple[StoredTf, ...] = ("3m", "15m")
_ET = ZoneInfo("America/New_York")
_DAY_DONE = time(16, 15)
_REPLACE_TRIES = 5
_LISTED_SLACK = timedelta(days=7)
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
        first_3m: Date from which every stock has 3m bars (stocks listed later are skipped),
            or ``None`` when no 3m bars are saved.
        missing_1d: 1d requests the download plan still needs (set by the caller).
        missing_3m: 3m requests the download plan still needs (set by the caller).
        short_stocks: Stocks with any request in the download plan (set by the caller).
    """

    stocks: int
    bars_1d: int
    bars_3m: int
    first: date | None
    last: date | None
    size_bytes: int
    last_delta: datetime | None
    first_3m: date | None = None
    missing_1d: int = 0
    missing_3m: int = 0
    short_stocks: int = 0


class BacktestStore:
    """Read, merge-save and summarise backtest candles under ``root``."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def save(
        self,
        symbol: str,
        tf: Timeframe,
        df: pd.DataFrame,
        now: datetime,
        start: date | None = None,
    ) -> int:
        """Merge ``df`` into the saved bars for ``symbol`` and replace the file(s) atomically.

        Bars of today's US/Eastern date are dropped when ``now`` is before 16:15 ET, and bars
        before ``start`` are dropped so the store keeps only the asked range. A 3m save rebuilds
        the 15m file of each year it touched; a 1d save rebuilds the 1w file.

        Args:
            symbol: Stock ticker.
            tf: ``"1d"`` or ``"3m"``.
            df: Bars with columns ``ts, open, high, low, close, volume``.
            now: Current time (timezone-aware).
            start: Oldest US/Eastern date to keep, or ``None`` to keep all.

        Returns:
            Number of bars saved from ``df``.
        """
        bars = _normalise(df, tf)
        now_et = now.astimezone(_ET)
        if now_et.time() < _DAY_DONE:
            bars = bars[_et_dates(bars["ts"], tf) != now_et.date()]
        if start is not None:
            bars = bars[_et_dates(bars["ts"], tf) >= start]
        if bars.empty:
            return 0
        if tf == "1d":
            self._merge_write(self._single(symbol, "1d"), bars)
            self._build_1w(symbol)
        else:
            years = pd.Series([d.year for d in _et_dates(bars["ts"], tf)], index=bars.index)
            for year, part in bars.groupby(years):
                self._merge_write(self._yearly(symbol, "3m") / f"{year}.parquet", part)
                self._build_15m(symbol, f"{year}.parquet")
        return len(bars)

    def build_missing(self) -> int:
        """Build 15m and 1w files that are missing or older than their 3m or 1d source.

        Returns:
            Number of stocks that got at least one file built.
        """
        built: set[str] = set()
        for src in self._glob("3m", "*/*.parquet"):
            symbol = src.parent.name
            if _stale(self._yearly(symbol, "15m") / src.name, src):
                self._build_15m(symbol, src.name)
                built.add(symbol)
        for src in self._glob("1d", "*.parquet"):
            if _stale(self._single(src.stem, "1w"), src):
                self._build_1w(src.stem)
                built.add(src.stem)
        return len(built)

    def read(
        self,
        symbol: str,
        tf: StoredTf,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Return saved bars for ``symbol`` in time order, optionally limited to a date range.

        1w bars carry an extra ``days`` column: the number of daily bars in that week.
        """
        files = self._files(symbol, tf)
        if start is not None and tf in _YEARLY:
            files = [f for f in files if int(f.stem) >= start.year]
        if end is not None and tf in _YEARLY:
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

    def coverage(self, symbol: str, tf: StoredTf) -> tuple[date, date] | None:
        """Return the first and last saved date from Parquet metadata, or ``None``.

        For 3m only the oldest and newest year files are read; year files never overlap.
        """
        files = self._files(symbol, tf)
        ends = list(dict.fromkeys(files[:1] + files[-1:]))
        ranges = [r for f in ends if (r := _ts_range(f)) is not None]
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
        files_built = self._glob("15m", "*/*.parquet") + self._glob("1w", "*.parquet")
        dates = [d for sym in symbols_1d if (cov := self.coverage(sym, "1d")) for d in cov]
        state = DownloadState.load(self.root)
        firsts_3m = [
            cov[0] for sym in symbols_3m if (cov := self.coverage(sym, "3m"))
            and not ((floor := state.floors.get(sym)) and cov[0] <= floor + _LISTED_SLACK)
        ]
        return BacktestStats(
            stocks=len(symbols_1d | symbols_3m),
            bars_1d=sum(pq.read_metadata(f).num_rows for f in files_1d),
            bars_3m=sum(pq.read_metadata(f).num_rows for f in files_3m),
            first=min(dates) if dates else None,
            last=max(dates) if dates else None,
            size_bytes=sum(f.stat().st_size for f in files_1d + files_3m + files_built),
            last_delta=state.last_delta,
            first_3m=max(firsts_3m) if firsts_3m else None,
        )

    def clear(self) -> None:
        """Delete all saved candles and the download state; keep ``settings.json``."""
        for sub in ("1d", "3m", "15m", "1w"):
            shutil.rmtree(self.root / sub, ignore_errors=True)
        (self.root / STATE_FILE).unlink(missing_ok=True)

    def _single(self, symbol: str, tf: StoredTf) -> Path:
        return self.root / tf / f"{symbol}.parquet"

    def _yearly(self, symbol: str, tf: StoredTf) -> Path:
        return self.root / tf / symbol

    def _files(self, symbol: str, tf: StoredTf) -> list[Path]:
        if tf in _YEARLY:
            return sorted(self._yearly(symbol, tf).glob("*.parquet"))
        path = self._single(symbol, tf)
        return [path] if path.exists() else []

    def _glob(self, sub: str, pattern: str) -> list[Path]:
        return sorted((self.root / sub).glob(pattern))

    def _build_15m(self, symbol: str, year_file: str) -> None:
        bars = pd.read_parquet(self._yearly(symbol, "3m") / year_file)
        _write(self._yearly(symbol, "15m") / year_file, _to_15m(bars))

    def _build_1w(self, symbol: str) -> None:
        bars = pd.read_parquet(self._single(symbol, "1d"))
        _write(self._single(symbol, "1w"), _to_1w(bars))

    @staticmethod
    def _merge_write(path: Path, bars: pd.DataFrame) -> None:
        if path.exists():
            bars = pd.concat([pd.read_parquet(path), bars], ignore_index=True)
        merged = (
            bars.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
        )
        _write(path, merged)


def _write(path: Path, bars: pd.DataFrame) -> None:
    """Write ``bars`` to ``path`` atomically; the temp name is unique per call."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        pq.write_table(pa.Table.from_pandas(bars, preserve_index=False), tmp)
        _replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _stale(built: Path, source: Path) -> bool:
    return not built.exists() or built.stat().st_mtime < source.stat().st_mtime


def _to_15m(bars: pd.DataFrame) -> pd.DataFrame:
    """Group 3m bars into 15m bars timed by their start (09:30, 09:45 … 15:45 ET).

    US/Eastern is a whole number of hours from UTC, so 15-minute UTC buckets match ET ones.
    """
    return _ohlcv(bars, bars["ts"].dt.floor("15min"))


def _to_1w(bars: pd.DataFrame) -> pd.DataFrame:
    """Group 1d bars into Monday-to-Friday weeks dated by the Monday; ``days`` counts bars."""
    monday = bars["ts"] - pd.to_timedelta(bars["ts"].dt.weekday, unit="D")
    weeks = _ohlcv(bars, monday)
    weeks["days"] = bars.groupby(monday).size().to_numpy()
    return weeks


def _ohlcv(bars: pd.DataFrame, key: pd.Series) -> pd.DataFrame:
    grouped = bars.sort_values("ts").groupby(key.rename("ts"))
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    return out.reset_index()


def _replace(tmp: Path, path: Path) -> None:
    """``os.replace`` with short retries: on Windows a stats read can hold the file briefly."""
    for attempt in range(_REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _REPLACE_TRIES - 1:
                raise
            time_mod.sleep(0.2)


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


def _et_dates(ts: pd.Series, tf: StoredTf) -> pd.Series:
    days: pd.Series = ts.dt.tz_convert(_ET).dt.date if tf in _YEARLY else ts.dt.date
    return days


def _et_date(stamp: pd.Timestamp, tf: StoredTf) -> date:
    if tf in _YEARLY:
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
