"""
Module: MD-DSK-006.004.M19 — desk/shadow.py
Parent SRD: SRD-DSK-006.004
Also: SRD-DSK-006.005 (shadow ends after 14 data days), SRD-DSK-006.010 (log lines)

A shadow employee answers the same facts as its skill's holder, but its answer is only
checked and recorded (tries marked shadow). The skill's ``act`` is never called, so no
views, picks, briefs or events come from a shadow.
"""
from __future__ import annotations

import logging

from us_swing.core.desk_agents import Facts
from us_swing.desk.gateway import Gateway
from us_swing.desk.recorder import Recorder
from us_swing.desk.registry import Hire

log = logging.getLogger(__name__)

SHADOW_DAYS = 14


def run_shadow(hire: Hire, facts: Facts, gateway: Gateway, recorder: Recorder) -> bool:
    """Ask once for ``facts.data_day`` and record the answer; return True when asked."""
    spec = hire.spec
    days = recorder.shadow_days(spec.id)
    if len(days) >= SHADOW_DAYS:
        log.info("[Hiring] %s finished the shadow and waits for a decision", spec.name)
        return False
    if facts.data_day in days:
        log.info("[Hiring] %s already answered in shadow for %s", spec.name, facts.data_day)
        return False
    gateway.ask(facts.text, hire.skill.answer)
    done = len(days) + 1
    if done == SHADOW_DAYS:
        log.info("[Hiring] %s finished the shadow and is ready for a decision", spec.name)
    else:
        log.info("[Hiring] %s answered in shadow for %s (day %d of %d)", spec.name,
                 facts.data_day, done, SHADOW_DAYS)
    return True
