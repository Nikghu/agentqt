"""Tests for MD-BKT-002.005.M03 — backtest/cache.py."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.backtest.cache import StepCache, make_key

_NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def test_write_then_read(tmp_path: Path) -> None:
    """UT-BKT-002.005.M03.T01: A written frame reads back; the key ignores dict order."""
    cache = StepCache(tmp_path)
    frame = pd.DataFrame({"symbol": ["AAPL"], "score": [0.5]})
    key = make_key("stocks", 1, {"a": 1, "b": [1, 2]})

    cache.write("stocks", key, "2026-01-02", frame)

    pd.testing.assert_frame_equal(cache.read("stocks", key, "2026-01-02"), frame)
    assert key == make_key("stocks", 1, {"b": [1, 2], "a": 1})
    assert key != make_key("stocks", 2, {"a": 1, "b": [1, 2]})
    assert cache.names("stocks", key) == {"2026-01-02"}


def test_miss_and_failed_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-BKT-002.005.M03.T02: A miss returns None; a failed write leaves no file."""
    cache = StepCache(tmp_path)
    assert cache.read("stocks", "nokey", "x") is None

    def boom(self: pd.DataFrame, path: Any, **_: Any) -> None:
        Path(path).write_bytes(b"half")
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", boom)
    with pytest.raises(OSError):
        cache.write("stocks", "k", "d", pd.DataFrame({"a": [1]}))

    assert list((tmp_path / "stocks" / "k").iterdir()) == []


def test_cleanup_by_age_and_size(tmp_path: Path) -> None:
    """UT-BKT-002.006.M03.T01: Old files go first, then the oldest over the size limit."""
    cache = StepCache(tmp_path)
    frame = pd.DataFrame({"a": list(range(100))})
    for i, name in enumerate(("old", "n1", "n2", "n3")):
        cache.write("stocks", "k", name, frame)
        path = tmp_path / "stocks" / "k" / f"{name}.parquet"
        age = 40 * 86_400 if name == "old" else (10 - i) * 60
        os.utime(path, (_NOW.timestamp() - age, _NOW.timestamp() - age))
    size = (tmp_path / "stocks" / "k" / "n1.parquet").stat().st_size

    freed = cache.cleanup(_NOW, max_bytes=2 * size)

    assert cache.names("stocks", "k") == {"n2", "n3"}
    assert freed == 2 * size
