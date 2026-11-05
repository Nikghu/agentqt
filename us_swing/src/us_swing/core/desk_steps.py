"""
Module: MD-DSK-001.021.M07 — core/desk_steps.py
Parent SRD: SRD-DSK-001.021

The list of steps the desk runs, loaded by import path, so ``desk`` never imports
the tools (such as ``market``) that provide the steps.
"""
from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence

from us_swing.core.desk_contract import DeskStep

log = logging.getLogger(__name__)

STEP_PATHS: tuple[str, ...] = (
    "us_swing.market.step:RegimeStep",
    "us_swing.market.sector_step:SectorStep",
    "us_swing.market.idea_step:IdeaStep",
)


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
