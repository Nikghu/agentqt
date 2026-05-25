"""
Module: MD-EXE-011.001.M08 — QtEventBus
Parent SRD: SRD-EXE-011.015
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from us_swing.execution.strategy_engine._events import StrategyEvent

log = logging.getLogger(__name__)


class QtEventBus(QObject):
    """Thread-safe Qt signal bridge for StrategyEvent dispatch."""

    event_published = pyqtSignal(object)

    def publish(self, event: StrategyEvent) -> None:
        log.debug("[EventBus] %s", type(event).__name__)
        self.event_published.emit(event)
