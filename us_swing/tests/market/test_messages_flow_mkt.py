"""End-to-end test of the M1 send-back fix loop in one morning run (MD-MKT-005.012.M07).

Employee names here are made up: no skill may depend on who uses it.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from tests.market import test_p5b_defaults as defaults
from tests.market.p5b_support import Env, query, set_ideas, set_regime
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_registry import fill_registry
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply


def test_fix_loop_in_one_run(p5b: Env) -> None:
    """UT-MKT-005.022.M07.T05: Fix loop in one run; the lead runs after with the new levels."""
    defaults._CANDLES[0] = p5b.candles
    for number, source in enumerate(("emp-001", "emp-002", "emp-003", "emp-004", "emp-005"), 1):
        defaults._hire(p5b.home, number, source)
    fill_registry(p5b.home, datetime.now(UTC))
    set_regime(p5b, "Choppy")
    set_ideas(p5b, [("long", "ZZA", "list", 1, "Tech", 50.0, 44.3)])  # stop 11.4% away
    sectors = [str(r[0]) for r in query(p5b.home, "SELECT sector FROM sector_daily "
                                        "WHERE date = ? ORDER BY rank", (p5b.day,))]
    grade = {"side": "long", "symbol": "ZZA", "grade": "B", "note": "Decent setup near trigger"}
    answers = {
        "Tester A": {"regime": "Choppy", "confidence": 0.6, "reasons": ["Breadth is mixed"],
                     "brief": "Trend is flat and breadth is mixed, so the market looks choppy."},
        "Tester B": {"favour": sectors[:1], "avoid": sectors[-1:],
                     "rotation": "Money is moving into the leading sector",
                     "brief": "The leading sector gets the money, so favour it for now."},
        "Tester C": {"grades": [grade]},
        "Tester D": {"vetoes": []},
        "Tester E": {"picks": [{"side": "long", "symbol": "ZZA",
                                "reason": "Best setup that passed the risk check"}],
                     "morning": "The market is mixed today; one idea passed every check and "
                                "it is the only pick for tomorrow."},
    }
    order: list[str] = []

    def caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
        name = next(n for n in answers if n in system)
        order.append(name)
        body = dict(answers[name])
        found = re.search(r"#(\d+) send_back from", user)
        if name == "Tester C" and found:
            body["messages"] = [{"type": "reply", "parent": int(found.group(1)),
                                 "verdict": {"result": "done"},
                                 "data": {"schema": "idea_fix.v1",
                                          "rows": [["long", "ZZA", 50.0, 46.15]]}}]
        return Reply(json.dumps(body), 500, 50, 0.0)

    step = EmployeesStep(lambda: defaults_skills(), lambda: [],
                         lambda: DeskAiSettings(claude_on=True, claude_model="claude-haiku-5-5",
                                                messages_on=True),
                         lambda: "", caller)
    step(StepContext(7, "manual", datetime.now(UTC), p5b.home))

    assert query(p5b.home, "SELECT verdict, by, reason FROM risk_check") == [
        ("pass", "code", "Fixed in round 1")]
    assert query(p5b.home, "SELECT status, round, stop FROM idea_fixes") == [("pass", 1, 46.15)]
    assert query(p5b.home, "SELECT symbol FROM lead_picks") == [("ZZA",)]
    assert order[-1] == "Tester E" and order.count("Tester C") == 2
    types = [r[0] for r in query(p5b.home, "SELECT type FROM messages ORDER BY id")]
    assert types == ["send_back", "reply"]


def defaults_skills() -> dict[str, str]:
    """The five P5b skills, built on the test market's candles."""
    return {"regime_view": "tests.market.test_p5b_defaults:_regime",
            "sector_flow_view": "tests.market.test_p5b_defaults:_sector",
            "setup_review": "tests.market.test_p5b_defaults:_setup",
            "risk_check": "tests.market.test_p5b_defaults:_risk",
            "lead_brief": "tests.market.test_p5b_defaults:_lead"}
