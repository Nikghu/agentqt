"""
Module: MD-MKT-001.005.M03 — market/vix.py
Parent SRD: SRD-MKT-001.005

Daily VIX and VIX3M closes from Yahoo Finance.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

import pandas as pd

log = logging.getLogger(__name__)

TICKERS = {"^VIX": "vix", "^VIX3M": "vix3m"}

Downloader = Callable[[list[str], date], pd.DataFrame]


def _yahoo_closes(tickers: list[str], start: date) -> pd.DataFrame:
    import yfinance as yf  # type: ignore[import-untyped]  # noqa: PLC0415 — slow import

    raw = yf.download(
        tickers, start=start.isoformat(), interval="1d", progress=False,
        auto_adjust=False, threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    closes = raw["Close"]
    return closes if isinstance(closes, pd.DataFrame) else closes.to_frame(tickers[0])


def fetch_vix(start: date, downloader: Downloader | None = None) -> pd.DataFrame:
    """Return daily ``vix`` and ``vix3m`` closes from ``start``, indexed by date.

    Any failure is logged and gives an empty frame, so the caller carries on without VIX.
    """
    try:
        closes = (downloader or _yahoo_closes)(list(TICKERS), start)
    except Exception as exc:  # noqa: BLE001 — network or parsing failure must not stop the step
        log.warning("[Regime] Could not download VIX from Yahoo Finance: %s", exc)
        return pd.DataFrame(columns=list(TICKERS.values()))
    if closes.empty:
        return pd.DataFrame(columns=list(TICKERS.values()))
    out = closes.rename(columns=TICKERS).reindex(columns=list(TICKERS.values()))
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    return out.dropna(how="all")
