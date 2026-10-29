"""Tests for MD-BKT-001.004.M02 — backtest/settings.py."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from us_swing.backtest.settings import BacktestDataSettings, DownloadState


def test_settings_round_trip(tmp_path: Path) -> None:
    """UT-BKT-001.004.M02.T01: Saved custom settings load back equal."""
    custom = BacktestDataSettings(
        start_date=date(2020, 3, 1),
        end_date=date(2024, 12, 31),
        auto_delta=False,
        run_time=time(18, 5),
        run_days=(1, 3),
    )
    custom.save(tmp_path)

    assert BacktestDataSettings.load(tmp_path) == custom


def test_broken_settings_file_loads_defaults(tmp_path: Path) -> None:
    """UT-BKT-001.004.M02.T02: A broken settings.json loads the defaults."""
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")

    loaded = BacktestDataSettings.load(tmp_path)

    assert loaded == BacktestDataSettings()
    assert loaded.start_date == date(2016, 1, 1)
    assert loaded.end_date is None
    assert loaded.auto_delta is True
    assert loaded.run_time == time(17, 30)
    assert loaded.run_days == (0, 1, 2, 3, 4)


def test_download_state_round_trip(tmp_path: Path) -> None:
    """UT-BKT-001.004.M02.T01: Download state saves and loads back equal."""
    state = DownloadState(
        last_delta=datetime(2026, 10, 27, 21, 35, tzinfo=timezone.utc),
        floors={"AAPL": date(2006, 1, 3)},
        failed=["ZZZZ"],
    )
    state.save(tmp_path)

    assert DownloadState.load(tmp_path) == state
