"""Tests for the daily Telegram triggers on AppService (SRD-INF-010.010, FO-INF-012)."""
from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from us_swing.core.notifications import DayEndPnLEvent, MorningBriefEvent, ToolStartedEvent
from us_swing.core.notifications._briefs import DAY_END, MORNING_BRIEF, SendLog
from us_swing.data.market_calendar import ET
from us_swing.data.models import RiskConfig, UserProfile
from us_swing.gui import morning_brief, telegram_token_store
from us_swing.gui.app_service import AppService

THU = datetime.date(2026, 11, 5)


def _at(day: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)


def _user(**kw: Any) -> UserProfile:
    return UserProfile(
        user_id=1, username="t", display_name="T", ibkr_client_id=1, mode="paper",
        risk_config=RiskConfig(), strategy_config={}, screener_config={},
        telegram_enabled=True, telegram_chat_id="42", **kw,
    )


def _fake(tmp_path: Path, **kw: Any) -> tuple[SimpleNamespace, list[Any]]:
    calls: list[Any] = []
    ns = SimpleNamespace(
        _active_uid=1,
        _send_log=SendLog(tmp_path / "state.json"),
        _notif_worker=object(),
        _publish_day_end_pnl=lambda now: calls.append(now) or True,
        get_active_user=_user,
        _brief_base=lambda now: MorningBriefEvent(session_date=str(now.date())),
        _brief_ai_config=lambda: None,
        publish_notification=lambda e: calls.append(e) or True,
    )
    ns.__dict__.update(kw)
    return ns, calls


def test_day_end_sends_once_per_day(tmp_path: Path) -> None:
    """UT-INF-010.001.M09.T01: the day-end summary sends once per trading day."""
    ns, calls = _fake(tmp_path)
    AppService._maybe_publish_day_end(ns, _at(THU, 16, 6))
    AppService._maybe_publish_day_end(ns, _at(THU, 16, 7))
    assert len(calls) == 1
    assert SendLog(tmp_path / "state.json").last_sent(1, DAY_END) == THU


def test_day_end_sends_again_next_day(tmp_path: Path) -> None:
    """UT-INF-010.001.M09.T02: a new trading day sends a fresh summary."""
    ns, calls = _fake(tmp_path)
    AppService._maybe_publish_day_end(ns, _at(THU, 16, 6))
    AppService._maybe_publish_day_end(ns, _at(THU + datetime.timedelta(days=1), 16, 6))
    assert len(calls) == 2


def test_day_end_skips_until_worker_ready(tmp_path: Path) -> None:
    """UT-INF-010.001.M09.T03: no send and no guard before notifications start."""
    ns, calls = _fake(tmp_path, _notif_worker=None)
    AppService._maybe_publish_day_end(ns, _at(THU, 16, 6))
    assert calls == []
    assert ns._send_log.last_sent(1, DAY_END) is None


def test_no_startup_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """UT-INF-012.001.M04.T01: starting notifications publishes no ToolStartedEvent."""
    published: list[object] = []

    class _Worker:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr("us_swing.gui.app_service.NotificationWorker", _Worker)
    monkeypatch.setattr("us_swing.gui.telegram_commands.TelegramCommandBridge",
                        lambda _app: object())
    ns, _ = _fake(tmp_path, _build_notification_config=lambda: None,
                  publish_notification=published.append)

    AppService._start_notifications(ns)

    assert isinstance(ns._notif_worker, _Worker)
    assert not any(isinstance(e, ToolStartedEvent) for e in published)


def test_brief_sent_once_per_day(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """UT-INF-012.002.M04.T01: two pre-market ticks start one brief and save the day."""
    jobs: list[Any] = []
    monkeypatch.setattr(morning_brief, "send_brief_async",
                        lambda event, ai, publish: jobs.append(event) or publish(event))
    ns, _ = _fake(tmp_path, _brief_in_flight=False)

    AppService._maybe_send_morning_brief(ns, _at(THU, 7))
    AppService._maybe_send_morning_brief(ns, _at(THU, 7, 1))

    assert len(jobs) == 1
    assert SendLog(tmp_path / "state.json").last_sent(1, MORNING_BRIEF) == THU


def test_brief_not_marked_when_not_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """UT-INF-012.002.M04.T01: a brief the worker could not take is tried again."""
    monkeypatch.setattr(morning_brief, "send_brief_async",
                        lambda event, ai, publish: publish(event))
    ns, _ = _fake(tmp_path, _brief_in_flight=False, publish_notification=lambda _e: False)

    AppService._maybe_send_morning_brief(ns, _at(THU, 7))

    assert ns._send_log.last_sent(1, MORNING_BRIEF) is None
    assert ns._brief_in_flight is False


def test_day_end_not_marked_when_not_sent(tmp_path: Path) -> None:
    """UT-INF-010.001.M09.T03: a day-end report the worker could not take is retried."""
    ns, _ = _fake(tmp_path, _publish_day_end_pnl=lambda _now: False)
    AppService._maybe_publish_day_end(ns, _at(THU, 21))
    assert ns._send_log.last_sent(1, DAY_END) is None


def test_day_end_uses_todays_closed_trades(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """UT-INF-012.005.M04.T01: only this user's trades closed in the ET day are listed."""
    from us_swing.gui import active_cycles_model

    monkeypatch.setattr(active_cycles_model, "_today_et_bounds_utc",
                        lambda: ("2026-11-05T05:00:00", "2026-11-06T05:00:00"))
    seen: list[tuple[str, str]] = []

    def _closed(start: str, end: str) -> tuple[Any, ...]:
        seen.append((start, end))
        return (
            SimpleNamespace(symbol="AAPL", user_id=1, realized_pnl_usd=120.0,
                            realized_pnl_pct=2.4),
            SimpleNamespace(symbol="MSFT", user_id=1, realized_pnl_usd=-40.0,
                            realized_pnl_pct=None),
            SimpleNamespace(symbol="TSLA", user_id=2, realized_pnl_usd=500.0,
                            realized_pnl_pct=1.0),
        )

    published: list[Any] = []
    ns, _ = _fake(
        tmp_path, _tc_query=SimpleNamespace(closed_between=_closed),
        get_positions=lambda _uid: [SimpleNamespace(unrealised_pnl=10.0)],
        publish_notification=published.append,
    )

    AppService._publish_day_end_pnl(ns, _at(THU, 16, 6))

    event = published[0]
    assert isinstance(event, DayEndPnLEvent)
    assert seen == [("2026-11-05T05:00:00", "2026-11-06T05:00:00")]
    assert [t.symbol for t in event.trades] == ["AAPL", "MSFT"]
    assert (event.realized, event.unrealized, event.trade_count) == (80.0, 10.0, 2)


def test_morning_brief_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-012.006.M04.T01: the Morning brief toggle reaches the config; test always on."""
    monkeypatch.setattr(telegram_token_store, "load", lambda _uid: "token")
    ns = SimpleNamespace(get_active_user=lambda: _user(notify_morning_brief=False))

    config = AppService._build_notification_config(ns)

    assert config.event_toggles["MorningBriefEvent"] is False
    assert config.event_toggles["ToolStartedEvent"] is True
