"""
Module: MD-DSK-001.021.M07 — core/desk_steps.py
Parent SRD: SRD-DSK-001.021
Also: SRD-DSK-001.022 — score proof runner path
Also: SRD-DSK-002.001, SRD-DSK-003.001 — skill list, default employee files and the "AI employees" step
Also: SRD-MKT-007.007 — report page skill path
Also: SRD-DSK-006.009 — "Weekly report" step path

The list of steps the desk runs, loaded by import path, so ``desk`` never imports
the tools (such as ``market``) that provide the steps.
"""
from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from us_swing.core.desk_contract import DeskStep

log = logging.getLogger(__name__)

STEP_PATHS: tuple[str, ...] = (
    "us_swing.market.step:RegimeStep",
    "us_swing.market.sector_step:SectorStep",
    "us_swing.market.idea_step:IdeaStep",
    "us_swing.market.news_step:NewsStep",
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
}
# Packages whose ``employees/`` folder holds default employee files to copy on first run.
DEFAULT_EMPLOYEE_PACKAGES: tuple[str, ...] = ("us_swing.market",)
PROOF_PATH = "us_swing.market.proof:run_proof"


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
