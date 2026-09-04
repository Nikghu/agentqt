"""Module: universe/store.py — S&P 500 universe flat-file cache.

Infrastructure layer — no GUI, no PyQt, no framework imports.

Storage location
────────────────
    ~/.usswing/sp500_universe.csv   — ticker list (Symbol, IbkrSymbol, Name, Sector)
    ~/.usswing/sp500_meta.json      — fetch metadata (last_fetched, source, count)
    ~/.usswing/sp500_ibkr.csv       — IBKR-qualified contracts (Symbol, IbkrSymbol, conid, PrimaryExch)

Refresh policy
──────────────
    Data is considered stale after REFRESH_DAYS (default 7).
    On load, if the CSV is missing or stale, it is downloaded automatically.
    IbkrSymbol replaces '.' with ' ' (e.g. BRK.B → BRK B) for IBKR compatibility.

IBKR qualification
──────────────────
    A separate offline script (scripts/qualify_sp500_ibkr.py) reads sp500_universe.csv,
    connects to TWS on port 7497, qualifies all 500 Stock contracts via SMART exchange,
    and writes ~/.usswing/sp500_ibkr.csv.

Public API
──────────
    get_meta()                          -> Sp500Meta
    refresh()                           -> list[Sp500Record]
    load_sp500(*, force_refresh=False)  -> list[Sp500Record]
    ibkr_csv_exists()                   -> bool
    load_ibkr_universe()                -> list[dict]
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# ── Storage paths (same directory as users.json / system.json) ────────────────

_APP_DIR      = Path.home() / ".usswing"
_UNIVERSE_CSV = _APP_DIR / "sp500_universe.csv"
_META_JSON    = _APP_DIR / "sp500_meta.json"
_IBKR_CSV     = _APP_DIR / "sp500_ibkr.csv"

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
REFRESH_DAYS   = 7


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class Sp500Record:
    symbol:      str   # Original Wikipedia symbol  (e.g. BRK.B)
    ibkr_symbol: str   # IBKR-compatible symbol     (e.g. BRK B)
    name:        str
    sector:      str
    market_cap:  float | None = None  # USD, fetched from yfinance after Wikipedia fetch


@dataclass
class Sp500Meta:
    last_fetched: datetime | None   # UTC
    source:       str
    count:        int

    def is_stale(self) -> bool:
        if self.last_fetched is None:
            return True
        age = datetime.now(tz=timezone.utc) - self.last_fetched
        return age > timedelta(days=REFRESH_DAYS)

    def age_str(self) -> str:
        if self.last_fetched is None:
            return "never fetched"
        age = datetime.now(tz=timezone.utc) - self.last_fetched
        days = age.days
        hours = age.seconds // 3600
        if days:
            return f"{days}d {hours}h ago"
        return f"{hours}h ago"


# ── Meta helpers ──────────────────────────────────────────────────────────────

def _load_meta() -> Sp500Meta:
    if not _META_JSON.exists():
        return Sp500Meta(last_fetched=None, source=_WIKIPEDIA_URL, count=0)
    try:
        data = json.loads(_META_JSON.read_text(encoding="utf-8"))
        ts_str = data.get("last_fetched")
        ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc) if ts_str else None
        return Sp500Meta(
            last_fetched = ts,
            source       = data.get("source", _WIKIPEDIA_URL),
            count        = int(data.get("count", 0)),
        )
    except Exception as exc:
        log.warning("universe.store: could not read meta — %s", exc)
        return Sp500Meta(last_fetched=None, source=_WIKIPEDIA_URL, count=0)


def _save_meta(count: int) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "last_fetched": datetime.now(tz=timezone.utc).isoformat(),
        "source":       _WIKIPEDIA_URL,
        "count":        count,
    }
    _META_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _load_from_csv() -> list[Sp500Record]:
    records: list[Sp500Record] = []
    with _UNIVERSE_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mc_raw = row.get("MarketCap", "")
            try:
                mc: float | None = float(mc_raw) if mc_raw else None
            except ValueError:
                mc = None
            records.append(Sp500Record(
                symbol      = row["Symbol"],
                ibkr_symbol = row["IbkrSymbol"],
                name        = row["Name"],
                sector      = row["Sector"],
                market_cap  = mc,
            ))
    return records


def _save_to_csv(records: list[Sp500Record]) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _UNIVERSE_CSV.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Symbol", "IbkrSymbol", "Name", "Sector", "MarketCap"])
        w.writeheader()
        for r in records:
            w.writerow({
                "Symbol":      r.symbol,
                "IbkrSymbol":  r.ibkr_symbol,
                "Name":        r.name,
                "Sector":      r.sector,
                "MarketCap":   "" if r.market_cap is None else str(r.market_cap),
            })
    tmp.replace(_UNIVERSE_CSV)   # atomic rename


# ── Wikipedia fetch ───────────────────────────────────────────────────────────

def _fetch_from_wikipedia() -> list[Sp500Record]:
    """Download S&P 500 table from Wikipedia and return normalised records."""
    import io
    import urllib.request

    import pandas as pd   # already a project dependency

    log.info("universe.store: fetching from Wikipedia …")

    # Wikipedia returns 403 for requests without a browser-like User-Agent.
    req = urllib.request.Request(
        _WIKIPEDIA_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; usswing-universe-fetcher/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html_bytes = resp.read()

    tables = pd.read_html(io.BytesIO(html_bytes), attrs={"id": "constituents"})
    df = tables[0]

    # Wikipedia column names vary slightly across revisions
    col_map: dict[str, str] = {}
    for col in df.columns:
        low = col.lower()
        if "symbol" in low:
            col_map[col] = "symbol"
        elif "security" in low or "name" in low:
            col_map[col] = "name"
        elif "gics sector" in low or "sector" in low:
            col_map[col] = "sector"
    df = df.rename(columns=col_map)

    records: list[Sp500Record] = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        if not sym:
            continue
        ibkr_sym = sym.replace(".", " ")    # BRK.B → BRK B for IBKR compatibility
        records.append(Sp500Record(
            symbol      = sym,
            ibkr_symbol = ibkr_sym,
            name        = str(row.get("name", "")).strip(),
            sector      = str(row.get("sector", "")).strip(),
        ))
    log.info("universe.store: fetched %d records", len(records))

    # Fetch market caps in parallel via yfinance (background-safe).
    caps = _fetch_market_caps([r.symbol for r in records])
    for r in records:
        r.market_cap = caps.get(r.symbol)
    log.info("universe.store: market caps collected")
    return records


def _fetch_market_caps(symbols: list[str]) -> dict[str, float | None]:
    """Return {symbol: market_cap_usd} for each symbol via yfinance fast_info.

    Uses a thread pool (20 workers) so 500 tickers complete in ~15–30 seconds.
    Failures are silently mapped to None.
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor

    from us_swing.core.symbols import yahoo_symbol

    def _one(sym: str) -> tuple[str, float | None]:
        try:
            mc = yf.Ticker(yahoo_symbol(sym)).fast_info.market_cap
            return sym, float(mc) if mc else None
        except Exception:
            return sym, None

    with ThreadPoolExecutor(max_workers=20) as ex:
        return dict(ex.map(_one, symbols))


# ── Public API ────────────────────────────────────────────────────────────────

def get_meta() -> Sp500Meta:
    """Return current metadata (last_fetched timestamp, source, count)."""
    return _load_meta()


def refresh() -> list[Sp500Record]:
    """Force-download from Wikipedia, save CSV + meta, return records."""
    records = _fetch_from_wikipedia()
    _save_to_csv(records)
    _save_meta(len(records))
    log.info("universe.store: saved %d records to %s", len(records), _UNIVERSE_CSV)
    return records


def load_sp500(*, force_refresh: bool = False) -> list[Sp500Record]:
    """Return the S&P 500 universe, refreshing from Wikipedia if stale or missing.

    Args:
        force_refresh: If True, always re-download even if data is fresh.

    The file is considered stale after ``REFRESH_DAYS`` days (default 7).
    """
    meta = _load_meta()

    if force_refresh or meta.is_stale() or not _UNIVERSE_CSV.exists():
        reason = "forced" if force_refresh else ("missing" if not _UNIVERSE_CSV.exists() else f"stale ({meta.age_str()})")
        log.info("universe.store: refreshing — %s", reason)
        return refresh()

    log.info(
        "universe.store: loaded from cache (%s, %d tickers, last fetched %s)",
        _UNIVERSE_CSV, meta.count, meta.age_str(),
    )
    return _load_from_csv()


def ibkr_csv_exists() -> bool:
    """Return True if the IBKR-qualified CSV (~/.usswing/sp500_ibkr.csv) exists."""
    return _IBKR_CSV.exists()


def load_ibkr_universe() -> list[dict]:
    """Load the IBKR-qualified universe CSV (Symbol, IbkrSymbol, conid, PrimaryExch).

    Returns an empty list if the file does not exist yet
    (run scripts/qualify_sp500_ibkr.py first).
    """
    if not _IBKR_CSV.exists():
        return []
    records: list[dict] = []
    with _IBKR_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            records.append(dict(row))
    return records
