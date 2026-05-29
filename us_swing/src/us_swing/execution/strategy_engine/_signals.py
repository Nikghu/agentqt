"""
Module: MD-EXE-011.001.M06 — TradeSignal & Action
Parent SRD: SRD-EXE-011.008
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class Action(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


def _new_signal_id() -> str:
    return f"sig-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class TradeSignal:
    action: Action
    symbol: str
    strategy_id: str
    entry_price: float | None = None
    stop_loss: float | None = None
    target: float | None = None
    qty_recommended: int = 0
    user_id: int = 0
    reason: str | None = None
    signal_id: str = field(default_factory=_new_signal_id)
    schema_version: int = 2


class PendingSignalSink(Protocol):
    """Narrow sink interface used by the engine router; concrete
    implementation lives outside the engine package to keep it GUI-free."""

    def add(self, signal: TradeSignal) -> None: ...
