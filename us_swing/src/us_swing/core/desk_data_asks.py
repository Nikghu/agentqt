"""
Module: MD-MKT-011.001.M01 — core/desk_data_asks.py
Parent SRD: SRD-MKT-011.001
Also: SRD-MKT-011.005 (asked product rows), SRD-MKT-011.006 (decisions)

Data requests from the Floor catalog and the desk's asked products, in ``desk.db``. The GUI
adds requests (with one ``data_request`` event each) and decisions; the desk adds one asked
product per request. Both tables are append-only.
Shared by the GUI and the desk; this module imports neither ``desk``, ``market`` nor ``gui``.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import post_event
from us_swing.core.desk_hiring import _APPROVALS
from us_swing.core.desk_recipes import DataRecipe, check_recipe

log = logging.getLogger(__name__)

MAX_REQUEST = 300
OPEN_FOR = timedelta(hours=2)
FAILED_FOR = timedelta(days=1)
KIND = "data_product"
DECISIONS = ("approve", "reject")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_requests (id INTEGER PRIMARY KEY, created TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS asked_products (
    id INTEGER PRIMARY KEY, created TEXT, request_id INTEGER UNIQUE, state TEXT, title TEXT,
    recipe TEXT, reason TEXT
);
CREATE TRIGGER IF NOT EXISTS data_requests_no_update BEFORE UPDATE ON data_requests
BEGIN SELECT RAISE(ABORT, 'data_requests is append-only'); END;
CREATE TRIGGER IF NOT EXISTS data_requests_no_delete BEFORE DELETE ON data_requests
BEGIN SELECT RAISE(ABORT, 'data_requests is append-only'); END;
CREATE TRIGGER IF NOT EXISTS asked_products_no_update BEFORE UPDATE ON asked_products
BEGIN SELECT RAISE(ABORT, 'asked_products is append-only'); END;
CREATE TRIGGER IF NOT EXISTS asked_products_no_delete BEFORE DELETE ON asked_products
BEGIN SELECT RAISE(ABORT, 'asked_products is append-only'); END;
"""
_PRODUCT_SQL = (
    "SELECT p.id, p.created, p.request_id, r.text, p.state, p.title, p.recipe, p.reason "
    "FROM asked_products p JOIN data_requests r ON r.id = p.request_id"
)


@dataclass(frozen=True)
class DataRequest:
    """One Master data request."""

    id: int
    created: str
    text: str


@dataclass(frozen=True)
class AskedProduct:
    """The desk's answer to one request: proposed with a recipe, or failed with a reason."""

    id: int
    created: str
    request_id: int
    request: str
    state: str
    title: str
    recipe: DataRecipe | None
    reason: str


def _open(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.executescript(_SCHEMA + _APPROVALS)
    return con


def _recipe(text: object) -> DataRecipe | None:
    try:
        recipe = DataRecipe.model_validate_json(str(text))
    except ValidationError:
        return None
    return None if check_recipe(recipe) else recipe


def _products(home: Path, where: str, args: tuple[object, ...] = ()) -> list[AskedProduct]:
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        rows = con.execute(f"{_PRODUCT_SQL} WHERE {where} ORDER BY p.id", args).fetchall()
    finally:
        con.close()
    return [AskedProduct(int(i), str(c), int(q), str(t), str(s), str(ti or ""),
                         _recipe(rc) if s == "proposed" else None, str(why or ""))
            for i, c, q, t, s, ti, rc, why in rows]


def ask_data(home: Path, text: str, now: datetime) -> int:
    """Save a Master data request and post its event; return the request id.

    Raises:
        ValueError: When the text is empty or longer than 300 characters.
    """
    text = text.strip()
    if not text or len(text) > MAX_REQUEST:
        raise ValueError("a request needs 1 to 300 characters")
    con = _open(home)
    try:
        with con:
            cur = con.execute("INSERT INTO data_requests (created, text) VALUES (?, ?)",
                              (now.isoformat(timespec="seconds"), text))
        rid = int(cur.lastrowid or 0)
    finally:
        con.close()
    post_event(home, "data_request", now.date().isoformat(), now, run_id=rid)
    return rid


def open_request(home: Path, now: datetime) -> DataRequest | None:
    """The oldest request without an asked product that is not older than 2 hours."""
    if not (home / DB_NAME).exists():
        return None
    con = _open(home)
    try:
        rows = con.execute("SELECT id, created, text FROM data_requests WHERE id NOT IN "
                           "(SELECT request_id FROM asked_products) ORDER BY id").fetchall()
    finally:
        con.close()
    asked = [DataRequest(int(i), str(c), str(t)) for i, c, t in rows]
    return next((r for r in asked if now - datetime.fromisoformat(r.created) <= OPEN_FOR), None)


def add_asked(home: Path, request_id: int, recipe: DataRecipe | None, reason: str,
              now: datetime) -> int:
    """Save the desk's answer: proposed when ``recipe`` is given, else failed with ``reason``."""
    state = "proposed" if recipe is not None else "failed"
    con = _open(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO asked_products (created, request_id, state, title, recipe, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now.isoformat(timespec="seconds"), request_id, state,
                 recipe.title if recipe else "", recipe.model_dump_json() if recipe else "",
                 "" if recipe else reason))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


_DECIDED = f"SELECT subject FROM approvals WHERE kind = '{KIND}'"


def waiting_products(home: Path) -> list[AskedProduct]:
    """Proposed products with no decision yet, oldest first."""
    return [p for p in _products(home, f"p.state = 'proposed' AND CAST(p.id AS TEXT) NOT IN "
                                       f"({_DECIDED})") if p.recipe is not None]


def approved_products(home: Path) -> list[AskedProduct]:
    """Proposed products the Master approved, oldest first."""
    return [p for p in _products(home, f"p.state = 'proposed' AND CAST(p.id AS TEXT) IN "
                                       f"({_DECIDED} AND decision = 'approve')")
            if p.recipe is not None]


def failed_products(home: Path, now: datetime) -> list[AskedProduct]:
    """Failed requests of the last day, newest first."""
    failed = _products(home, "p.state = 'failed'")
    return [p for p in failed[::-1] if now - datetime.fromisoformat(p.created) <= FAILED_FOR]


def decide_product(home: Path, product_id: int, decision: str, now: datetime) -> str:
    """Record the Master's decision on a proposed product; an empty string means saved."""
    if decision not in DECISIONS:
        return "unknown decision"
    found = _products(home, "p.id = ? AND p.state = 'proposed'", (product_id,))
    if not found:
        return "not found"
    try:
        con = _open(home)
        try:
            with con:
                con.execute("BEGIN IMMEDIATE")
                if con.execute(f"{_DECIDED} AND subject = ?", (str(product_id),)).fetchone():
                    return "already decided"
                con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (now.isoformat(timespec="seconds"), KIND, str(product_id),
                             decision, found[0].title))
        finally:
            con.close()
    except sqlite3.Error as exc:
        log.error("[AI Desk] Could not save the panel decision: %s", exc)
        return "could not save"
    log.info("[AI Desk] Asked panel %s %s", found[0].title,
             "approved" if decision == "approve" else "rejected")
    return ""
