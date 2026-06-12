"""Regression tests for the auto-update check-throttle (ISS-INF-0001).

A failed update poll must NOT stamp the 24-hour throttle, so the next launch
retries instead of going silent for the whole interval. A poll that actually
reaches the source (update found OR already up to date) must stamp.
"""
from __future__ import annotations

from typing import Any

import updater_stub as u


def _patch(monkeypatch: Any, *, manifest: dict[str, Any] | None, current: str = "1.0.0") -> list[int]:
    """Wire a deterministic config + fetch and record stamp calls."""
    stamped: list[int] = []
    cfg = {"enabled": True, "interval_hours": 24, "github_repo": "owner/repo",
           "current_version": current, "github_asset_pattern": "_Setup.exe"}
    monkeypatch.setattr(u, "_load_config", lambda: cfg)
    monkeypatch.setattr(u, "_is_check_due", lambda _secs: True)
    monkeypatch.setattr(u, "_fetch_github_manifest", lambda _repo, _cfg: manifest)
    monkeypatch.setattr(u, "_stamp_check_time", lambda: stamped.append(1))
    return stamped


def test_failed_fetch_does_not_stamp(monkeypatch: Any) -> None:
    """A None manifest (unreachable source) returns None without stamping the throttle."""
    stamped = _patch(monkeypatch, manifest=None)

    result = u.check_update_available()

    assert result is None
    assert stamped == [], "failed poll must not burn the 24-hour throttle"


def test_update_available_stamps(monkeypatch: Any) -> None:
    """A newer version returns UpdateInfo and stamps the throttle (source was reached)."""
    stamped = _patch(
        monkeypatch,
        manifest={"version": "2.0.0", "download_url": "https://example.com/x.exe", "sha256": "deadbeef"},
        current="1.0.0",
    )

    result = u.check_update_available()

    assert result is not None
    assert result.remote_version == "2.0.0"
    assert stamped == [1]


def test_up_to_date_still_stamps(monkeypatch: Any) -> None:
    """An up-to-date result returns None but still stamps (source answered, no error)."""
    stamped = _patch(
        monkeypatch,
        manifest={"version": "1.0.0", "download_url": "https://example.com/x.exe", "sha256": "deadbeef"},
        current="1.0.0",
    )

    result = u.check_update_available()

    assert result is None
    assert stamped == [1]
