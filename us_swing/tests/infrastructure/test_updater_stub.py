"""Regression tests for the auto-update check-throttle (ISS-INF-0001 / ISS-INF-0002).

The throttle is stamped *before* the poll: once the interval is due, the check time
is recorded and then the source is polled. A failed poll therefore still stamps, so
a rate-limited or unreachable source waits until the next interval instead of
re-polling on every launch and burning GitHub's 60/hour unauthenticated cap.

The in-app "Check for Updates" button passes force=True to bypass the throttle, so
the user is never blocked by a check that ran before the new release was published.
"""
from __future__ import annotations

from typing import Any

import updater_stub as u


def _patch(
    monkeypatch: Any,
    *,
    manifest: dict[str, Any] | None,
    current: str = "1.0.0",
    due: bool = True,
) -> list[int]:
    """Wire a deterministic config + fetch and record stamp calls."""
    stamped: list[int] = []
    cfg = {"enabled": True, "interval_hours": 24, "github_repo": "owner/repo",
           "current_version": current, "github_asset_pattern": "_Setup.exe"}
    monkeypatch.setattr(u, "_load_config", lambda: cfg)
    monkeypatch.setattr(u, "_is_check_due", lambda _secs: due)
    monkeypatch.setattr(u, "_fetch_github_manifest", lambda _repo, _cfg: manifest)
    monkeypatch.setattr(u, "_stamp_check_time", lambda: stamped.append(1))
    return stamped


def test_failed_fetch_still_stamps(monkeypatch: Any) -> None:
    """A None manifest (unreachable source) returns None but still stamps the throttle."""
    stamped = _patch(monkeypatch, manifest=None)

    result = u.check_update_available()

    assert result is None
    assert stamped == [1], "stamp-before-fetch prevents a re-poll death spiral on failure"


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


def test_not_due_skips_poll(monkeypatch: Any) -> None:
    """When the interval is not due, the check returns early without stamping or polling."""
    fetched: list[int] = []
    stamped = _patch(
        monkeypatch,
        manifest={"version": "2.0.0", "download_url": "https://example.com/x.exe", "sha256": "deadbeef"},
        due=False,
    )
    monkeypatch.setattr(u, "_fetch_github_manifest", lambda _repo, _cfg: fetched.append(1) or None)

    result = u.check_update_available()

    assert result is None
    assert stamped == []
    assert fetched == [], "throttled check must not hit the network"


def test_force_bypasses_throttle(monkeypatch: Any) -> None:
    """force=True polls and detects an update even when the interval is not due."""
    _patch(
        monkeypatch,
        manifest={"version": "2.0.0", "download_url": "https://example.com/x.exe", "sha256": "deadbeef"},
        current="1.0.0",
        due=False,
    )

    result = u.check_update_available(force=True)

    assert result is not None
    assert result.remote_version == "2.0.0"
