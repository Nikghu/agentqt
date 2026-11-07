"""
Module: MD-GUI-034.010.M03 — Floor sample data
Parent SRD: SRD-GUI-034.010
Also: SRD-GUI-034.047 — sample market tiles and breadth history
Also: SRD-GUI-034.054 — sample feed cards

Fixed sample products and rows behind the ``FloorData`` interface. A desk.db reader
replaces this later without any GUI change.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_feed import FeedCard

SAMPLE_TAG = "Sample data"

_PRODUCTS: tuple[ProductDescriptor, ...] = (
    ProductDescriptor(
        "ideas.top", "Top ideas", "table", ("table", "card"),
        ("symbol", "side", "score", "setup", "sector", "trigger"),
        {"side": ("long", "short")}, sample=True,
    ),
    ProductDescriptor(
        "regime.today", "Market regime", "card", ("card",),
        ("regime", "volatility", "fear"), sample=True,
    ),
    ProductDescriptor(
        "breadth.daily", "Breadth", "table", ("table",),
        ("measure", "value", "reading"), sample=True,
    ),
    ProductDescriptor(
        "sectors.rank", "Sector strength", "table", ("heatmap", "table"),
        ("sector", "rs", "quadrant", "change_5d"), {"quadrant": ("Leading", "Improving",
        "Weakening", "Lagging")}, sample=True,
    ),
    ProductDescriptor(
        "sectors.rrg", "Sector rotation", "table", ("rotation", "table"),
        ("sector", "rs_ratio", "rs_momentum", "quadrant"), sample=True,
    ),
    ProductDescriptor(
        "news.latest", "Latest news", "table", ("table",),
        ("time", "headline", "impact", "symbols"), {"impact": ("high", "medium", "low")},
        sample=True,
    ),
    ProductDescriptor(
        "calendar.week", "Calendar", "table", ("table",),
        ("date", "event", "importance"), {"importance": ("high", "medium", "low")}, sample=True,
    ),
    ProductDescriptor(
        "flow.leaders", "Flow leaders", "table", ("table",),
        ("symbol", "flow", "volume_x", "sector"), sample=True,
    ),
    ProductDescriptor(
        "market.tiles", "Market tiles", "tiles", ("tiles",), ("title", "value", "note"),
        sample=True,
    ),
    ProductDescriptor(
        "breadth.history", "Breadth · % above 50-day", "line", ("line", "table"),
        ("date", "value"), sample=True,
    ),
)

_IDEAS = [
    ("NVDA", "long", 92, "Breakout", "Technology", "Close above 131.40"),
    ("AAPL", "long", 88, "Pullback to 20 EMA", "Technology", "Hold above 226.10"),
    ("JPM", "long", 84, "Base breakout", "Financials", "Close above 248.00"),
    ("LLY", "long", 81, "Flag", "Health Care", "Break of 812.50"),
    ("XOM", "short", 79, "Failed breakout", "Energy", "Close below 112.30"),
    ("TSLA", "short", 76, "Lower high", "Consumer Discretionary", "Break of 238.40"),
    ("COST", "long", 74, "Tight range", "Consumer Staples", "Close above 905.00"),
    ("INTC", "short", 71, "Downtrend retest", "Technology", "Close below 20.80"),
]
_REGIME = [("regime", "Uptrend"), ("volatility", "Moderate"), ("fear", "Calm")]
_BREADTH = [
    ("Stocks above 50-day average", "64%", "Healthy"),
    ("Stocks above 200-day average", "71%", "Healthy"),
    ("Advancing vs declining", "1.8 : 1", "Positive"),
    ("New highs minus new lows", "+112", "Positive"),
]
_SECTORS = [
    ("Technology", 104.2, "Leading", 2.1),
    ("Financials", 102.6, "Leading", 1.4),
    ("Industrials", 101.1, "Improving", 0.8),
    ("Health Care", 99.4, "Improving", 0.5),
    ("Consumer Discretionary", 98.8, "Weakening", -0.4),
    ("Energy", 96.5, "Lagging", -1.7),
    ("Utilities", 97.2, "Lagging", -0.9),
]
_RRG = [
    ("Technology", 104.2, 101.8, "Leading"),
    ("Financials", 102.6, 100.9, "Leading"),
    ("Health Care", 99.4, 100.6, "Improving"),
    ("Consumer Discretionary", 98.8, 99.3, "Weakening"),
    ("Energy", 96.5, 98.7, "Lagging"),
]
_TILES = [
    ("Regime", "Uptrend", "trend · day 13"),
    ("Above 50-day", "64%", "+3 pts in 5 days"),
    ("New highs · lows", "38 · 7", "today"),
    ("Ideas", "6 L · 2 S", "today's list"),
    ("Leading sector", "Technology", "+4.3% vs SPY 1M"),
]
_HISTORY = [(f"day {i + 1}", v) for i, v in enumerate(
    (48, 47, 49, 46, 50, 52, 51, 54, 56, 55, 57, 59, 58, 61, 60, 62, 64))]
_NEWS = [
    ("09:12", "Chipmaker lifts full-year revenue outlook", "high", "NVDA, AMD"),
    ("08:47", "Bank earnings beat on trading income", "medium", "JPM, GS"),
    ("08:30", "Jobless claims fall to 215,000", "medium", "SPY"),
    ("07:55", "Oil slips as supply data surprises", "low", "XOM, CVX"),
    ("07:20", "Retailer confirms store expansion plan", "low", "COST"),
]
_CALENDAR = [
    ("Mon", "Consumer confidence", "low"),
    ("Tue", "Fed speakers", "medium"),
    ("Wed", "CPI inflation report", "high"),
    ("Thu", "Retail sales", "medium"),
    ("Fri", "Options expiry", "high"),
]
_FLOW = [
    ("NVDA", "Inflow", 2.4, "Technology"),
    ("JPM", "Inflow", 1.9, "Financials"),
    ("XOM", "Outflow", 1.6, "Energy"),
    ("AAPL", "Inflow", 1.3, "Technology"),
]

_FEED: tuple[dict[str, str], ...] = (
    {"time": "09:14", "author": "Lead 1", "kind": "info",
     "text": "Market opens in an uptrend with calm volatility."},
    {"time": "09:10", "author": "Expert 1", "kind": "idea",
     "text": "NVDA breakout idea scored 92; trigger above 131.40."},
    {"time": "09:05", "author": "Expert 2", "kind": "info",
     "text": "Technology and Financials lead the sector ranking."},
    {"time": "08:58", "author": "Expert 3", "kind": "approval",
     "text": "Buy 40 NVDA at 131.40 with stop 127.90. Approve?"},
    {"time": "08:40", "author": "Expert 1", "kind": "approval",
     "text": "Sell short 60 XOM at 112.30 with stop 114.60. Approve?"},
)


def _dicts(columns: Sequence[str], rows: Sequence[tuple[Any, ...]]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


class SampleFloorData:
    """``FloorData`` backed by fixed sample rows (every product is marked sample)."""

    def __init__(self) -> None:
        self._rows: dict[str, list[dict[str, Any]]] = {
            "ideas.top": _dicts(_PRODUCTS[0].columns, _IDEAS),
            "regime.today": _dicts(_PRODUCTS[1].columns, [tuple(v for _, v in _REGIME)]),
            "breadth.daily": _dicts(_PRODUCTS[2].columns, _BREADTH),
            "sectors.rank": _dicts(_PRODUCTS[3].columns, _SECTORS),
            "sectors.rrg": _dicts(_PRODUCTS[4].columns, _RRG),
            "news.latest": _dicts(_PRODUCTS[5].columns, _NEWS),
            "calendar.week": _dicts(_PRODUCTS[6].columns, _CALENDAR),
            "flow.leaders": _dicts(_PRODUCTS[7].columns, _FLOW),
            "market.tiles": _dicts(_PRODUCTS[8].columns, _TILES),
            "breadth.history": _dicts(_PRODUCTS[9].columns, _HISTORY),
        }

    def products(self) -> Sequence[ProductDescriptor]:
        """Return every sample product."""
        return _PRODUCTS

    def rows(self, product_id: str, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        """Return rows of ``product_id`` whose columns equal every filter value.

        An unknown product gives an empty list.
        """
        rows = self._rows.get(product_id, [])
        return [r for r in rows if all(str(r.get(k)) == v for k, v in filters.items())]


def sample_feed_items() -> list[dict[str, str]]:
    """Return sample AI feed items (time, author, text, kind info, idea or approval)."""
    return [dict(item) for item in _FEED]


def sample_feed_cards() -> list[FeedCard]:
    """Return the sample feed items as cards; approval items become Asks without a pick."""
    kinds = {"approval": "ask", "idea": "result", "info": "result"}
    return [FeedCard(kinds.get(i["kind"], "result"), i["author"],  # type: ignore[arg-type]
                     "Sample", None, i["text"]) for i in sample_feed_items()]
