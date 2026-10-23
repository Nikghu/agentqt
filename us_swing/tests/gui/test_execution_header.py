"""
Module: MD-GUI-024.001.M01 — Execution page header tests
Parent SRD: SRD-GUI-024.001
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from pytestqt.qtbot import QtBot

from us_swing.data.models import ConnectionStatus
from us_swing.gui import execution_header as eh
from us_swing.gui.strategy_store import StrategyConfig


class _Svc(QObject):
    viewing_changed = pyqtSignal()
    positions_updated = pyqtSignal()
    strategy_status_changed = pyqtSignal(str, str)
    feed_status_changed = pyqtSignal(str)
    screener_results_updated = pyqtSignal(list)

    def __init__(self, mode: str = "paper", pnls: tuple[float, ...] = (),
                 with_open: set[str] | None = None) -> None:
        super().__init__()
        self._mode = mode
        self._with_open = with_open or set()
        cycles = [SimpleNamespace(current_pnl_usd=p, user_id=1) for p in pnls]
        self.cycle_query = SimpleNamespace(open_cycles=lambda: cycles)
        self.connection_status = ConnectionStatus.DISCONNECTED

    def get_users(self) -> list[Any]:
        return []

    def get_latest_screener_results(self) -> list[Any]:
        return []

    def get_viewing_uid(self) -> int | None:
        return None

    def get_strategies_with_open_cycles(self) -> set[str]:
        return self._with_open

    def get_active_user(self) -> Any:
        return SimpleNamespace(mode=self._mode)


def _cfg(name: str, run_state: str = "STOPPED") -> StrategyConfig:
    return StrategyConfig(name=name, mode="auto", capital_max=0, start_time="09:35",
                          end_time="15:45", start_date="2026-06-01", end_date="2026-12-31",
                          days=[], entry_condition="", exit_condition="", run_state=run_state)


@pytest.fixture(autouse=True)
def _strategies(monkeypatch: pytest.MonkeyPatch) -> None:
    configs = [_cfg("A", "RUNNING"), _cfg("B"), _cfg("C")]
    monkeypatch.setattr(eh, "load_strategies", lambda: configs)


def test_chips_running_and_unrealised(qtbot: QtBot) -> None:
    """UT-GUI-024.001.M01.T01: Chips show running count and unrealised P&L."""
    header = eh.ExecutionHeader(_Svc(pnls=(10.0, -4.0), with_open={"B"}))  # type: ignore[arg-type]
    qtbot.addWidget(header)

    assert "<b>2</b> of <b>3</b>" in header.running_chip.text()
    assert "+$6.00" in header.unrealised_chip.text()


@pytest.mark.parametrize(("mode", "name"), [("paper", "Paper broker"), ("live", "IBKR live")])
def test_broker_chip_follows_mode(qtbot: QtBot, mode: str, name: str) -> None:
    """UT-GUI-024.001.M01.T02: Broker chip follows the active user's mode."""
    header = eh.ExecutionHeader(_Svc(mode=mode))  # type: ignore[arg-type]
    qtbot.addWidget(header)

    assert name in header.broker_chip.text()


def test_charts_button_label(qtbot: QtBot) -> None:
    """UT-GUI-024.008.M01.T03: The header charts button names the next action."""
    header = eh.ExecutionHeader(_Svc())  # type: ignore[arg-type]
    qtbot.addWidget(header)
    assert header.charts_btn.text() == "Hide charts"
    header.show_charts_state(True)
    assert header.charts_btn.text() == "Show charts"
