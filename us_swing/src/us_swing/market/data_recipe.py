"""
Module: MD-MKT-011.003.M04 — market/data_recipe.py
Parent SRD: SRD-MKT-011.003
Also: SRD-MKT-011.005 (asked product row), SRD-MKT-011.009 (log lines)

The data recipe skill: turns the Master's oldest open data request into a recipe from the
fixed menu. The answer holds only recipe fields; code checks the recipe before it is saved
as a proposed panel, so the model never writes SQL.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_data_asks import add_asked, open_request
from us_swing.core.desk_recipes import MENU, DataRecipe, check_recipe
from us_swing.data.market_calendar import ET

log = logging.getLogger(__name__)

KEY = "data_recipe"
NO_ANSWER = "The desk could not answer this request"
NO_FIT = "The menu cannot serve this request"
_RULES = (
    "Rules: pick one source; use only its columns; text columns take = or != only; "
    "number filters need a number; at most 8 columns, 5 filters and 100 rows. "
    "When the menu cannot serve the request, leave recipe empty and give the reason."
)


class DataRecipeAnswer(BaseModel):
    """The model's answer to one data request, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    recipe: DataRecipe | None = Field(description="The recipe, or null when it cannot be built")
    reason: str = Field(default="", max_length=300,
                        description="Why the menu cannot serve the request, when recipe is null")


def _now() -> datetime:
    return datetime.now(ET)


def _sectors(home: Path) -> list[str]:
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            rows = con.execute("SELECT sector FROM sector_daily WHERE date = "
                               "(SELECT MAX(date) FROM sector_daily) ORDER BY sector").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [str(r[0]) for r in rows]


def _menu_lines() -> list[str]:
    return [f"{src.label} ({key}): "
            + ", ".join(f"{name} ({kind})" for name, (_, kind) in src.columns.items())
            for key, src in MENU.items()]


class DataRecipeSkill:
    """Builds one asked panel each time the data employee is woken."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = DataRecipeAnswer

    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        """Set the clock; injectable for tests."""
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """The open request, the menu, the known values and the rules."""
        now = self._clock()
        day = now.date().isoformat()
        request = open_request(home, now)
        if request is None:
            return Facts("", day, False, "no open request")
        sectors = _sectors(home)
        text = "\n".join([
            f"Request #{request.id}: {request.text}", "",
            "Menu:", *_menu_lines(), "",
            "Known values:",
            "side: long, short",
            "status (ideas): list, watch",
            "status (pick results): no_fill, open, stop, target, time",
            f"sector: {', '.join(sectors) if sectors else '(none stored yet)'}", "",
            _RULES,
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the recipe, check it and save a proposed or failed panel; no feed item."""
        request = open_request(ctx.home, self._clock())
        if request is None:
            return []
        reply = ctx.ask(facts.text, DataRecipeAnswer)
        recipe: DataRecipe | None = None
        if reply is None:
            reason = NO_ANSWER
        elif reply.recipe is None:
            reason = reply.reason.strip() or NO_FIT
        elif why := check_recipe(reply.recipe):
            reason = f"The recipe did not pass the check: {why}"
        else:
            recipe, reason = reply.recipe, ""
        add_asked(ctx.home, request.id, recipe, reason, self._clock())
        if recipe is None:
            log.warning("[Data] Request %d failed: %s", request.id, reason)
        else:
            log.info("[Data] Request %d proposed: %s", request.id, recipe.title)
        return []
