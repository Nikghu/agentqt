"""
Module: MD-MKT-011.004.M03 — core/desk_recipes.py
Parent SRD: SRD-MKT-011.004

Safe data recipes for asked Floor panels. A recipe picks one source from a fixed menu, its
columns, filters, sort and row limit. Code checks every recipe against the menu and runs it
read-only on the latest data day; table and column names come only from the menu and filter
values are bound as parameters, so no model text is ever run as SQL.
Shared by the GUI and the desk; this module imports neither ``desk``, ``market`` nor ``gui``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_contract import DB_NAME

MAX_ROWS = 100
Op = Literal["=", "!=", ">", ">=", "<", "<="]
SourceKey = Literal["scores", "ideas", "stock_rs", "sectors", "pick_results"]
_TEXT_OPS = ("=", "!=")


@dataclass(frozen=True)
class Source:
    """One menu source: its label, ``FROM`` text, day column and columns by name."""

    label: str
    table: str
    day: str
    columns: dict[str, tuple[str, str]]


def _plain(table: str, text: tuple[str, ...], numbers: tuple[str, ...]) -> dict[str, tuple[str, str]]:
    cols = {c: (f"{table}.{c}", "text") for c in text}
    cols.update({c: (f"{table}.{c}", "number") for c in numbers})
    return cols


MENU: dict[str, Source] = {
    "scores": Source(
        "Scores",
        "stock_score s LEFT JOIN stock_rs r ON r.date = s.date AND r.symbol = s.symbol",
        "s.date",
        {**_plain("s", ("symbol", "side", "setup"),
                  ("score", "trigger", "stop", "rs_part", "flow_part", "setup_part",
                   "sector_part", "regime_part", "penalty")),
         "sector": ("r.sector", "text")},
    ),
    "ideas": Source("Ideas", "ideas", "ideas.date", _plain(
        "ideas", ("symbol", "side", "status", "sector", "setup"),
        ("rank", "score", "trigger", "stop"))),
    "stock_rs": Source("Stock RS", "stock_rs", "stock_rs.date", _plain(
        "stock_rs", ("symbol", "sector"), ("score", "rs_rating", "sector_rank", "sector_size"))),
    "sectors": Source("Sectors", "sector_daily", "sector_daily.date", _plain(
        "sector_daily", ("sector", "quadrant"),
        ("rank", "rel_1m", "rel_3m", "rel_6m", "rs_ratio", "rs_momentum", "members"))),
    "pick_results": Source("Pick results", "pick_results", "pick_results.date", _plain(
        "pick_results", ("symbol", "side", "status", "entry_day", "exit_day"),
        ("entry", "exit", "r"))),
}


class RecipeFilter(BaseModel):
    """One filter: a menu column, a compare sign and a value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    column: str = Field(min_length=1, max_length=40)
    op: Op
    value: str | float


class DataRecipe(BaseModel):
    """A data recipe chosen from the menu; ``check_recipe()`` must pass before it runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=60, description="Short panel title")
    source: SourceKey
    columns: list[str] = Field(min_length=1, max_length=8)
    filters: list[RecipeFilter] = Field(default_factory=list, max_length=5)
    sort: str | None = None
    descending: bool = True
    limit: int = Field(default=20, ge=1, le=MAX_ROWS)


def _is_number(value: str | float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def check_recipe(recipe: DataRecipe) -> str:
    """Return why ``recipe`` does not fit the menu, or an empty string when it does."""
    cols = MENU[recipe.source].columns
    seen: set[str] = set()
    for name in recipe.columns:
        if name not in cols:
            return f"unknown column {name}"
        if name in seen:
            return f"column {name} twice"
        seen.add(name)
    for f in recipe.filters:
        if f.column not in cols:
            return f"unknown filter column {f.column}"
        kind = cols[f.column][1]
        if kind == "text" and f.op not in _TEXT_OPS:
            return f"{f.column} takes = or != only"
        if kind == "number" and not _is_number(f.value):
            return f"{f.column} needs a number"
    if recipe.sort is not None and recipe.sort not in cols:
        return f"unknown sort column {recipe.sort}"
    return ""


def _sql(recipe: DataRecipe) -> tuple[str, list[object]]:
    src = MENU[recipe.source]
    pick = ", ".join(f"{src.columns[c][0]} AS {c}" for c in recipe.columns)
    day_table = src.day.split(".")[0]
    day_from = src.table if day_table == "s" else day_table
    where = [f"{src.day} = (SELECT MAX({src.day}) FROM {day_from})"]
    params: list[object] = []
    for f in recipe.filters:
        where.append(f"{src.columns[f.column][0]} {f.op} ?")
        params.append(f.value)
    sql = f"SELECT {pick} FROM {src.table} WHERE {' AND '.join(where)}"
    if recipe.sort is not None:
        expr = src.columns[recipe.sort][0]
        sql += f" ORDER BY {expr} IS NULL, {expr} {'DESC' if recipe.descending else 'ASC'}"
    params.append(min(recipe.limit, MAX_ROWS))
    return sql + " LIMIT ?", params


def _cell(value: object) -> object:
    return round(value, 2) if isinstance(value, float) else value


def run_recipe(home: Path, recipe: DataRecipe) -> list[dict[str, Any]]:
    """Run ``recipe`` read-only on the latest data day; ``[]`` when there is no data.

    Raises:
        ValueError: When the recipe does not pass ``check_recipe()``.
    """
    why = check_recipe(recipe)
    if why:
        raise ValueError(why)
    path = home / DB_NAME
    if not path.exists():
        return []
    sql, params = _sql(recipe)
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [{c: _cell(v) for c, v in zip(recipe.columns, row, strict=True)} for row in rows]


def _value(value: str | float) -> str:
    return f"{value:g}" if _is_number(value) else str(value)


def recipe_words(recipe: DataRecipe) -> str:
    """The recipe in plain words, for the approval card."""
    parts = [MENU[recipe.source].label, ", ".join(recipe.columns)]
    if recipe.filters:
        parts.append(", ".join(f"{f.column} {f.op} {_value(f.value)}" for f in recipe.filters))
    if recipe.sort is not None:
        parts.append(f"{recipe.sort} {'high to low' if recipe.descending else 'low to high'}")
    parts.append(f"up to {recipe.limit} rows")
    return " · ".join(parts)
