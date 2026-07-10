"""Tests for the once-per-day day-end P&L trigger (SRD-INF-010.010)."""
from __future__ import annotations

import datetime
from types import SimpleNamespace

from us_swing.gui.app_service import AppService


def _fake(**kw):
    calls: list[int] = []
    ns = SimpleNamespace(
        _day_end_sent_date=None,
        _notif_worker=object(),
        _publish_day_end_pnl=lambda: calls.append(1),
    )
    ns.__dict__.update(kw)
    return ns, calls


def test_day_end_sends_once_per_day():
    """UT-INF-010.001.M09.T01: the day-end summary sends once per trading day."""
    ns, calls = _fake()
    day = datetime.date(2026, 7, 9)
    AppService._maybe_publish_day_end(ns, day)
    AppService._maybe_publish_day_end(ns, day)  # same day -> no second send
    assert len(calls) == 1
    assert ns._day_end_sent_date == day


def test_day_end_sends_again_next_day():
    """UT-INF-010.001.M09.T02: a new trading day sends a fresh summary."""
    ns, calls = _fake()
    AppService._maybe_publish_day_end(ns, datetime.date(2026, 7, 9))
    AppService._maybe_publish_day_end(ns, datetime.date(2026, 7, 10))
    assert len(calls) == 2


def test_day_end_skips_until_worker_ready():
    """UT-INF-010.001.M09.T03: no send and no guard before notifications start."""
    ns, calls = _fake(_notif_worker=None)
    day = datetime.date(2026, 7, 9)
    AppService._maybe_publish_day_end(ns, day)
    assert calls == []
    assert ns._day_end_sent_date is None  # guard not consumed -> retries later
