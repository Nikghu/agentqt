"""
Module: MD-DSK-001.021.M07 — core/desk_steps.py
Parent SRD: SRD-DSK-001.021
Also: SRD-DSK-001.022 — score proof runner path
Also: SRD-DSK-002.001, SRD-DSK-003.001 — skill list, default employee files and the "AI employees" step
Also: SRD-MKT-007.007 — report page skill path
Also: SRD-DSK-006.009 — "Weekly report" step path
Also: MD-MKT-010.007.M04 — ``lead_chat`` skill path (SRD-MKT-010.007)
Also: MD-MKT-011.008.M06 — ``data_recipe`` skill path (SRD-MKT-011.008)
Also: MD-MKT-009.001.M06 — "Pick results" step path (SRD-MKT-009.001)
Also: MD-MKT-012.004.M02 — ``lesson_reflect`` skill path (SRD-MKT-012.004)
Also: SRD-DSK-003.023 — watcher pass path; MD-MKT-013.011.M04 — ``watch_flag`` and ``checkin_note``
skill paths (SRD-MKT-013.011)

The list of steps the desk runs, loaded by import path, so ``desk`` never imports
the tools (such as ``market``) that provide the steps.
"""
from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from us_swing.core.desk_contract import DeskStep

log = logging.getLogger(__name__)

STEP_PATHS: tuple[str, ...] = (
    "us_swing.market.candle_check:CandleCheckStep",  # first: SRD-MKT-001.013
    "us_swing.market.step:RegimeStep",
    "us_swing.market.sector_step:SectorStep",
    "us_swing.market.idea_step:IdeaStep",
    "us_swing.market.news_step:NewsStep",
    "us_swing.market.pick_results:PickResultsStep",
    "us_swing.desk.employees_step:EmployeesStep",
    "us_swing.desk.weekly_report:WeeklyReportStep",
)
# Skills by key (named by what they do, never by who does them).
SKILL_PATHS: dict[str, str] = {
    "regime_view": "us_swing.market.regime_view:RegimeViewSkill",
    "sector_flow_view": "us_swing.market.sector_view:SectorViewSkill",
    "setup_review": "us_swing.market.setup_review:SetupReviewSkill",
    "risk_check": "us_swing.market.risk_check:RiskCheckSkill",
    "lead_brief": "us_swing.market.lead_brief:LeadBriefSkill",
    "news_review": "us_swing.market.news_review:NewsReviewSkill",
    "report_page": "us_swing.market.report_page:ReportPageSkill",
    "lead_chat": "us_swing.market.lead_chat:LeadChatSkill",
    "data_recipe": "us_swing.market.data_recipe:DataRecipeSkill",
    "lesson_reflect": "us_swing.market.lesson_reflect:LessonReflectSkill",
    "watch_flag": "us_swing.market.watch_flag:WatchFlagSkill",
    "checkin_note": "us_swing.market.checkin_note:CheckinNoteSkill",
    "setup_tuning": "us_swing.market.setup_tuning:SetupTuningSkill",
    "post_mortem": "us_swing.market.post_mortem:PostMortemSkill",
}
# Packages whose ``employees/`` folder holds default employee files to copy on first run.
DEFAULT_EMPLOYEE_PACKAGES: tuple[str, ...] = ("us_swing.market",)
PROOF_PATH = "us_swing.market.proof:run_proof"
WATCH_PATH = "us_swing.market.watch:run_watch"


def load_steps(paths: Sequence[str] = STEP_PATHS) -> list[DeskStep]:
    """Import and build each step in ``paths`` (``"module:Class"``), in order.

    A step that cannot be loaded is logged and left out, so one bad step never
    stops the desk.
    """
    steps: list[DeskStep] = []
    for path in paths:
        module_name, _, class_name = path.partition(":")
        try:
            step = getattr(importlib.import_module(module_name), class_name)()
        except Exception as exc:  # noqa: BLE001 — any load failure only drops that step
            log.warning("[Desk] Could not load desk step %s: %s", path, exc)
            continue
        steps.append(step)
    return steps


def load_proof(path: str = PROOF_PATH) -> Callable[[Path], str | None]:
    """Import the score proof runner (``"module:function"``); given the desk folder it returns
    the report text, or ``None`` when there is no data.
    """
    module_name, _, func_name = path.partition(":")
    runner: Callable[[Path], str | None] = getattr(importlib.import_module(module_name), func_name)
    return runner


def load_watch(path: str = WATCH_PATH) -> Callable[[Path, datetime], int]:
    """Import the market watcher pass (``"module:function"``); given the desk folder and the
    time it returns the number of new flags (SRD-DSK-003.023)."""
    module_name, _, func_name = path.partition(":")
    runner: Callable[[Path, datetime], int] = getattr(importlib.import_module(module_name),
                                                      func_name)
    return runner
