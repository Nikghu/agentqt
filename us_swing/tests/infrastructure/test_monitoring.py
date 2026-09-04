"""Unit tests — MD-INF-005.001.M01 / M02 / M03 Monitoring subsystem.

Refs:
  UT-INF-005.001.M01.T01 – T04  (logging_setup)
  UT-INF-005.001.M02.T01 – T02  (alerts)
  UT-INF-005.001.M03.T01        (health)
"""
from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from us_swing.monitoring.alerts import AlertDispatcher
from us_swing.monitoring.health import HealthCheck
from us_swing.monitoring.logging_setup import (
    _DailyDateHandler,
    _resolve_tz,
    _ZonedFormatter,
    configure_logging,
)


def test_T01_configure_logging_attaches_daily_file_handler(tmp_path: Path) -> None:
    """UT-INF-005.001.M01.T01 — configure_logging() attaches a _DailyDateHandler to root."""
    log_dir = tmp_path / "logs"
    root = logging.getLogger()
    before_count = sum(1 for h in root.handlers if isinstance(h, _DailyDateHandler))

    configure_logging(log_dir, "INFO")

    after_count = sum(1 for h in root.handlers if isinstance(h, _DailyDateHandler))
    assert after_count > before_count


def test_T03_timestamps_use_the_configured_market_timezone() -> None:
    """UT-INF-005.001.M01.T03 — a record is stamped in the market zone with a true offset."""
    moment = datetime.datetime(2026, 8, 31, 16, 35, 45, tzinfo=datetime.timezone.utc)
    record = logging.LogRecord(
        name="demo", level=logging.INFO, pathname=__file__, lineno=1,
        msg="order sent", args=(), exc_info=None,
    )
    record.created = moment.timestamp()

    stamped = _ZonedFormatter(_resolve_tz("US/Eastern")).formatTime(record)

    assert stamped == "2026-08-31T12:35:45-0400"
    assert not stamped.endswith("Z")


def test_T04_unknown_timezone_falls_back_to_the_local_zone() -> None:
    """UT-INF-005.001.M01.T04 — an unusable zone name resolves to the local zone, not a crash."""
    local = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

    assert _resolve_tz("Not/AZone") == local
    assert _resolve_tz(None) == local
    assert _resolve_tz("US/Eastern") != datetime.timezone.utc


def test_T02_excepthook_logs_uncaught_exception(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-INF-005.001.M01.T02 — installed sys.excepthook logs CRITICAL on uncaught exception."""
    saved = sys.excepthook
    # Restore the Python default hook before installing ours so that our hook's
    # _original is sys.__excepthook__ (prints to stderr) rather than pytest-qt's
    # hook (which would re-raise and fail the test).
    sys.excepthook = sys.__excepthook__
    try:
        configure_logging(tmp_path / "logs", "INFO")
        with caplog.at_level(logging.CRITICAL):
            sys.excepthook(ValueError, ValueError("sentinel-test-error"), None)
        assert any("sentinel-test-error" in r.message for r in caplog.records)
    finally:
        sys.excepthook = saved


def test_T03_alert_dispatcher_appends_to_file(tmp_path: Path) -> None:
    """UT-INF-005.001.M02.T01 — AlertDispatcher.send() appends line to alerts.log."""
    dispatcher = AlertDispatcher(log_dir=tmp_path)
    dispatcher.send("WARNING", "test-alert-message")

    alerts_file = tmp_path / "alerts.log"
    assert alerts_file.exists()
    content = alerts_file.read_text()
    assert "test-alert-message" in content
    assert "WARNING" in content


def test_T04_webhook_failure_does_not_crash(tmp_path: Path) -> None:
    """UT-INF-005.001.M02.T02 — webhook failure does not propagate an exception."""
    dispatcher = AlertDispatcher(log_dir=tmp_path, webhook_url="http://127.0.0.1:1")
    # Should not raise, even with a bad URL.
    dispatcher.send("WARNING", "webhook-failure-test")


def test_T05_health_report_has_expected_keys(tmp_path: Path) -> None:
    """UT-INF-005.001.M03.T01 — HealthCheck.report() returns dict with required keys."""
    mock_broker = MagicMock()
    mock_broker.is_connected.return_value = True

    from us_swing.db.manager import DatabaseManager
    db = DatabaseManager("sqlite:///:memory:")
    db.create_schema()

    hc = HealthCheck(broker=mock_broker, db=db)
    report = hc.report()

    required_keys = {"broker_connected", "last_update", "universe_count", "open_positions", "db_reachable"}
    assert required_keys <= set(report.keys())
    assert report["broker_connected"] is True
    assert report["db_reachable"] is True
