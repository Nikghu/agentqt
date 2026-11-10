"""Fixtures for desk (DSK) tests."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from us_swing.desk.store import DeskStore


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def move(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


# Thursday 2026-11-05 15:00 ET (EST, UTC-5).
THU_1500_ET = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)
# Thursday 2026-11-05 02:30 ET — 90 minutes before the morning run window opens at 04:00.
THU_0230_ET = datetime(2026, 11, 5, 7, 30, tzinfo=UTC)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(THU_0230_ET)


@pytest.fixture
def store(home: Path) -> Iterator[DeskStore]:
    s = DeskStore(home)
    yield s
    s.close()
