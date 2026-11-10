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
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.desk.registry import load_employee

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
