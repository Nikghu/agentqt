"""
Module: MD-MKT-007.001.M02 — market/report_page.py
Parent SRD: SRD-MKT-007.001
Also: SRD-MKT-007.002 (typed answer), SRD-MKT-007.005 (no answer keeps the last good
version), SRD-MKT-007.006 (feed brief), SRD-MKT-007.008 (log line)

The report page skill: turns the day's lead brief, picks and views into one HTML/CSS
page. Code cleans the page (``core.report_html``) before it is added as a new version
in ``canvas_pages``. The lead brief is read with plain SQL from the desk ``briefs``
table; it uses only ``core`` types and never imports the desk harness.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.report_html import MAX_PAGE_BYTES, clean_page
from us_swing.market.candles import CANDLE_DB
from us_swing.market.risk_check import views_text
from us_swing.market.setup_review import ideas_day, rule_regime, table
from us_swing.market.store import MarketStore

log = logging.getLogger(__name__)

KEY = "report_page"
VIEW_KEYS = ("regime_view", "sector_flow_view", "news_review")
_HTML_RULES = (
    "One HTML page body (no <html>, <head> or <body> tags) with one <style> block. Use "
    "headings, short paragraphs, tables and simple inline <svg> charts. No scripts, no event "
    "handlers, no links, no outside or local images or fonts, no url() in CSS. Images only "
    "as data:image/png, jpeg, gif or webp base64. Aim for 20 to 40 KB; never over 200 KB."
)


class ReportPage(BaseModel):
    """The model's answer for the report page skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=80, description="Short page title")
    html: str = Field(min_length=200, max_length=MAX_PAGE_BYTES, description=_HTML_RULES)


def lead_brief_text(store: MarketStore, day: str) -> str:
    """The newest lead brief text for ``day`` (morning, or evening before 2026-11-11)."""
    try:
        frame = store.read_frame("SELECT text FROM briefs WHERE kind IN ('morning', 'evening') "
                                 "AND data_day = ? ORDER BY id DESC LIMIT 1", (day,))
    except pd.errors.DatabaseError:
        return ""
    return str(frame["text"].iloc[0]) if not frame.empty else ""


def _picks(store: MarketStore, day: str) -> pd.DataFrame:
    return store.read_frame(
        "SELECT p.side, p.symbol, p.rank, p.reason, i.score, t.final_score AS final, i.setup, "
        "i.trigger, i.stop FROM lead_picks p LEFT JOIN ideas i ON i.date = p.date AND "
        "i.side = p.side AND i.symbol = p.symbol LEFT JOIN news_tags t ON t.date = p.date AND "
        "t.side = p.side AND t.symbol = p.symbol WHERE p.date = ? ORDER BY p.side, p.rank",
        (day,))


class ReportPageSkill:
    """The report page skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ("lead_brief",)
    answer = ReportPage

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the ideas are up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts; stale unless the day's ideas are fresh and a lead brief exists."""
        store = MarketStore(home)
        try:
            day, why = ideas_day(store, self._candles)
            if why:
                return Facts("", day, False, why)
            brief = lead_brief_text(store, day)
            if not brief:
                return Facts("", day, False, f"no lead brief for {day} yet")
            text = "\n\n".join([
                f"Data day: {day}",
                f"Regime by the rules: {rule_regime(store, day) or 'unknown'}",
                f"Lead brief:\n{brief}",
                f"Lead picks:\n{table(_picks(store, day))}",
                views_text(store, day, VIEW_KEYS),
                f"Page rules: {_HTML_RULES}",
            ])
            return Facts(text, day, True)
        finally:
            store.close()

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the page, clean it and add it as a new version.

        Without a valid answer, or when the cleaned page is empty or too big, nothing is
        stored and no brief is posted, so a later run on the same data day asks again.
        """
        day = facts.data_day
        page = ctx.ask(facts.text, ReportPage)
        if page is None:
            return []
        clean = clean_page(page.html)
        size = len(clean.html.encode("utf-8"))
        if not clean.html.strip() or size > MAX_PAGE_BYTES:
            log.warning("[Report] Page for %s was not saved: it is empty or over 200 KB "
                        "after cleaning", day)
            return []
        store = MarketStore(ctx.home)
        try:
            version = store.add_page(day, page.title, clean.html,
                                     datetime.now(UTC).isoformat(timespec="seconds"))
        finally:
            store.close()
        log.info("[Report] Page for %s saved as version %d: %d KB written, %d KB kept, "
                 "%d item(s) removed", day, version,
                 round(len(page.html.encode("utf-8")) / 1024), round(size / 1024), clean.removed)
        return [FeedItem("info", f"Report page ready: {page.title} (version {version})", day)]
