"""Unit tests for inbound Telegram commands (MD-INF-010.001.M10)."""
from __future__ import annotations

import json

import httpx

from us_swing.core.notifications import CommandRouter, TelegramPoller


class _FakePort:
    """A CommandPort double recording which queries the router calls."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.raise_on: str | None = None

    def _answer(self, name: str) -> str:
        self.calls.append(name)
        if self.raise_on == name:
            raise RuntimeError("boom")
        return name.upper()

    def status(self) -> str:
        return self._answer("status")

    def pnl(self) -> str:
        return self._answer("pnl")

    def positions(self) -> str:
        return self._answer("positions")

    def signals(self) -> str:
        return self._answer("signals")

    def screener(self) -> str:
        return self._answer("screener")

    def cycles(self) -> str:
        return self._answer("cycles")


# ── CommandRouter (M10.T01–T06) ──────────────────────────────────────────────

def test_route_dispatches_to_port():
    """UT-INF-010.001.M10.T01: /pnl calls the port and returns its reply."""
    port = _FakePort()
    reply = CommandRouter(port).route("/pnl")
    assert port.calls == ["pnl"]
    assert reply == "PNL"


def test_help_lists_all_commands():
    """UT-INF-010.001.M10.T02: /help returns every command."""
    reply = CommandRouter(_FakePort()).route("/help")
    assert reply is not None
    for token in ("/status", "/pnl", "/positions", "/signals", "/screener", "/cycles", "/help"):
        assert token in reply


def test_unknown_command_returns_hint():
    """UT-INF-010.001.M10.T03: an unknown command points at /help."""
    reply = CommandRouter(_FakePort()).route("/foo")
    assert reply is not None
    assert "/foo" in reply
    assert "/help" in reply


def test_plain_text_ignored():
    """UT-INF-010.001.M10.T04: non-command text returns None."""
    assert CommandRouter(_FakePort()).route("hello there") is None


def test_command_is_normalized():
    """UT-INF-010.001.M10.T05: case and a trailing @botname are stripped."""
    port = _FakePort()
    reply = CommandRouter(port).route("/PnL@usswing_bot")
    assert port.calls == ["pnl"]
    assert reply == "PNL"


def test_handler_error_returns_apology(caplog):
    """UT-INF-010.001.M10.T06: a raising handler yields a plain apology."""
    port = _FakePort()
    port.raise_on = "status"
    with caplog.at_level("ERROR"):
        reply = CommandRouter(port).route("/status")
    assert reply is not None
    assert "stack" not in reply.lower() and "Traceback" not in reply
    assert "Sorry" in reply
    assert any("[Notify]" in r.message for r in caplog.records)


# ── TelegramPoller (M10.T07–T08) ─────────────────────────────────────────────

def _poller(sent: list[httpx.Request], chat_id: str = "999") -> TelegramPoller:
    def _handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    return TelegramPoller("token", chat_id, client, CommandRouter(_FakePort()))


def _update(update_id: int, chat_id: str, text: str) -> dict[str, object]:
    return {"update_id": update_id, "message": {"text": text, "chat": {"id": chat_id}}}


async def test_authorized_update_replies_and_advances_offset():
    """UT-INF-010.001.M10.T07: an authorized command is answered; offset advances."""
    sent: list[httpx.Request] = []
    poller = _poller(sent)
    next_offset = await poller._process([_update(41, "999", "/help")], 0)
    assert next_offset == 42
    assert len(sent) == 1
    assert sent[0].url.path.endswith("/sendMessage")
    assert json.loads(sent[0].content)["parse_mode"] == "HTML"


async def test_register_commands_posts_setmycommands():
    """UT-INF-010.001.M10.T09: the poller registers its command menu with Telegram."""
    sent: list[httpx.Request] = []
    poller = _poller(sent)
    await poller._register_commands()
    assert len(sent) == 1
    request = sent[0]
    assert request.url.path.endswith("/setMyCommands")
    body = json.loads(request.content)
    names = [c["command"] for c in body["commands"]]
    assert names == ["status", "pnl", "positions", "signals", "screener", "cycles", "help"]
    assert all(c["description"] for c in body["commands"])


async def test_unauthorized_chat_ignored(caplog):
    """UT-INF-010.001.M10.T08: a command from another chat is unanswered."""
    sent: list[httpx.Request] = []
    poller = _poller(sent, chat_id="999")
    with caplog.at_level("WARNING"):
        next_offset = await poller._process([_update(7, "111", "/pnl")], 0)
    assert next_offset == 8
    assert sent == []
    assert any("[Notify]" in r.message for r in caplog.records)
