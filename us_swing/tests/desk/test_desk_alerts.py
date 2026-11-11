"""Tests for AI problem alerts (MD-DSK-007.001.M21, MD-DSK-004.001.M11, MD-DSK-003.001.M10).
Employee names are made up; no test sends a real Telegram message."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.desk.test_harness import BAD, GOOD, ON, SKILLS, FakeCaller, View, employee, job
from us_swing.core import desk_alerts
from us_swing.core.desk_alerts import classify, open_alerts, raise_alert, send_telegram
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_events import Event, open_events
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.desk.registry import load_employee
from us_swing.desk.store import DeskStore

NY = desk_alerts.NY
NOW = datetime(2026, 11, 9, 16, 26, tzinfo=NY)
LOGIN = RuntimeError("Failed to authenticate: this login reached its time limit. "
                     "Run `claude auth login` to sign in again")
CLAUDE_FIRST = job().replace("primary: {source: openrouter, model: or-model}",
                             "primary: {source: claude, model: default}").replace(
    "backup: {source: claude, model: default}", "backup: {source: openrouter, model: or-model}")


class FakeSend:
    """Records messages instead of sending them."""

    def __init__(self, ok: bool = True) -> None:
        self.sent: list[str] = []
        self.ok = ok

    def __call__(self, text: str) -> bool:
        self.sent.append(text)
        return self.ok


def _valid(home: Path, started: str, source: str) -> None:
    rec = Recorder(home)
    try:
        rec.add(Attempt(9, "t-1", "Tester A", 1, "2026-11-09", started, source, "m", 1, "p", "a",
                        True, "", 10, 1, 0.0, 1.0))
    finally:
        rec.close()


def test_classify() -> None:
    """UT-DSK-007.001.M21.T01: login, key and credit problems are found; others are not."""
    assert classify("claude", str(LOGIN)) == "login"
    assert classify("openrouter", "401 Unauthorized: No auth credentials found") == "key"
    assert classify("openrouter", "402 insufficient credits") == "credit"
    assert classify("claude", "answer: field required") is None
    assert classify("claude", "Credit balance is too low") == "credit"
    assert classify("openrouter", "connect failed on port 4010, request 14012") is None
    assert classify("openrouter", "the model said it earned credits") is None


def test_once_a_day(tmp_path: Path) -> None:
    """UT-DSK-007.002.M21.T01: one alert per problem per day, sent once."""
    send = FakeSend()
    first = raise_alert(tmp_path, "login", "claude", 3, "Tester A: no login", NOW, send)
    assert first is not None and first.sent and first.title == "Claude login expired"
    assert raise_alert(tmp_path, "login", "claude", 4, "again", NOW, send) is None
    assert len(send.sent) == 1 and "claude auth login" in send.sent[0]
    later = raise_alert(tmp_path, "login", "claude", 5, "next day", NOW + timedelta(days=1), send)
    assert later is not None and len(send.sent) == 2


def test_failed_send_still_shows(tmp_path: Path) -> None:
    """UT-DSK-007.003.M21.T01: a failed Telegram send keeps the alert open and is tried again."""
    alert = raise_alert(tmp_path, "key", "openrouter", 1, "bad key", NOW, FakeSend(ok=False))
    assert alert is not None and not alert.sent
    assert [a.kind for a in open_alerts(tmp_path, NOW)] == ["key"]
    retry = FakeSend()
    assert raise_alert(tmp_path, "key", "openrouter", 2, "bad key", NOW, retry) is None
    assert len(retry.sent) == 1 and open_alerts(tmp_path, NOW)[0].sent
    again = FakeSend()
    raise_alert(tmp_path, "key", "openrouter", 3, "bad key", NOW, again)
    assert again.sent == []


def test_open_until_fixed(tmp_path: Path) -> None:
    """UT-DSK-007.006.M21.T01: alerts close when the source works again, or after a day."""
    raise_alert(tmp_path, "login", "claude", 1, "no login", NOW, FakeSend())
    raise_alert(tmp_path, "run_failed", "", 1, "none valid", NOW, FakeSend())
    _valid(tmp_path, "2026-11-09T16:40:00-05:00", "openrouter")
    assert [a.kind for a in open_alerts(tmp_path, NOW)] == ["login"]
    _valid(tmp_path, "2026-11-09T17:00:00-05:00", "claude")
    assert open_alerts(tmp_path, NOW) == []
    raise_alert(tmp_path, "key", "openrouter", 2, "bad key", NOW, FakeSend())
    assert open_alerts(tmp_path, NOW + timedelta(hours=25)) == []


def _run(home: Path, kind: str, started: datetime, result: str) -> None:
    store = DeskStore(home)
    try:
        store.end_run(store.start_run(kind, started), result, started)
    finally:
        store.close()


def test_candles_alert_once_a_day(tmp_path: Path) -> None:
    """UT-DSK-007.007.M21.T01: Candles alert stored and sent once a day (SRD-DSK-007.007)."""
    send = FakeSend()
    first = raise_alert(tmp_path, "candles", "", 1, "7 of 504 stocks behind", NOW, send)
    assert first is not None and first.title == "Candles not up to date"
    assert raise_alert(tmp_path, "candles", "", 2, "again", NOW, send) is None
    assert len(send.sent) == 1 and "Update now" in send.sent[0]


def test_candles_alert_closed_by_ok_run(tmp_path: Path) -> None:
    """UT-DSK-007.007.M21.T02: Candles alert closed by a later ok run (SRD-DSK-007.007)."""
    at = datetime(2026, 11, 11, 8, 31, tzinfo=NY)
    raise_alert(tmp_path, "candles", "", 1, "behind", at, FakeSend())
    _run(tmp_path, "morning", at + timedelta(minutes=16), "ok")
    assert open_alerts(tmp_path, at + timedelta(minutes=20)) == []


def test_candles_alert_stays_open(tmp_path: Path) -> None:
    """UT-DSK-007.007.M21.T03: Candles alert stays after a failed run or a valid AI answer."""
    at = datetime(2026, 11, 9, 16, 0, tzinfo=NY)
    raise_alert(tmp_path, "candles", "", 1, "behind", at, FakeSend())
    _run(tmp_path, "morning", at + timedelta(minutes=16), "failed")
    _run(tmp_path, "event", at + timedelta(minutes=17), "ok")
    _valid(tmp_path, "2026-11-09T16:40:00-05:00", "claude")
    assert [a.kind for a in open_alerts(tmp_path, at + timedelta(hours=1))] == ["candles"]


def test_telegram_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-007.003.M21.T02: the first user with Telegram on is the target; none sends nothing."""
    users = tmp_path / "users.json"
    users.write_text(json.dumps([
        {"user_id": 1, "telegram_enabled": False, "telegram_chat_id": "11"},
        {"user_id": 2, "telegram_enabled": True, "telegram_chat_id": "22"}]), encoding="utf-8")
    import keyring

    monkeypatch.setattr(keyring, "get_password",
                        lambda service, user: "tok" if user == "2" else None)
    assert desk_alerts.telegram_target(users) == ("tok", "22")
    assert desk_alerts.telegram_target(tmp_path / "none.json") is None
    assert send_telegram("hello") is False


def _gateway(home: Path, caller: FakeCaller, run_id: int, send: FakeSend) -> Gateway:
    hire = load_employee(employee(home, job_text=CLAUDE_FIRST), SKILLS)
    assert hire is not None
    rec = Recorder(home)
    return Gateway(home, hire, rec, ON, "key", run_id, "2026-11-09", caller, lambda: NOW,
                   send=send)


def test_login_skips_to_backup(tmp_path: Path) -> None:
    """UT-DSK-007.004.M11.T01: a login error raises an alert and the run moves to the backup."""
    send = FakeSend()
    caller = FakeCaller(LOGIN, GOOD)
    first = _gateway(tmp_path, caller, 21, send)
    assert first.ask("facts", View) is not None
    assert [c[0] for c in caller.calls] == ["claude", "openrouter"]
    assert len(send.sent) == 1 and "Claude login expired" in send.sent[0]
    second_caller = FakeCaller(GOOD)
    second = _gateway(tmp_path, second_caller, 21, send)
    assert second.ask("facts", View) is not None
    assert [c[0] for c in second_caller.calls] == ["openrouter"]
    next_run = FakeCaller(GOOD)
    assert _gateway(tmp_path, next_run, 22, send).ask("facts", View) is not None
    assert [c[0] for c in next_run.calls] == ["claude"]


def test_bad_answer_is_not_a_problem(tmp_path: Path) -> None:
    """UT-DSK-007.004.M11.T02: an answer in the wrong form retries as before, no alert."""
    send = FakeSend()
    caller = FakeCaller(BAD, GOOD)
    assert _gateway(tmp_path, caller, 31, send).ask("facts", View) is not None
    assert [c[0] for c in caller.calls] == ["claude", "claude"] and send.sent == []


def test_whole_run_failed(tmp_path: Path) -> None:
    """UT-DSK-007.005.M10.T01: a run with calls but no valid answer raises one alert."""
    home = tmp_path / "desk"
    employee(home)
    send = FakeSend()
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key",
                         FakeCaller(BAD, BAD, BAD, BAD), lambda: NOW, send=send)
    step(StepContext(41, "manual", NOW, home))
    assert len(send.sent) == 1 and "No employee gave a valid answer" in send.sent[0]
    ok_send = FakeSend()
    ok_home = tmp_path / "ok"
    employee(ok_home)
    EmployeesStep(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key", FakeCaller(GOOD),
                  lambda: NOW, send=ok_send)(StepContext(42, "manual", NOW, ok_home))
    assert ok_send.sent == []


# ---------------- partial plan alert (step B) ----------------

def _chain_done(home: Path, note: str, handled: datetime) -> None:
    con = open_events(home)
    try:
        with con:
            con.execute("INSERT INTO events (key, kind, state, handled, note) "
                        "VALUES (?, 'after_run', 'done', ?, ?)",
                        (f"k{handled.isoformat()}", handled.isoformat(timespec="seconds"), note))
    finally:
        con.close()


def test_partial_alert(home: Path) -> None:
    """UT-DSK-007.008.M21.T01: A step failed 3 times gives one partial alert with the error."""
    employee(home)
    hire = load_employee(home / "employees" / "t-1", SKILLS)
    assert hire is not None
    rec = Recorder(home)
    try:
        rec.add(Attempt(1, "t-1", "Tester A", 1, "2026-11-09", "2026-11-09T16:20:00-05:00",
                        "openrouter", "m", 1, "p", "", False, "answer was not json", 1, 1, 0.0,
                        1.0))
    finally:
        rec.close()
    send = FakeSend()
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key", FakeCaller(),
                         lambda: NOW, send)
    router, _ = step._router(home, 3)
    router._alert(hire, Event(1, "after_run", 1, "2026-11-09", "", None, ""))  # type: ignore[misc]
    alerts = open_alerts(home, NOW)
    assert [(a.kind, a.source, a.title) for a in alerts] == [
        ("partial", "t-1", "Desk plan is partial")]
    assert "Tester A failed 3 times: answer was not json" in alerts[0].text
    assert len(send.sent) == 1


def test_partial_alert_once_a_day(tmp_path: Path) -> None:
    """UT-DSK-007.008.M21.T02: The same step failing in 2 chains on one day gives one alert."""
    send = FakeSend()
    assert raise_alert(tmp_path, "partial", "t-1", 1, "first", NOW, send) is not None
    assert raise_alert(tmp_path, "partial", "t-1", 2, "second", NOW, send) is None
    assert len(send.sent) == 1


def test_partial_alert_closes(tmp_path: Path) -> None:
    """UT-DSK-007.008.M21.T03: A later chain with note chain full closes the partial alert."""
    raise_alert(tmp_path, "partial", "t-1", 1, "failed", NOW, FakeSend())
    _chain_done(tmp_path, "chain partial", NOW + timedelta(minutes=5))
    assert [a.kind for a in open_alerts(tmp_path, NOW + timedelta(minutes=6))] == ["partial"]
    _chain_done(tmp_path, "chain full", NOW + timedelta(minutes=10))
    assert open_alerts(tmp_path, NOW + timedelta(minutes=11)) == []
