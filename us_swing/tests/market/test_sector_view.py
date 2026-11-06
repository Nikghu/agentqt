"""Tests for MD-MKT-005.006.M04 — market/sector_view.py (sector/flow view skill)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx, query
from us_swing.core.desk_agents import Facts
from us_swing.market.sector_view import SectorView, SectorViewSkill, schema_for

ROTATION = "Money is moving from Energy into Tech this week"
BRIEF = "Tech leads the market and money is flowing in, so favour it for now."


def _sectors(env: Env) -> list[str]:
    rows = query(env.home, "SELECT sector FROM sector_daily WHERE date = ? ORDER BY rank",
                 (env.day,))
    return [str(r[0]) for r in rows]


def _view(env: Env, favour: list[str], avoid: list[str]) -> SectorView:
    return schema_for(_sectors(env)).model_validate(
        {"favour": favour, "avoid": avoid, "rotation": ROTATION, "brief": BRIEF})


def test_facts_built(p5b: Env) -> None:
    """UT-MKT-005.006.M04.T01: Facts hold ranks, quadrants, moves and flow per side; fresh."""
    facts = SectorViewSkill(p5b.candles).facts(p5b.home)
    assert facts.fresh and facts.data_day == p5b.day
    days = query(p5b.home, "SELECT DISTINCT date FROM sector_daily ORDER BY date DESC LIMIT 5")
    assert len(days) == 5 and all(str(d[0]) in facts.text for d in days)
    quadrants = {str(r[0]) for r in query(p5b.home, "SELECT quadrant FROM sector_daily")}
    assert any(q in facts.text for q in quadrants)
    for part in ("Regime by the rules: Downtrend", "rank", "rel_1m_pct", "rel_3m_pct",
                 "Money flow today", "avg_flow", "long", "short", "Sector names you may use"):
        assert part in facts.text
    assert all(s in facts.text for s in _sectors(p5b))


def test_stale_sectors(p5b: Env) -> None:
    """UT-MKT-005.006.M04.T02: A newer SPY candle than the sector day makes the facts stale."""
    con = sqlite3.connect(p5b.candles)
    con.execute("INSERT INTO price_1d VALUES ('SPY', '2099-01-02T00:00:00', 1, 1, 1, 1, 1)")
    con.commit()
    con.close()
    facts = SectorViewSkill(p5b.candles).facts(p5b.home)
    assert not facts.fresh
    assert p5b.day in facts.why_stale and "2099-01-02" in facts.why_stale


def test_valid_sector_view() -> None:
    """UT-MKT-005.007.M04.T01: Two sectors to favour and one to avoid make a SectorView."""
    view = schema_for(["Tech", "Energy", "Health Care"]).model_validate(
        {"favour": ["Tech", "Energy"], "avoid": ["Health Care"], "rotation": ROTATION,
         "brief": BRIEF})
    assert isinstance(view, SectorView)
    assert (view.favour, view.avoid) == (["Tech", "Energy"], ["Health Care"])


@pytest.mark.parametrize("data", [
    {"favour": ["Mining"]}, {"avoid": ["Mining"]},
    {"favour": ["A", "B", "C", "D"]}, {"favour": ["A"], "avoid": ["A"]},
    {"brief": "x" * 401}, {"favour": []}, {"rotation": "short"},
])
def test_bad_sector_view(data: dict[str, Any]) -> None:
    """UT-MKT-005.007.M04.T02: Unknown sector, 4 favour, a sector twice or a long brief fail."""
    base = {"favour": ["A", "B"], "avoid": ["C"], "rotation": ROTATION, "brief": BRIEF}
    with pytest.raises(ValidationError):
        schema_for(["A", "B", "C", "D"]).model_validate({**base, **data})


def test_stored_and_in_feed(p5b: Env) -> None:
    """UT-MKT-005.008.M04.T01: Run twice, one row holds the second view; info feed item."""
    skill = SectorViewSkill(p5b.candles)
    facts = skill.facts(p5b.home)
    first, second = _sectors(p5b)[:2]
    skill.act(FakeCtx(p5b.home, _view(p5b, [first], [second])), facts)
    items = skill.act(FakeCtx(p5b.home, _view(p5b, [second], [first])), facts)
    assert [(i.kind, i.text, i.data_day) for i in items] == [("info", BRIEF, p5b.day)]
    rows = query(p5b.home, "SELECT date, favour, avoid, rotation, brief FROM sector_view")
    assert len(rows) == 1
    assert (rows[0][0], json.loads(rows[0][1]), json.loads(rows[0][2])) == (
        p5b.day, [second], [first])


def test_no_answer(p5b: Env) -> None:
    """UT-MKT-005.008.M04.T02: No valid answer gives no row and no feed item."""
    skill = SectorViewSkill(p5b.candles)
    assert skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home)) == []
    assert query(p5b.home, "SELECT * FROM sector_view") == []


def test_no_sector_rows(p5b: Env) -> None:
    """UT-MKT-005.008.M04.T03: Facts for a day without sectors give no question and no item."""
    ctx = FakeCtx(p5b.home, None)
    assert SectorViewSkill(p5b.candles).act(ctx, Facts("x", "1999-01-01", True)) == []
    assert ctx.asked == []
