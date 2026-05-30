"""
Module: MD-GUI-004.001.M01 test cases (FO-GUI-004)
Parent SRD: SRD-GUI-004.001

Unit tests for _StrategyTablePane._on_run() — SQUARING_OFF force-clear path.
Covers the fix shipped in RN-GUI-1.2.3-20260529.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# execution_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui.strategy_builder_dialog import StrategyConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _squaring_off_cfg(name: str = "TESTING") -> StrategyConfig:
    cfg = StrategyConfig(
        name=name,
        mode="manual",
        capital_max=25,
        start_time="09:30",
        end_time="15:30",
        start_date="2026-05-29",
        end_date="2026-11-29",
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        entry_condition="",
        exit_condition="",
    )
    cfg.strategy_signal["run_state"] = "SQUARING_OFF"
    return cfg


def _make_demo(open_syms: list[str]) -> MagicMock:
    demo = MagicMock()
    demo.strategy_status_changed = MagicMock()
    demo.strategy_status_changed.connect = MagicMock()
    demo.get_open_symbols_for_strategy.return_value = open_syms
    demo.reload_strategy_registry = MagicMock()
    demo.get_strategies_with_open_cycles.return_value = set()
    demo._strategy_engine = None
    return demo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pane_no_cycles(qapp):
    """_StrategyTablePane with one SQUARING_OFF strategy and no open cycles."""
    import us_swing.gui.execution_panel as ep

    cfg = _squaring_off_cfg()
    demo = _make_demo([])

    with (
        patch.object(ep, "load_strategies", return_value=[cfg]),
        patch.object(ep, "save_strategies") as mock_save,
    ):
        pane = ep._StrategyTablePane(demo)
        yield pane, cfg, mock_save


@pytest.fixture()
def pane_with_cycles(qapp):
    """_StrategyTablePane with one SQUARING_OFF strategy that still has open cycles."""
    import us_swing.gui.execution_panel as ep

    cfg = _squaring_off_cfg()
    demo = _make_demo(["AAPL", "MSFT"])

    with (
        patch.object(ep, "load_strategies", return_value=[cfg]),
        patch.object(ep, "save_strategies") as mock_save,
    ):
        pane = ep._StrategyTablePane(demo)
        yield pane, cfg, mock_save


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOnRunSquaringOff:
    def test_force_stopped_when_no_open_cycles(self, pane_no_cycles):
        """UT-GUI-004.001.M01.T06: SQUARING_OFF → STOPPED when no open cycles remain."""
        pane, cfg, mock_save = pane_no_cycles

        pane._on_run(0)

        assert cfg.strategy_signal["run_state"] == "STOPPED"
        mock_save.assert_called_once()

    def test_stays_squaring_off_when_cycles_remain(self, pane_with_cycles):
        """UT-GUI-004.001.M01.T07: SQUARING_OFF stays locked while open cycles exist."""
        pane, cfg, mock_save = pane_with_cycles

        pane._on_run(0)

        assert cfg.strategy_signal["run_state"] == "SQUARING_OFF"
        mock_save.assert_not_called()
