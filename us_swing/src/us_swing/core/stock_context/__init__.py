"""
Module: MD-SCR-018.003.M37 — core/stock_context/__init__.py
Parent SRD: SRD-SCR-018.002 – SRD-SCR-018.006, SRD-SCR-019.002 – SRD-SCR-019.006

Public surface of the stock context package used by the AI ranking (screener)
and the sector views (gui).
"""
from __future__ import annotations

from us_swing.core.stock_context._context import (
    CONTEXT_KINDS,
    NEGATIVE_NEWS_FLAG,
    REGIME_SYMBOL,
    StockContext,
    apply_news_tone,
    build_context,
    context_text,
    earnings_level,
    earnings_when,
    market_regime,
    news_level,
)
from us_swing.core.stock_context._earnings import EarningsLookup
from us_swing.core.stock_context._news import Headline, NewsLookup
from us_swing.core.stock_context._research import Research, research_picks
from us_swing.core.stock_context._sector import (
    GICS_TO_ETF,
    RANGE_DAYS,
    SECTOR_BENCHMARK,
    SECTOR_ETFS,
    SECTOR_SYMBOLS,
    SectorMove,
    sector_moves,
)

__all__ = [
    "CONTEXT_KINDS",
    "NEGATIVE_NEWS_FLAG",
    "GICS_TO_ETF",
    "RANGE_DAYS",
    "REGIME_SYMBOL",
    "SECTOR_BENCHMARK",
    "SECTOR_ETFS",
    "SECTOR_SYMBOLS",
    "EarningsLookup",
    "Headline",
    "NewsLookup",
    "Research",
    "SectorMove",
    "StockContext",
    "apply_news_tone",
    "build_context",
    "context_text",
    "earnings_level",
    "earnings_when",
    "market_regime",
    "news_level",
    "research_picks",
    "sector_moves",
]
