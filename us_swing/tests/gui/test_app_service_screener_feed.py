"""
Module: MD-GUI-004.001.M01 — tests (ISS-GUI-0004)
Parent SRD: SRD-GUI-004.009

The Execution feed takes screener results only from presets that still exist
and have at least one assigned user. A manual run of an unassigned preset
used to show its stocks in Filtered Stocks and send them to the engine.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from us_swing.gui.app_service import AppService
from us_swing.screener.manager import PresetManager
from us_swing.screener.preset import Preset, PresetType
from us_swing.screener.storage import ScreenerResultsStorage, ScreenerRunResult


@pytest.fixture()
def base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path / ".usswing" / "screener_results"


def _save_result(base: Path, preset_id: str, symbol: str) -> None:
    ScreenerResultsStorage(base).save_result(
        ScreenerRunResult(
            preset_id=preset_id,
            run_timestamp="2026-10-22T14:00:00Z",
            execution_mode="manual",
            results={symbol: {"passed": True, "score": 1.0}},
        ),
        preset_id,
    )


def _add_preset(base: Path, preset_id: str, name: str, assigned_to: list[str]) -> None:
    preset = Preset(
        id=preset_id, name=name, preset_type=PresetType.COMPOSITE,
        is_admin=True, assigned_to=assigned_to,
    )
    PresetManager(base).create_preset(preset, "1", is_admin_user=True)


def _feed() -> list[tuple[str, str]]:
    fake = SimpleNamespace(_active_uid=1, _manual_pick_entries=list)
    entries = AppService.get_latest_screener_results(fake)  # type: ignore[arg-type]
    return [(e.symbol, e.screener_name) for e in entries]


def test_assigned_preset_reaches_feed(base: Path) -> None:
    """UT-GUI-004.001.M01.T08: a preset with assigned users feeds Execution."""
    _add_preset(base, "p1", "Momentum", ["1"])
    _save_result(base, "p1", "AAPL")

    assert _feed() == [("AAPL", "Momentum")]


def test_unassigned_preset_excluded(base: Path) -> None:
    """UT-GUI-004.001.M01.T09: a preset with no assigned users is skipped."""
    _add_preset(base, "p1", "Momentum", ["1"])
    _save_result(base, "p1", "AAPL")
    _add_preset(base, "p2", "Test", [])
    _save_result(base, "p2", "MSFT")

    assert _feed() == [("AAPL", "Momentum")]


def test_deleted_preset_excluded(base: Path) -> None:
    """UT-GUI-004.001.M01.T10: a result folder with no preset file is skipped."""
    _save_result(base, "gone", "TSLA")

    assert _feed() == []
