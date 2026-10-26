"""
Module: MD-GUI-024.003.M03 / MD-GUI-024.004.M04 / MD-GUI-024.006.M05 — Execution tab card tests
Parent SRD: SRD-GUI-024.003, .004, .005, .006
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

# QWebEngineWidgets DLL is unavailable in the test environment — stub it.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

import us_swing.data  # noqa: E402,F401  — load data before db (db ↔ data import cycle)
import us_swing.gui.strategies_pane as sp  # noqa: E402
from us_swing.execution.trade_cycle import (  # noqa: E402
    CycleSnapshot,
    PnlPoint,
    StrategyPnlSummary,
    TradeCycleState,
)
from us_swing.gui.active_cycles_panel import ActiveCyclesPanel  # noqa: E402
from us_swing.gui.strategy_pnl_chart import StrategyPnlCard, nice_ticks  # noqa: E402
from us_swing.gui.strategy_store import StrategyConfig  # noqa: E402


def _cfg(name: str) -> StrategyConfig:
    return StrategyConfig(name=name, mode="auto", capital_max=25, start_time="09:35",
                          end_time="15:45", start_date="2026-06-01", end_date="2026-12-31",
                          days=["Monday"], entry_condition="", exit_condition="")


def _demo() -> MagicMock:
    demo = MagicMock()
    demo.get_strategies_with_open_cycles.return_value = set()
    demo.get_open_symbols_for_strategy.return_value = []
    demo.get_strategy_pnl.return_value = StrategyPnlSummary()
    demo.get_viewing_uid.return_value = None
    demo.cycle_query.open_cycles_for_strategy.return_value = ()
    demo.cycle_query.closed_between.return_value = ()
    demo._strategy_engine = None
    return demo


# ── Tab filter (ActiveCyclesPanel) ────────────────────────────────────────────

def _snap(cycle_id: int, state: TradeCycleState) -> CycleSnapshot:
    return CycleSnapshot(cycle_id=cycle_id, strategy_id="S1", symbol=f"S{cycle_id}",
                         state=state, entry_price=10.0, entry_qty=1,
                         closed_at="2026-10-23T15:00:00" if state == "CLOSED" else None)


@pytest.fixture
def trades_panel(qtbot: QtBot) -> tuple[ActiveCyclesPanel, list[tuple[int, int]]]:
    query = MagicMock()
    query.open_cycles.return_value = (_snap(1, TradeCycleState.OPEN),
                                      _snap(2, TradeCycleState.OPEN))
    query.closed_between.return_value = (_snap(3, TradeCycleState.CLOSED),)
    pending = MagicMock()
    pending.list.return_value = []
    panel = ActiveCyclesPanel(
        cycle_query=query, cycle_cmd=MagicMock(), pending_store=pending,
        app_service=SimpleNamespace(viewing_uid=None, rex_counters=None),
        exit_executor=lambda *_: None, execute_executor=lambda *_: 1,
    )
    qtbot.addWidget(panel)
    counts: list[tuple[int, int]] = []
    panel.counts_changed.connect(lambda a, c: counts.append((a, c)))
    return panel, counts


def _hidden(panel: ActiveCyclesPanel) -> int:
    return sum(panel._table.isRowHidden(r) for r in range(panel.model.rowCount()))


def test_active_filter_hides_closed(
    trades_panel: tuple[ActiveCyclesPanel, list[tuple[int, int]]],
) -> None:
    """UT-GUI-024.003.M03.T01: Active filter hides closed rows and reports counts."""
    panel, counts = trades_panel
    panel.set_row_filter("active")
    assert _hidden(panel) == 1
    assert counts[-1] == (2, 1)


def test_closed_filter_shows_only_closed(
    trades_panel: tuple[ActiveCyclesPanel, list[tuple[int, int]]],
) -> None:
    """UT-GUI-024.003.M03.T02: Closed filter shows only closed rows."""
    panel, _ = trades_panel
    panel.set_row_filter("closed")
    assert _hidden(panel) == 2


# ── Strategies pane ───────────────────────────────────────────────────────────

def _pane(qtbot: QtBot, configs: list[StrategyConfig]) -> tuple[sp.StrategiesPane, Any]:
    with (
        patch.object(sp, "load_strategies", return_value=configs),
        patch.object(sp, "save_strategies") as save,
    ):
        pane = sp.StrategiesPane(_demo())
    qtbot.addWidget(pane)
    return pane, save


def test_list_and_detail(qtbot: QtBot) -> None:
    """UT-GUI-024.004.M04.T01: List rows and the first selection fill the detail."""
    pane, _ = _pane(qtbot, [_cfg("ST_AUTO"), _cfg("Trade1st")])

    assert pane.list.count() == 2
    assert pane.list.currentRow() == 0
    assert pane.title_lbl.text() == "ST_AUTO"
    assert pane.when_box.values["Entry window"].text() == "09:35 – 15:45"


def test_duplicate_unique_stopped(qtbot: QtBot) -> None:
    """UT-GUI-024.005.M04.T02: Duplicate saves a stopped copy with a unique name."""
    source = _cfg("ST")
    source.run_state = "RUNNING"
    with (
        patch.object(sp, "load_strategies", return_value=[source, _cfg("ST copy")]),
        patch.object(sp, "save_strategies") as save,
    ):
        pane = sp.StrategiesPane(_demo())
        qtbot.addWidget(pane)
        pane._on_duplicate(0)

    names = [c.name for c in pane._configs]
    assert names[-1] == "ST copy 2"
    assert pane._configs[-1].run_state == "STOPPED"
    assert source.run_state == "RUNNING"
    save.assert_called_once()
    assert pane.title_lbl.text() == "ST copy 2"


# ── P&L card ──────────────────────────────────────────────────────────────────

def test_pnl_card_empty(qtbot: QtBot) -> None:
    """UT-GUI-024.006.M05.T01: Empty summary shows the empty text and dashes."""
    card = StrategyPnlCard()
    qtbot.addWidget(card)
    card.show_summary(StrategyPnlSummary())

    assert card.chart.is_empty
    assert card.stats["Win rate"].text() == "—"


def test_pnl_card_values(qtbot: QtBot) -> None:
    """UT-GUI-024.006.M05.T02: Card shows total, trade count and win rate."""
    card = StrategyPnlCard()
    qtbot.addWidget(card)
    point = PnlPoint("2026-06-01T15:00:00", "AAPL", 412.6, 412.6)
    card.show_summary(StrategyPnlSummary(points=(point,), total=412.6, trades=38, wins=21,
                                         win_rate=0.55))

    assert card.total_lbl.text() == "+$412.60"
    assert "38 trades" in card.meta_lbl.text()
    assert card.stats["Win rate"].text().startswith("55%")


def test_pnl_range_asks_since(qtbot: QtBot) -> None:
    """UT-GUI-024.006.M05.T03: The 1W button asks the provider for the last 7 days."""
    card = StrategyPnlCard()
    qtbot.addWidget(card)
    asked: list[str | None] = []
    card.set_provider(lambda since: (asked.append(since), StrategyPnlSummary())[1])

    card.range_group.buttons[0].click()

    assert asked[0] is None  # All by default
    since = datetime.strptime(str(asked[-1]), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    assert abs(datetime.now(timezone.utc) - timedelta(days=7) - since) < timedelta(minutes=1)


def test_nice_ticks() -> None:
    """UT-GUI-024.006.M05.T04: Round y ticks."""
    assert nice_ticks(0, 412.6) == [0, 150, 300, 450]
