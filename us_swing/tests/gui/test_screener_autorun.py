"""Unit tests: MD-SCR-007.010.M16 — gui/screener_panel.py daily auto-run
Refs: UT-SCR-004.007.M16.T01 – UT-SCR-004.007.M16.T06 (ISS-SCR-0003)
"""
from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from us_swing.gui import screener_panel as sp
from us_swing.gui.app_service import CandleDbStatus
from us_swing.screener.storage import ScreenerResultsStorage, ScreenerRunResult

LTD = "2026-11-02"


def _status(status: CandleDbStatus = CandleDbStatus.CURRENT, last: str = LTD) -> SimpleNamespace:
    return SimpleNamespace(status=status, last_trading_day=LTD, last_candle_date=last)


def _save(storage: ScreenerResultsStorage, candle_date: str | None, mode: str = "manual") -> None:
    storage.save_result(
        ScreenerRunResult(
            preset_id="p1",
            run_timestamp="2026-11-03T13:00:00Z",
            execution_mode=mode,
            candle_date=candle_date,
        ),
        "p1",
    )


@pytest.fixture
def storage(tmp_path: Path) -> ScreenerResultsStorage:
    return ScreenerResultsStorage(base_dir=tmp_path / "results")


@pytest.fixture
def panel(monkeypatch: pytest.MonkeyPatch, storage: ScreenerResultsStorage) -> sp.ScreenerPanel:
    """A ScreenerPanel with only the auto-run state set; Qt widgets are not built."""
    monkeypatch.setattr(
        "us_swing.gui.system_store.load_system_config",
        lambda: SimpleNamespace(scheduler_enabled=True),
    )
    monkeypatch.setattr(sp, "_in_auto_run_window", lambda: True)

    demo = MagicMock()
    demo.last_trading_day.return_value = datetime.date.fromisoformat(LTD)
    demo.has_candle_checkpoint.return_value = False
    demo.get_active_user.return_value = SimpleNamespace(user_id="u")
    mgr = MagicMock()
    mgr.list_admin_presets.return_value = [SimpleNamespace(id="p1", assigned_to=["u"])]
    mgr.list_user_presets.return_value = []

    p = sp.ScreenerPanel.__new__(sp.ScreenerPanel)
    p._demo = demo
    p._mgr = mgr
    p._storage = storage
    p._worker = None
    p._db_info = _status()  # cached status from an earlier check
    p._db_info_fresh = False
    p._db_check_requested_at = float("-inf")
    p._behind_warned_for = ""
    p._auto_run_queue = []
    p._run_preset_as = MagicMock()
    return p


def test_fresh_check_then_run(panel: sp.ScreenerPanel):
    """UT-SCR-004.007.M16.T01: a fresh candle check runs first, then the preset runs."""
    panel._maybe_auto_run()
    panel._demo.refresh_candle_db_status.assert_called_once()
    panel._run_preset_as.assert_not_called()

    panel._on_db_status_changed(_status())
    panel._run_preset_as.assert_called_once_with(preset_id="p1", manual=False)


def test_candles_behind_no_run_one_warning(panel: sp.ScreenerPanel):
    """UT-SCR-004.007.M16.T02: candles behind → no run and a single warning."""
    behind = _status(CandleDbStatus.PARTIAL, last="2026-10-30")
    panel._on_db_status_changed(behind)
    panel._on_db_status_changed(behind)

    panel._run_preset_as.assert_not_called()
    warnings = [c for c in panel._demo.log_message.emit.call_args_list if c.args[0] == "WARNING"]
    assert len(warnings) == 1
    assert warnings[0].args[1].startswith("[Screener]")
    assert "2026-10-30" in warnings[0].args[1]


def test_already_ran_on_latest_candles(panel: sp.ScreenerPanel, storage: ScreenerResultsStorage):
    """UT-SCR-004.007.M16.T03: a manual run on the latest candles counts as done."""
    _save(storage, candle_date=LTD, mode="manual")
    panel._maybe_auto_run()

    panel._demo.refresh_candle_db_status.assert_not_called()
    panel._run_preset_as.assert_not_called()


@pytest.mark.parametrize("old_date", ["2026-10-30", None])
def test_run_on_older_candles_runs_again(
    panel: sp.ScreenerPanel, storage: ScreenerResultsStorage, old_date: str | None
):
    """UT-SCR-004.007.M16.T04: a result on older candles, or with no date, is not done."""
    _save(storage, candle_date=old_date, mode="scheduled")
    panel._on_db_status_changed(_status())

    panel._run_preset_as.assert_called_once_with(preset_id="p1", manual=False)


def test_cached_status_not_trusted(panel: sp.ScreenerPanel):
    """UT-SCR-004.007.M16.T05: an old cached 'current' status never starts a run."""
    panel._maybe_auto_run()
    panel._maybe_auto_run()  # next tick before the check returns

    panel._run_preset_as.assert_not_called()
    panel._demo.refresh_candle_db_status.assert_called_once()


def test_outside_window_does_nothing(panel: sp.ScreenerPanel, monkeypatch: pytest.MonkeyPatch):
    """UT-SCR-004.007.M16.T06: outside 09:00–09:30 ET there is no check and no run."""
    monkeypatch.setattr(sp, "_in_auto_run_window", lambda: False)
    panel._on_db_status_changed(_status())

    panel._demo.refresh_candle_db_status.assert_not_called()
    panel._run_preset_as.assert_not_called()
