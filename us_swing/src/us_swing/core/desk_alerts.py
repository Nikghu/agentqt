"""
Module: MD-DSK-007.001.M21 — core/desk_alerts.py
Parent SRD: SRD-DSK-007.001
Also: SRD-DSK-007.002 (once a day), SRD-DSK-007.003 (Telegram), SRD-DSK-007.005 (whole run
failed), SRD-DSK-007.006 (open alerts close when the source works again), SRD-DSK-007.007
(candles not up to date, closed by a later ok run), SRD-DSK-007.008 (desk plan is partial,
closed by a later full chain), SRD-DSK-007.009 (trade at stop or target, plan broken), SRD-DSK-007.010 (research ticket waiting,
closed once the ticket is no longer waiting), SRD-DSK-007.011 (escalation not answered)

AI problem alerts: sorts an LLM error into a problem the user must fix (Claude login, OpenRouter
key or credit), keeps one alert per problem per day in ``desk.db``, sends it to Telegram and
lists the alerts that are still open. Written by the desk process, read by the GUI.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from us_swing.core.desk_contract import DB_NAME, utc_text

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
OPEN_HOURS = 24
USERS_FILE = Path.home() / ".usswing" / "users.json"
TELEGRAM_SERVICE = "usswing_telegram"
_API = "https://api.telegram.org"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY, key TEXT UNIQUE, created TEXT, kind TEXT, source TEXT,
    run_id INTEGER, title TEXT, text TEXT, fix TEXT, sent INTEGER DEFAULT 0
);
"""
_AUTH = re.compile(r"failed to authenticate|claude auth login|not logged in|oauth token|"
                   r"\b401\b|unauthori[sz]ed|invalid api key|no auth credentials|"
                   r"user not found", re.IGNORECASE)
_CREDIT = re.compile(r"\b402\b|insufficient credits?|credit balance|insufficient balance|"
                     r"payment required", re.IGNORECASE)
_FIX = {
    "login": ("Claude login expired",
              "Run `claude auth login` on this PC, or set CLAUDE_CODE_OAUTH_TOKEN for "
              "unattended runs. Until then the desk uses the backup model."),
    "key": ("OpenRouter key not accepted",
            "Check the OpenRouter key in AI Desk → Desk settings."),
    "credit": ("AI credit used up",
               "Add credit with the model provider, or switch the desk to the other model in "
               "AI Desk → Desk settings."),
    "run_failed": ("No employee gave a valid answer",
                   "Open AI Desk → Team at work → Event log to see each error."),
    "candles": ("Candles not up to date",
                "Open Settings → Candle data and press Update now with TWS connected. The desk "
                "tries again after 15 minutes, up to 3 times a day; after that press Run now "
                "in AI Desk."),
    "trade_stop": ("Trade at stop", "Check the trade in Execution; the desk does not close it."),
    "trade_target": ("Trade at target", "Check the trade in Execution."),
    "plan_broken": ("Plan broken", "Read the desk's note in Market Floor before you act."),
    "ticket_waiting": ("Research ticket waiting",
                       "Approve or reject it in AI Desk → Research."),
    "escalation": ("Escalation not answered",
                   "Read the thread in AI Desk → Team at work → Threads."),
    "partial": ("Desk plan is partial",
                "Open AI Desk → Team at work → Event log to see the error; the next run tries "
                "again."),
}
DATA_PROBLEMS = ("candles",)
MARKET_ALERTS = ("trade_stop", "trade_target", "plan_broken", "escalation")  # open for the day
USER_PROBLEMS = ("login", "key", "credit")

Sender = Callable[[str], bool]


@dataclass(frozen=True)
class Alert:
    """One AI problem alert."""

    id: int
    created: datetime
    kind: str
    source: str
    run_id: int
    title: str
    text: str
    fix: str
    sent: bool

    @property
    def message(self) -> str:
        """The alert as one plain message."""
        return f"AI Desk alert: {self.title}\n{self.text}\nWhat to do: {self.fix}"


def classify(source: str, error: str) -> str | None:
    """Return ``login``, ``key`` or ``credit`` when ``error`` needs the user, else ``None``."""
    if _CREDIT.search(error):
        return "credit"
    if _AUTH.search(error):
        return "login" if source == "claude" else "key"
    return None


def _connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    with con:
        con.executescript(_SCHEMA)
    return con


def raise_alert(home: Path, kind: str, source: str, run_id: int, detail: str,
                now: datetime, send: Sender | None = None, title: str = "") -> Alert | None:
    """Store an alert once per kind, source and New York day, and send it to Telegram.

    Args:
        home: Desk folder.
        kind: ``login``, ``key``, ``credit``, ``run_failed``, ``candles``, ``partial``,
            ``trade_stop``, ``trade_target``, ``plan_broken``, ``ticket_waiting`` or
            ``escalation``.
        source: The model source (``claude``, ``openrouter``) or empty.
        run_id: Desk run that found the problem.
        detail: What happened, in a line.
        now: Time-zone aware time.
        send: Sends one message; ``send_telegram`` when ``None``.
        title: Overrides the kind's title.

    Returns:
        The new alert, or ``None`` when the same problem was already raised today.
    """
    head, fix = _FIX[kind]
    stamp = now.astimezone(NY)
    key = f"{kind}|{source}|{stamp.date().isoformat()}"
    con = _connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT OR IGNORE INTO alerts (key, created, kind, source, run_id, title, text, "
                "fix) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (key, stamp.isoformat(timespec="seconds"), kind, source, run_id, title or head,
                 detail[:300], fix))
        if not cur.rowcount:
            _resend(con, key, send)
            return None
        alert = Alert(int(cur.lastrowid or 0), stamp, kind, source, run_id, title or head,
                      detail[:300], fix, False)
        log.warning("[AI Desk] Alert: %s", alert.title)
        if (send or send_telegram)(alert.message):
            with con:
                con.execute("UPDATE alerts SET sent = 1 WHERE id = ?", (alert.id,))
            alert = replace(alert, sent=True)
        return alert
    finally:
        con.close()


def _resend(con: sqlite3.Connection, key: str, send: Sender | None) -> None:
    """Send today's alert again when its first Telegram send failed."""
    row = con.execute("SELECT id, title, text, fix FROM alerts WHERE key = ? AND sent = 0",
                      (key,)).fetchone()
    if row is None:
        return
    message = f"AI Desk alert: {row[1]}\n{row[2]}\nWhat to do: {row[3]}"
    if (send or send_telegram)(message):
        with con:
            con.execute("UPDATE alerts SET sent = 1 WHERE id = ?", (row[0],))


def _read(home: Path, sql: str, params: tuple[object, ...]) -> list[tuple[object, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            return [tuple(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def open_alerts(home: Path, now: datetime) -> list[Alert]:
    """Alerts of the last day that are not fixed yet, newest first.

    A login, key or credit alert closes once its source gives a valid answer later; a whole-run
    alert closes once any valid answer comes later; a candles alert closes once a later morning
    or manual run ends ok; a partial alert closes once a later chain finishes in full.
    """
    since = (now - timedelta(hours=OPEN_HOURS)).astimezone(NY).isoformat(timespec="seconds")
    rows = _read(home, "SELECT id, created, kind, source, run_id, title, text, fix, sent "
                       "FROM alerts WHERE created >= ? ORDER BY id DESC", (since,))
    out: list[Alert] = []
    for aid, created, kind, source, run_id, title, text, fix, sent in rows:
        when = datetime.fromisoformat(str(created))
        if not _fixed(home, str(kind), str(source), when):
            out.append(Alert(int(str(aid)), when, str(kind), str(source), int(str(run_id)),
                             str(title), str(text), str(fix), bool(sent)))
    return out


def _fixed(home: Path, kind: str, source: str, when: datetime) -> bool:
    """True when something after ``when`` shows the alert's problem is gone."""
    if kind in MARKET_ALERTS:
        return False
    if kind in DATA_PROBLEMS:
        return bool(_read(home, "SELECT 1 FROM runs WHERE kind IN ('morning', 'manual') AND "
                                "result = 'ok' AND started_at > ? LIMIT 1", (utc_text(when),)))
    if kind == "ticket_waiting":
        rows = _read(home, "SELECT status FROM tickets WHERE id = ?", (int(source or 0),))
        return not rows or str(rows[0][0]) != "waiting"
    if kind == "partial":
        return bool(_read(home, "SELECT 1 FROM events WHERE note = 'chain full' AND handled > ? "
                                "LIMIT 1", (when.isoformat(timespec="seconds"),)))
    same = "AND source = ?" if kind in USER_PROBLEMS else ""
    params: tuple[object, ...] = (when.isoformat(timespec="seconds"), source) if same else (
        when.isoformat(timespec="seconds"),)
    return bool(_read(home, "SELECT 1 FROM activity WHERE valid = 1 AND started > ? "
                            f"{same} LIMIT 1", params))


def run_outcome(home: Path, run_id: int) -> tuple[int, int, str]:
    """Real LLM calls of a run, how many were valid, and the last error."""
    rows = _read(home, "SELECT COUNT(*), COALESCE(SUM(valid), 0) FROM activity WHERE run_id = ? "
                       "AND COALESCE(replay, 0) = 0 AND COALESCE(shadow, 0) = 0", (run_id,))
    last = _read(home, "SELECT error FROM activity WHERE run_id = ? AND valid = 0 "
                       "AND error != '' AND COALESCE(replay, 0) = 0 AND COALESCE(shadow, 0) = 0 "
                       "ORDER BY id DESC LIMIT 1", (run_id,))
    calls, valid = (int(str(rows[0][0])), int(str(rows[0][1]))) if rows else (0, 0)
    return calls, valid, str(last[0][0]) if last else ""


def last_error(home: Path, employee: str) -> str:
    """The newest error an employee's LLM calls gave; empty when there is none."""
    rows = _read(home, "SELECT error FROM activity WHERE employee = ? AND valid = 0 "
                       "AND error != '' AND COALESCE(replay, 0) = 0 ORDER BY id DESC LIMIT 1",
                 (employee,))
    return str(rows[0][0]) if rows else ""


def telegram_target(users_file: Path | None = None) -> tuple[str, str] | None:
    """Bot token and chat id of the first user with Telegram on, or ``None``."""
    try:
        users = json.loads((users_file or USERS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for user in users if isinstance(users, list) else []:
        chat = str(user.get("telegram_chat_id") or "").strip()
        if not user.get("telegram_enabled") or not chat:
            continue
        try:
            import keyring  # noqa: PLC0415 — slow import, only when needed

            token = keyring.get_password(TELEGRAM_SERVICE, str(user.get("user_id"))) or ""
        except Exception:  # noqa: BLE001 — no keychain means no Telegram
            token = ""
        if token:
            return token, chat
    return None


def send_telegram(text: str) -> bool:
    """Send ``text`` to the Telegram chat; False when Telegram is off or the send fails."""
    target = telegram_target()
    if target is None:
        log.info("[AI Desk] Telegram is off, so the alert shows only in the app")
        return False
    token, chat = target
    logging.getLogger("httpx").setLevel(logging.WARNING)  # the URL holds the bot token
    try:
        response = httpx.post(f"{_API}/bot{token}/sendMessage",
                              json={"chat_id": chat, "text": text}, timeout=10)
        response.raise_for_status()
    except Exception:  # noqa: BLE001 — an alert must never stop the desk
        log.warning("[AI Desk] Could not send the alert to Telegram")
        return False
    return True
