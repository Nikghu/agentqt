"""Tests for AI Desk v3 M7b tool requests in the lead chat: MD-MKT-010.003.M03
(market/lead_chat.py ``tool_hint``).

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

from pathlib import Path

import tests.desk.test_harness as th
from tests.market.test_lead_chat_sessions import NOW, _new, _skill, _Talk
from us_swing.core import desk_chat as dc
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.market import lead_chat as lc


def _on(home: Path, builder_on: bool = True, holder: bool = True) -> None:
    save_settings(DeskAiSettings(sessions_on=True, messages_on=True,
                                 tool_builder_on=builder_on), home)
    if holder:
        th.employee(home, "b-1", th.job("b-1", "Forge", "champion", "tool_builder"))


def _facts_seen(home: Path) -> str:
    sid = _new(home)
    dc.ask_question(home, "Can the desk build a gap tool?", NOW, session=sid)
    ctx = _Talk(home, [])
    skill = _skill()
    skill.act(ctx, skill.facts(home))
    return ctx.facts_seen


def test_tool_hint(tmp_path: Path) -> None:
    """UT-MKT-010.022.M03.T01: With sessions, messages and the tool builder on and a builder
    holder, the facts hold the hint to ask skill:tool_builder."""
    _on(tmp_path)
    seen = _facts_seen(tmp_path)
    assert lc.ASK_HINT in seen and lc.TOOL_HINT in seen
    assert '"skill:tool_builder"' in seen
    assert seen.index(lc.ASK_HINT) < seen.index(lc.TOOL_HINT)


def test_no_tool_hint(tmp_path: Path) -> None:
    """UT-MKT-010.022.M03.T02: With the tool builder off, or on with no holder, there is no tool
    hint."""
    off, alone = tmp_path / "off", tmp_path / "alone"
    _on(off, builder_on=False)
    _on(alone, holder=False)
    for home in (off, alone):
        assert lc.tool_hint(home) == ""
        seen = _facts_seen(home)
        assert lc.ASK_HINT in seen and lc.TOOL_HINT not in seen
