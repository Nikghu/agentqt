"""
Module: MD-SCR-018.003.M37 — core/stock_context/_context.py
Parent SRD: SRD-SCR-018.003, SRD-SCR-018.005, SRD-SCR-018.006, SRD-SCR-019.003,
            SRD-SCR-019.004, SRD-SCR-020.003 – SRD-SCR-020.006

Earnings, sector, news and company levels, red flags, the SPY market regime and the context
block sent to the AI ranking. Pure functions; no network or database access.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from typing import Any

from us_swing.core.stock_context._company import AnalystChange, CompanyFacts
from us_swing.core.stock_context._news import Headline
from us_swing.core.stock_context._sector import GICS_TO_ETF, SectorMove, sector_moves

CONTEXT_KINDS: frozenset[str] = frozenset({
    "earnings", "sector", "news", "research",
    "surprise", "fundamentals", "short", "analysts", "review",
})
REGIME_SYMBOL = "SPY"
SECTOR_DAYS = 21
_EARNINGS_RED_DAYS = 5
_EARNINGS_YELLOW_DAYS = 10
_EDGE_RANKS = 3
_NEWS_RED_TONE = -0.3
_NEWS_GREEN_TONE = 0.3
NEGATIVE_NEWS_FLAG = "Negative news"
_SURPRISE_EDGE_PCT = 1.0
_SHORT_RED_PCT = 20.0
_ANALYST_DAYS = 30
_ANALYST_FLAG_DAYS = 7
_ANALYST_KEEP = 5
_Fields = tuple[dict[str, Any], tuple[str, ...]]
_REGIME_TEXT = {
    "risk-on": "risk-on, SPY above 50- and 200-day",
    "risk-off": "risk-off, SPY below 50- and 200-day",
    "mixed": "mixed, SPY between its 50- and 200-day",
    "": "unknown",
}


@dataclass(frozen=True, slots=True)
class StockContext:
    """What the AI and the result views know about one stock beyond its price."""

    earnings_date: str = ""
    earnings_days: int | None = None
    earnings_level: str = ""
    sector: str = ""
    sector_rank: int | None = None
    sector_count: int = 0
    sector_move_pct: float | None = None
    sector_level: str = ""
    market: str = ""
    news: tuple[Headline, ...] = ()
    news_tone: float | None = None
    news_level: str = ""
    eps_surprise_pct: float | None = None
    surprise_level: str = ""
    revenue_growth_pct: float | None = None
    margin_pct: float | None = None
    pe: float | None = None
    debt_to_equity: float | None = None
    short_pct: float | None = None
    days_to_cover: float | None = None
    short_level: str = ""
    analyst_changes: tuple[AnalystChange, ...] = ()
    analyst_target_pct: float | None = None
    analyst_level: str = ""
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Fields to save with a result row; flags are saved separately."""
        data = asdict(self)
        del data["flags"]
        return data


def earnings_level(days: int | None) -> str:
    """Red at 0–5 days to the report, yellow at 6–10, green beyond; "" without a date."""
    if days is None:
        return ""
    if days <= _EARNINGS_RED_DAYS:
        return "red"
    if days <= _EARNINGS_YELLOW_DAYS:
        return "yellow"
    return "green"


def news_level(tone: float | None) -> str:
    """Red at tone ≤ -0.3, yellow below 0, green at ≥ 0.3, else neutral; "" without a tone."""
    if tone is None:
        return ""
    if tone <= _NEWS_RED_TONE:
        return "red"
    if tone < 0:
        return "yellow"
    if tone >= _NEWS_GREEN_TONE:
        return "green"
    return "neutral"


def apply_news_tone(ctx: StockContext, tone: float | None) -> StockContext:
    """``ctx`` with the AI's news tone, its level and the "Negative news" flag (SRD-SCR-019.004)."""
    if tone is None:
        return ctx
    level = news_level(tone)
    flags = ctx.flags + ((NEGATIVE_NEWS_FLAG,) if level == "red" else ())
    return replace(ctx, news_tone=tone, news_level=level, flags=flags)


def surprise_level(pct: float | None) -> str:
    """Green above +1%, red below -1%, else neutral; "" without a surprise (SRD-SCR-020.003)."""
    if pct is None:
        return ""
    if pct > _SURPRISE_EDGE_PCT:
        return "green"
    if pct < -_SURPRISE_EDGE_PCT:
        return "red"
    return "neutral"


def _surprise_fields(facts: CompanyFacts) -> tuple[dict[str, Any], tuple[str, ...]]:
    pct = facts.eps_surprise_pct
    if pct is None:
        return {}, ()
    level = surprise_level(pct)
    flags = (f"EPS miss {pct:.1f}%",) if level == "red" else ()
    return {"eps_surprise_pct": pct, "surprise_level": level}, flags


def _fundamental_fields(facts: CompanyFacts) -> tuple[dict[str, Any], tuple[str, ...]]:
    fields = {"revenue_growth_pct": facts.revenue_growth_pct, "margin_pct": facts.margin_pct,
              "pe": facts.pe, "debt_to_equity": facts.debt_to_equity}
    return fields, ()


def _short_fields(facts: CompanyFacts) -> tuple[dict[str, Any], tuple[str, ...]]:
    pct = facts.short_pct
    if pct is None:
        return {}, ()
    red = pct > _SHORT_RED_PCT
    flags = (f"High short interest ({pct:.0f}% of float)",) if red else ()
    fields = {"short_pct": pct, "days_to_cover": facts.days_to_cover,
              "short_level": "red" if red else "neutral"}
    return fields, flags


def _analyst_fields(
    facts: CompanyFacts, today: date
) -> tuple[dict[str, Any], tuple[str, ...]]:
    start = (today - timedelta(days=_ANALYST_DAYS)).isoformat()
    recent_start = (today - timedelta(days=_ANALYST_FLAG_DAYS)).isoformat()
    changes = sorted((c for c in facts.changes if c.day >= start),
                     key=lambda c: c.day, reverse=True)[:_ANALYST_KEEP]
    target_pct = None
    if facts.target_mean is not None and facts.price is not None:
        target_pct = round((facts.target_mean / facts.price - 1) * 100, 1)
    if not changes and target_pct is None:
        return {}, ()
    recent = [c.action for c in changes if c.day >= recent_start]
    downs = recent.count("down")
    level = "red" if downs else "green" if "up" in recent else "neutral"
    flags = (f"{downs} downgrade{'' if downs == 1 else 's'}",) if downs else ()
    fields = {"analyst_changes": tuple(changes), "analyst_target_pct": target_pct,
              "analyst_level": level}
    return fields, flags


def _company_fields(
    facts: CompanyFacts, wanted: set[str], today: date
) -> tuple[dict[str, Any], tuple[str, ...]]:
    steps: dict[str, Callable[[CompanyFacts, date], _Fields]] = {
        "surprise": lambda f, _: _surprise_fields(f),
        "fundamentals": lambda f, _: _fundamental_fields(f),
        "short": lambda f, _: _short_fields(f),
        "analysts": _analyst_fields,
    }
    fields: dict[str, Any] = {}
    flags: tuple[str, ...] = ()
    for kind, step in steps.items():
        if kind in wanted:
            more, more_flags = step(facts, today)
            fields.update(more)
            flags += more_flags
    return fields, flags


def earnings_when(days: int) -> str:
    """"today", "in 1 day" or "in N days"."""
    if days == 0:
        return "today"
    return f"in {days} day{'' if days == 1 else 's'}"


def market_regime(spy_closes: Mapping[str, float]) -> str:
    """risk-on / risk-off / mixed from SPY's last close vs its 50- and 200-day averages."""
    closes = [spy_closes[day] for day in sorted(spy_closes)]
    if len(closes) < 200:
        return ""
    last = closes[-1]
    above = [last > sum(closes[-n:]) / n for n in (50, 200)]
    if all(above):
        return "risk-on"
    if not any(above):
        return "risk-off"
    return "mixed"


def _sector_fields(
    gics: str, moves: list[SectorMove]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    etf = GICS_TO_ETF.get(gics)
    ranked = [move.symbol for move in moves]
    if etf is None or etf not in ranked:
        return {}, ()
    rank = ranked.index(etf) + 1
    count = len(ranked)
    move = moves[rank - 1]
    level = "green" if rank <= _EDGE_RANKS else "red" if rank > count - _EDGE_RANKS else "neutral"
    flags = (f"Weak sector (#{rank} of {count})",) if level == "red" else ()
    fields = {"sector": move.name, "sector_rank": rank, "sector_count": count,
              "sector_move_pct": move.relative_pct, "sector_level": level}
    return fields, flags


def build_context(
    symbols: Iterable[str],
    kinds: Iterable[str],
    sectors: Mapping[str, str],
    closes: Mapping[str, Mapping[str, float]],
    earnings: Mapping[str, date | None],
    today: date,
    headlines: Mapping[str, Sequence[Headline]] | None = None,
    company: Mapping[str, CompanyFacts] | None = None,
) -> tuple[dict[str, StockContext], str]:
    """Context and flags per stock, plus the market regime (SRD-SCR-018.003–.005).

    Args:
        symbols: Stocks that reached Stage 3.
        kinds: Ticked context kinds ("earnings", "sector").
        sectors: Symbol → GICS sector name.
        closes: Daily closes keyed by ISO date for the sector ETFs, RSP and SPY.
        earnings: Symbol → next earnings date or None.
        today: The run date.
        headlines: Symbol → recent headlines, used when "news" is ticked.
        company: Symbol → company facts, used for the ticked company kinds.

    Returns:
        Symbol → ``StockContext`` and the regime ("" when SPY has too few closes).
    """
    wanted = set(kinds)
    regime = market_regime(closes.get(REGIME_SYMBOL, {}))
    moves = sector_moves(closes, SECTOR_DAYS)[0] if "sector" in wanted else []
    contexts: dict[str, StockContext] = {}
    for symbol in symbols:
        fields: dict[str, Any] = {"market": regime}
        flags: tuple[str, ...] = ()
        when = earnings.get(symbol) if "earnings" in wanted else None
        if when is not None:
            days = (when - today).days
            level = earnings_level(days)
            fields.update(earnings_date=when.isoformat(), earnings_days=days,
                          earnings_level=level)
            if level == "red":
                flags += (f"Earnings {earnings_when(days)}",)
        if moves:
            sector_fields, sector_flags = _sector_fields(sectors.get(symbol, ""), moves)
            fields.update(sector_fields)
            flags += sector_flags
        if "news" in wanted:
            fields["news"] = tuple((headlines or {}).get(symbol, ()))
        facts = (company or {}).get(symbol)
        if facts is not None:
            company_fields, company_flags = _company_fields(facts, wanted, today)
            fields.update(company_fields)
            flags += company_flags
        contexts[symbol] = StockContext(**fields, flags=flags)
    return contexts, regime


def surprise_text(pct: float) -> str:
    """"beat +6.2%", "miss -3.5%" or "in line +0.4%"."""
    word = {"green": "beat", "red": "miss"}.get(surprise_level(pct), "in line")
    return f"{word} {pct:+.1f}%"


def fundamentals_text(ctx: StockContext) -> str:
    """"revenue growth +62%, margin 55%, P/E 48.0, debt/equity 0.40" (missing parts left out)."""
    parts = []
    if ctx.revenue_growth_pct is not None:
        parts.append(f"revenue growth {ctx.revenue_growth_pct:+.0f}%")
    if ctx.margin_pct is not None:
        parts.append(f"margin {ctx.margin_pct:.0f}%")
    if ctx.pe is not None:
        parts.append(f"P/E {ctx.pe:.1f}")
    if ctx.debt_to_equity is not None:
        parts.append(f"debt/equity {ctx.debt_to_equity:.2f}")
    return ", ".join(parts)


def short_text(ctx: StockContext) -> str:
    """"short 1.1% of float, 2.7 days to cover"; "" without short data."""
    if ctx.short_pct is None:
        return ""
    cover = f", {ctx.days_to_cover:.1f} days to cover" if ctx.days_to_cover is not None else ""
    return f"short {ctx.short_pct:.1f}% of float{cover}"


def analysts_text(ctx: StockContext) -> str:
    """"analysts 30d: 1 up, 2 down; average target +14%"; "" without analyst data."""
    if not ctx.analyst_changes and ctx.analyst_target_pct is None:
        return ""
    actions = [c.action for c in ctx.analyst_changes]
    text = f"analysts 30d: {actions.count('up')} up, {actions.count('down')} down"
    if ctx.analyst_target_pct is not None:
        text += f"; average target {ctx.analyst_target_pct:+.0f}%"
    return text


def _line(symbol: str, ctx: StockContext) -> str:
    parts = [symbol]
    if ctx.earnings_days is not None:
        parts.append(f"earnings {earnings_when(ctx.earnings_days)} ({ctx.earnings_level})")
    if ctx.eps_surprise_pct is not None:
        parts.append(f"last EPS {surprise_text(ctx.eps_surprise_pct)} ({ctx.surprise_level})")
    if ctx.sector_rank is not None and ctx.sector_move_pct is not None:
        parts.append(f"{ctx.sector} #{ctx.sector_rank} of {ctx.sector_count}, "
                     f"{ctx.sector_move_pct:+.1f}% vs RSP ({ctx.sector_level})")
    if fundamentals := fundamentals_text(ctx):
        parts.append(fundamentals)
    if short := short_text(ctx):
        parts.append(f"{short} ({ctx.short_level})")
    if analysts := analysts_text(ctx):
        parts.append(f"{analysts} ({ctx.analyst_level})")
    parts.append("flags: " + ("; ".join(ctx.flags) if ctx.flags else "none"))
    news = [f"  news {h.published[5:10]} · {h.source} · {h.title}" for h in ctx.news]
    return "\n".join([" | ".join(parts), *news])


def context_text(contexts: Mapping[str, StockContext], regime: str) -> str:
    """The STOCK CONTEXT block for the AI prompt (SRD-SCR-018.006)."""
    header = f"=== STOCK CONTEXT (market: {_REGIME_TEXT.get(regime, regime)}) ==="
    return "\n".join([header, *(_line(sym, ctx) for sym, ctx in contexts.items())])
