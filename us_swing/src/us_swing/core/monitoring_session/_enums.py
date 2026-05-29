"""
Module: MD-EXE-009.001.M01 — core/monitoring_session/_enums.py
Parent SRD: SRD-EXE-009.012
"""
from __future__ import annotations

from enum import Enum


class TradeOrigin(str, Enum):
    SYSTEM = "system"
    MANUAL = "manual"


class Side(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
