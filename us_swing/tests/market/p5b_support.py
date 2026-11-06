"""Helpers shared by the P5b market tests: a desk copy, plain-INSERT idea factory, fake context.

Employee names here are made up: no skill may depend on who uses it.
"""
from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# (side, symbol, status, rank, sector, trigger, stop)
Idea = tuple[str, str, str, int, str, float | None, float | None]


@dataclass(frozen=True)
class Env:
    """A private copy of the synthetic market: candles file, desk folder, newest data day."""

    candles: Path
    home: Path
    day: str


@dataclass
class FakeCtx:
    """Context whose ask returns a fixed answer (or ``None``) and keeps what it was shown."""

    home: Path
    answer: Any
    asked: list[str] = field(default_factory=list)

    def ask(self, facts: str, schema: type[Any]) -> Any:
        self.asked.append(facts)
        return self.answer


def query(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    """Read rows from the copy's desk.db."""
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def execute(home: Path, sql: str, params: tuple[Any, ...] = ()) -> None:
    """Run one plain write on the copy's desk.db."""
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute(sql, params)
    finally:
        con.close()


def copy_env(market: tuple[Path, Path], tmp_path: Path) -> Env:
    """Copy the shared synthetic market into ``tmp_path``."""
    candles, home = market
    shutil.copytree(home, tmp_path / "desk")
    shutil.copy(candles, tmp_path / "candles.db")
    new_home = tmp_path / "desk"
    (day,) = query(new_home, "SELECT MAX(date) FROM regime_snapshot")[0]
    return Env(tmp_path / "candles.db", new_home, str(day))


def set_regime(env: Env, regime: str) -> None:
    """Set the rule regime of the newest day."""
    execute(env.home, "UPDATE regime_snapshot SET regime = ? WHERE date = ?", (regime, env.day))


def set_ideas(env: Env, ideas: Sequence[Idea]) -> None:
    """Replace the newest day's ideas, with score parts and two reasons for listed ones."""
    con = sqlite3.connect(env.home / "desk.db")
    try:
        with con:
            con.execute("DELETE FROM ideas WHERE date = ?", (env.day,))
            con.execute("DELETE FROM idea_reasons WHERE date = ?", (env.day,))
            for side, symbol, status, rank, sector, trigger, stop in ideas:
                con.execute(
                    'INSERT INTO ideas (date, side, symbol, status, rank, score, sector, setup, '
                    '"trigger", stop) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (env.day, side, symbol, status, rank, 80.0 - rank, sector, "Breakout",
                     trigger, stop))
                if status != "list":
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO stock_score (date, symbol, side, score, rs_part, "
                    "flow_part, setup_part, sector_part, regime_part, penalty) "
                    "VALUES (?, ?, ?, ?, 15, 12, 14, 10, 8, 0)",
                    (env.day, symbol, side, 80.0 - rank))
                for seq, reason in enumerate(("Strong relative strength", "Money flowing in")):
                    con.execute("INSERT INTO idea_reasons VALUES (?, ?, ?, ?, ?)",
                                (env.day, side, symbol, seq, reason))
    finally:
        con.close()


def listed(side: str, prefix: str, count: int, sector: str = "Tech") -> list[Idea]:
    """``count`` listed ideas of one side that break no limit (trigger 50, stop 6% away)."""
    stop = 47.0 if side == "long" else 53.0
    return [(side, f"{prefix}{i:02d}", "list", i, sector, 50.0, stop)
            for i in range(1, count + 1)]
