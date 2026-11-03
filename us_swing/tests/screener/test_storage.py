"""Unit tests: MD-SCR-006.001.M13 — screener/storage.py
Refs: UT-SCR-006.001.M13.T01 – UT-SCR-006.001.M13.T12
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from us_swing.screener.storage import (
    APIUsageTracker,
    FeatureCache,
    ScreenerResultsStorage,
    ScreenerRunResult,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_result(preset_id: str = "p1", date: str = "2026-04-17") -> ScreenerRunResult:
    return ScreenerRunResult(
        preset_id=preset_id,
        run_timestamp=f"{date}T10:00:00Z",
        execution_mode="manual",
        results={"AAPL": {"passed": True, "score": 0.85}},
    )


@pytest.fixture
def storage(tmp_path: Path) -> ScreenerResultsStorage:
    return ScreenerResultsStorage(base_dir=tmp_path / "results")


@pytest.fixture
def feature_cache(tmp_path: Path) -> FeatureCache:
    return FeatureCache(cache_dir=tmp_path / "cache")


@pytest.fixture
def usage_tracker(tmp_path: Path) -> APIUsageTracker:
    return APIUsageTracker(usage_file=tmp_path / "api_usage.json")


# ---------------------------------------------------------------------------
# T01 — save_result writes to correct path
# ---------------------------------------------------------------------------

def test_save_result_correct_path(storage: ScreenerResultsStorage, tmp_path: Path):
    """UT-SCR-006.001.M13.T01: save creates preset_{id}/{date}.json."""
    result = _make_result("p1", "2026-04-17")
    out_path = storage.save_result(result, "p1")
    assert out_path.name == "2026-04-17.json"
    assert "preset_p1" in str(out_path)
    assert out_path.exists()


# ---------------------------------------------------------------------------
# T02 — save_result is atomic (temp → rename)
# ---------------------------------------------------------------------------

def test_save_result_atomic(storage: ScreenerResultsStorage, tmp_path: Path):
    """UT-SCR-006.001.M13.T02: no .tmp file remains after save."""
    result = _make_result("p1", "2026-04-17")
    storage.save_result(result, "p1")
    result_dir = tmp_path / "results" / "preset_p1"
    tmp_files = list(result_dir.glob("*.tmp"))
    assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"


# ---------------------------------------------------------------------------
# T03 — load_result deserializes JSON to ScreenerRunResult
# ---------------------------------------------------------------------------

def test_load_result_deserializes(storage: ScreenerResultsStorage):
    """UT-SCR-006.001.M13.T03: save then load returns equal ScreenerRunResult."""
    result = _make_result("p1", "2026-04-17")
    storage.save_result(result, "p1")
    loaded = storage.load_result("p1", "2026-04-17")
    assert loaded.preset_id == result.preset_id
    assert loaded.run_timestamp == result.run_timestamp
    assert loaded.execution_mode == result.execution_mode
    assert loaded.results == result.results


# ---------------------------------------------------------------------------
# T04 — load_result raises FileNotFoundError on missing date
# ---------------------------------------------------------------------------

def test_load_result_missing_date(storage: ScreenerResultsStorage):
    """UT-SCR-006.001.M13.T04: FileNotFoundError on nonexistent date."""
    with pytest.raises(FileNotFoundError):
        storage.load_result("p1", "2000-01-01")


# ---------------------------------------------------------------------------
# T05 — load_result raises on corrupted JSON
# ---------------------------------------------------------------------------

def test_load_result_corrupted_json(storage: ScreenerResultsStorage, tmp_path: Path):
    """UT-SCR-006.001.M13.T05: JSONDecodeError logged and re-raised for corrupt file."""
    result_dir = tmp_path / "results" / "preset_p1"
    result_dir.mkdir(parents=True)
    (result_dir / "2026-04-17.json").write_text("NOT JSON", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        storage.load_result("p1", "2026-04-17")


# ---------------------------------------------------------------------------
# T06 — list_results returns last 30 of 50, sorted desc
# ---------------------------------------------------------------------------

def test_list_results_last_30_sorted_desc(storage: ScreenerResultsStorage, tmp_path: Path):
    """UT-SCR-006.001.M13.T06: 30 of 50 results returned, newest first."""
    result_dir = tmp_path / "results" / "preset_p1"
    result_dir.mkdir(parents=True)
    # Create 50 dated result files
    base = datetime(2026, 1, 1)
    dates = [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(50)]
    for d in dates:
        (result_dir / f"{d}.json").write_text("{}", encoding="utf-8")

    listed = storage.list_results("p1", limit=30)
    assert len(listed) == 30
    assert listed == sorted(listed, reverse=True)
    assert listed[0] == dates[-1]  # newest first


# ---------------------------------------------------------------------------
# T07 — FeatureCache.get returns cached features if < 24 h
# ---------------------------------------------------------------------------

def test_feature_cache_get_fresh(feature_cache: FeatureCache):
    """UT-SCR-006.001.M13.T07: features returned when < 24 h old."""
    features = {"price": 100.0, "RSI": 55.0}
    feature_cache.set("AAPL", features, date="2026-04-17")
    result = feature_cache.get("AAPL", date="2026-04-17")
    assert result is not None
    assert result["price"] == 100.0
    assert "_cached_at" not in result


# ---------------------------------------------------------------------------
# T08 — FeatureCache.get returns None if > 24 h old
# ---------------------------------------------------------------------------

def test_feature_cache_get_expired(feature_cache: FeatureCache, tmp_path: Path):
    """UT-SCR-006.001.M13.T08: None returned when cached entry is > 24 h old."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Manually write a cache entry with an old timestamp
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {"MSFT": {"price": 200.0, "_cached_at": old_ts}}
    (cache_dir / "features_2026-04-16.json").write_text(json.dumps(data), encoding="utf-8")
    result = feature_cache.get("MSFT", date="2026-04-16")
    assert result is None


# ---------------------------------------------------------------------------
# T09 — FeatureCache.set stores features with timestamp
# ---------------------------------------------------------------------------

def test_feature_cache_set_stores_timestamp(feature_cache: FeatureCache, tmp_path: Path):
    """UT-SCR-006.001.M13.T09: Features + _cached_at persisted to disk."""
    features = {"RSI": 62.0, "ATR": 1.5}
    feature_cache.set("TSLA", features, date="2026-04-17")
    cache_file = tmp_path / "cache" / "features_2026-04-17.json"
    assert cache_file.exists()
    raw = json.loads(cache_file.read_text())
    assert "TSLA" in raw
    assert "_cached_at" in raw["TSLA"]
    assert raw["TSLA"]["RSI"] == 62.0


# ---------------------------------------------------------------------------
# T10 — APIUsageTracker.log_usage appends entry with tokens + cost
# ---------------------------------------------------------------------------

def test_api_usage_tracker_log_usage(usage_tracker: APIUsageTracker, tmp_path: Path):
    """UT-SCR-006.001.M13.T10: log_usage appends entry with tokens and cost."""
    cost = usage_tracker.log_usage(tokens_in=1000, tokens_out=500, preset_id="p1")
    log = json.loads((tmp_path / "api_usage.json").read_text())
    assert len(log) == 1
    entry = log[0]
    assert entry["tokens_in"] == 1000
    assert entry["tokens_out"] == 500
    assert entry["preset_id"] == "p1"
    assert abs(entry["cost_usd"] - cost) < 1e-9


# ---------------------------------------------------------------------------
# T11 — APIUsageTracker cost formula
# ---------------------------------------------------------------------------

def test_api_usage_tracker_cost_formula(usage_tracker: APIUsageTracker):
    """UT-SCR-006.001.M13.T11: cost = (1000*0.003 + 500*0.009)/1000 ≈ 0.0075."""
    cost = usage_tracker.log_usage(tokens_in=1000, tokens_out=500)
    expected = (1000 * 0.003 + 500 * 0.009) / 1000.0  # 0.0075
    assert abs(cost - expected) < 1e-9


# ---------------------------------------------------------------------------
# T12 — Monthly cost > $50 emits WARNING
# ---------------------------------------------------------------------------

def test_api_usage_tracker_cost_threshold_warning(
    usage_tracker: APIUsageTracker,
    caplog: pytest.LogCaptureFixture,
):
    """UT-SCR-006.001.M13.T12: WARNING logged when monthly cost exceeds $50."""
    # Each call costs 0.0075; need > 50 / 0.0075 ≈ 6667 calls to exceed $50.
    # Instead, manually seed the log with $49.99 of prior usage, then add one more.
    from datetime import datetime, timezone
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    seed_entry = {
        "timestamp": f"{month_prefix}-01T00:00:00Z",
        "preset_id": "",
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 49.995,
    }
    import json
    usage_tracker._file.parent.mkdir(parents=True, exist_ok=True)
    usage_tracker._file.write_text(json.dumps([seed_entry]), encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="us_swing.screener.storage"):
        usage_tracker.log_usage(tokens_in=1000, tokens_out=500)

    assert any("50" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# SRD-SCR-004.009 — candle_date recorded with each result
# ---------------------------------------------------------------------------

def test_candle_date_round_trip(storage: ScreenerResultsStorage):
    """UT-SCR-004.009.M13.T01: candle_date survives save and load."""
    result = _make_result("p1", "2026-11-03")
    result.candle_date = "2026-10-30"
    storage.save_result(result, "p1")
    assert storage.load_result("p1", "2026-11-03").candle_date == "2026-10-30"


def test_candle_date_missing_in_old_file(storage: ScreenerResultsStorage, tmp_path: Path):
    """UT-SCR-004.009.M13.T02: a file saved before the field loads with candle_date None."""
    path = storage.save_result(_make_result("p1", "2026-11-03"), "p1")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["candle_date"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert storage.load_result("p1", "2026-11-03").candle_date is None
