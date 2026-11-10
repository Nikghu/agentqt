"""
Module: MD-MKT-001.013.M06 — market/candle_check.py
Parent SRD: SRD-MKT-001.013
Also: SRD-MKT-001.014 (Yahoo desk copy), SRD-MKT-001.015 (copy trimmed once IBKR has the day),
SRD-MKT-001.016 (stop the run when still behind), SRD-MKT-001.017 (log),
SRD-DSK-007.007 (candles alert)

Desk step "Candle check", the first step of every morning and manual run. It finds SPY and the
S&P 500 members whose daily candles stop before the last closed trading day, fills only those
days from Yahoo Finance into the desk's own ``candle_topup`` table (``candles.db`` stays
IBKR-only), and stops the run before any AI step when the candles are still not up to date.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from us_swing.core.desk_alerts import Sender, raise_alert
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.symbols import yahoo_symbol
from us_swing.data.market_calendar import get_exchange_status
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader, member_symbols
from us_swing.market.store import MarketStore, TopupRow

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)
SETTLED = time(16, 30)  # a Yahoo bar fetched before this may not be final; fetched again
MAX_BEHIND_SHARE = 0.02
OVERLAP_DAYS = 10
MIN_OVERLAP = 3
CLOSE_TOLERANCE = 0.005
LOOKBACK = timedelta(days=20)

Fetcher = Callable[[list[str], date, date], dict[str, pd.DataFrame]]


class CandleCheckError(RuntimeError):
    """The candles are not up to date, so the run must stop before any AI step."""


def _trading_day(day: date) -> bool:
    return get_exchange_status(datetime.combine(day, time(12, 0), NY)) == "open"


def last_closed_day(now: datetime) -> date:
    """Today after the 16:00 New York close on a trading day, else the trading day before."""
    now_ny = now.astimezone(NY)
    day = now_ny.date()
    if _trading_day(day) and now_ny.time() >= MARKET_CLOSE:
        return day
    day -= timedelta(days=1)
    while not _trading_day(day):
        day -= timedelta(days=1)
    return day


def fetch_daily(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """Daily bars (``open``, ``high``, ``low``, ``close``, ``volume`` by date) from Yahoo.

    Prices are not dividend-adjusted, as in IBKR. Any failure is logged and gives no bars.
    """
    import yfinance as yf  # type: ignore[import-untyped]  # noqa: PLC0415 — slow import

    names = {yahoo_symbol(s): s for s in symbols}
    try:
        raw = yf.download(
            list(names), start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=False, group_by="ticker", threads=True, progress=False,
        )
    except Exception as exc:  # noqa: BLE001 — a network failure only leaves stocks behind
        log.warning("[Candles] Could not download daily candles from Yahoo Finance: %s", exc)
        return {}
    if raw is None or raw.empty:
        return {}
    out: dict[str, pd.DataFrame] = {}
    for ticker, symbol in names.items():
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker not in raw.columns.get_level_values(0):
                continue
            frame = raw[ticker]
        else:
            frame = raw
        frame = frame.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        frame = frame.dropna()
        frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
        if not frame.empty:
            out[symbol] = frame
    return out


def topup_rows(
    ibkr: Mapping[str, pd.DataFrame],
    yahoo: Mapping[str, pd.DataFrame],
    target: date,
    fetched: str,
) -> list[TopupRow]:
    """Desk-copy rows for the Yahoo days each stock lacks, up to ``target``.

    Args:
        ibkr: ``candles.db`` bars per stock (``close``, ``volume`` by date).
        yahoo: Yahoo bars per stock (``open``, ``high``, ``low``, ``close``, ``volume``).
        target: Last day to keep.
        fetched: When the bars were fetched (UTC ISO).

    A stock is left out when fewer than ``MIN_OVERLAP`` recent days are in both sources or a
    shared close differs by more than ``CLOSE_TOLERANCE``. Volume is scaled by the median
    IBKR / Yahoo ratio of the shared days, because IBKR counts regular-hours trades only.
    """
    rows: list[TopupRow] = []
    end = pd.Timestamp(target)
    for symbol, new in yahoo.items():
        old = ibkr.get(symbol)
        if old is None or old.empty:
            continue
        shared = old.index.intersection(new.index)[-OVERLAP_DAYS:]
        if len(shared) < MIN_OVERLAP:
            log.debug("[Candles] %s has too few shared days with Yahoo Finance", symbol)
            continue
        drift = (new.loc[shared, "close"] / old.loc[shared, "close"] - 1).abs()
        if bool((drift > CLOSE_TOLERANCE).any()):
            log.debug("[Candles] %s prices from Yahoo Finance do not match IBKR", symbol)
            continue
        yahoo_volume = new.loc[shared, "volume"]
        ratio = (old.loc[shared, "volume"] / yahoo_volume.where(yahoo_volume > 0)).dropna()
        if ratio.empty:
            continue
        scale = float(ratio.median())
        add = new[(new.index > old.index.max()) & (new.index <= end)]
        rows += [
            TopupRow(symbol, stamp.date().isoformat(), float(bar.open), float(bar.high),
                     float(bar.low), float(bar.close), round(float(bar.volume) * scale), fetched)
            for stamp, bar in add.iterrows()
        ]
    return rows


class CandleCheckStep:
    """Desk step "Candle check": fill missing daily candles, or stop the run."""

    name = "Candle check"

    def __init__(
        self,
        candles: Path = CANDLE_DB,
        fetch: Fetcher = fetch_daily,
        universe: Callable[[], list[tuple[str, str]]] | None = None,
        clock: Callable[[], datetime] | None = None,
        send: Sender | None = None,
    ) -> None:
        """Set the data sources, clock and alert sender; all are injectable for tests."""
        self._candles = candles
        self._fetch = fetch
        self._universe = universe
        self._clock = clock or (lambda: datetime.now(UTC))
        self._send = send

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run.

        Raises:
            CandleCheckError: When there is no candle file, or SPY or more than
                ``MAX_BEHIND_SHARE`` of the members are still behind after the Yahoo fill.
        """
        home = ctx.home or desk_home()
        now = self._clock()
        day = last_closed_day(now).isoformat()
        try:
            reader = CandleReader(self._candles)
        except FileNotFoundError as exc:
            raise CandleCheckError("No candle file yet; download candles in Settings") from exc
        members = member_symbols(reader.symbols(), self._universe).symbols
        wanted = [*members, BENCHMARK]
        db_last = reader.last_days()
        store = MarketStore(home)
        try:
            store.trim_topup({s: d for s, d in db_last.items() if s in wanted})
            store.drop_unsettled_topup(_settled_utc)
            behind = _behind(wanted, db_last, store.topup_last_days(), day)
            if behind:
                self._fill(reader, store, [s for s in behind if s in db_last], db_last, day, now)
            still = _behind(wanted, db_last, store.topup_last_days(), day)
        finally:
            store.close()
        if behind:
            log.info("[Candles] %d stock(s) behind %s, %d filled from Yahoo Finance, "
                     "%d still behind", len(behind), day, len(behind) - len(still), len(still))
        else:
            log.info("[Candles] Daily candles are up to date for %s", day)
        late_members = [s for s in still if s != BENCHMARK]
        if BENCHMARK in still or len(late_members) > MAX_BEHIND_SHARE * len(members):
            detail = f"{len(still)} of {len(wanted)} stocks are still behind {day}"
            raise_alert(home, "candles", "", ctx.run_id, detail, now, self._send)
            raise CandleCheckError(f"Candles not up to date: {detail}")

    def _fill(self, reader: CandleReader, store: MarketStore, symbols: list[str],
              db_last: dict[str, str], day: str, now: datetime) -> None:
        if not symbols:
            return
        bars = reader.read(symbols)
        ibkr = {s: pd.DataFrame({"close": bars.closes[s], "volume": bars.volumes[s]}).dropna()
                for s in symbols if s in bars.closes.columns}
        start = min(date.fromisoformat(db_last[s]) for s in symbols) - LOOKBACK
        yahoo = self._fetch(symbols, start, date.fromisoformat(day))
        rows = topup_rows(ibkr, yahoo, date.fromisoformat(day),
                          now.astimezone(UTC).isoformat(timespec="seconds"))
        store.write_topup(rows)


def _settled_utc(day: str) -> str:
    """UTC ISO time from which a Yahoo bar for ``day`` is final (16:30 New York)."""
    moment = datetime.combine(date.fromisoformat(day), SETTLED, NY)
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def _behind(wanted: list[str], db_last: dict[str, str], copy_last: dict[str, str],
            day: str) -> list[str]:
    return [s for s in wanted if max(db_last.get(s, ""), copy_last.get(s, "")) < day]
