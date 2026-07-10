"""Unit tests for the notification service (MD-INF-010.001.M01–M07)."""
from __future__ import annotations

import dataclasses

import httpx
import pytest

from us_swing.core.notifications import (
    DayEndPnLEvent,
    NotificationChannel,
    NotificationConfig,
    NotificationMessage,
    ScreenerApprovedEvent,
    ToolStartedEvent,
    build_default_dispatcher,
    default_registry,
    load_config,
)
from us_swing.core.notifications._dispatcher import NotificationDispatcher
from us_swing.core.notifications._events import NotificationEvent, _InProcessBus
from us_swing.core.notifications._formatters import FormatterRegistry
from us_swing.core.notifications._telegram import TelegramChannel


async def _no_sleep(_seconds: float) -> None:
    return None


class _RecordingChannel:
    def __init__(self, name: str = "rec") -> None:
        self.name = name
        self.received: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> None:
        self.received.append(message)


class _FailingChannel:
    def __init__(self, name: str = "fail", fail_times: int | None = None) -> None:
        self.name = name
        self.attempts = 0
        self._fail_times = fail_times

    async def send(self, message: NotificationMessage) -> None:
        self.attempts += 1
        if self._fail_times is None or self.attempts <= self._fail_times:
            raise RuntimeError("boom")


def _dispatcher(channels, registry=None, **kw) -> NotificationDispatcher:
    return NotificationDispatcher(
        _InProcessBus(),
        channels,
        registry or default_registry(),
        min_interval_s=0.0,
        sleep=_no_sleep,
        **kw,
    )


# ── _events.py (M01) ─────────────────────────────────────────────────────────

def test_screener_event_stores_symbols():
    """UT-INF-010.001.M01.T01: event keeps its symbols and schema version."""
    event = ScreenerApprovedEvent(symbols=("AAPL", "MSFT"))
    assert event.symbols == ("AAPL", "MSFT")
    assert event.schema_version == 1


def test_event_is_frozen():
    """UT-INF-010.001.M01.T02: mutating a built event is rejected."""
    event = ScreenerApprovedEvent(symbols=("AAPL",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.symbols = ()  # type: ignore[misc]


def test_bus_publish_calls_handler():
    """UT-INF-010.001.M01.T03: publish invokes a subscribed handler."""
    seen: list[object] = []
    bus = _InProcessBus()
    bus.subscribe(seen.append)
    event = ToolStartedEvent()
    bus.publish(event)
    assert seen == [event]


def test_bus_isolates_raising_handler():
    """UT-INF-010.001.M01.T04: a raising handler does not block siblings."""
    seen: list[object] = []

    def _boom(_event: object) -> None:
        raise RuntimeError("boom")

    bus = _InProcessBus()
    bus.subscribe(_boom)
    bus.subscribe(seen.append)
    bus.publish(ToolStartedEvent())  # must not raise
    assert len(seen) == 1


# ── _protocols.py (M02) ──────────────────────────────────────────────────────

def test_telegram_satisfies_channel_protocol():
    """UT-INF-010.001.M02.T01: TelegramChannel is a NotificationChannel."""
    channel = TelegramChannel("token", "chat", httpx.AsyncClient())
    assert isinstance(channel, NotificationChannel)


def test_plain_object_not_channel():
    """UT-INF-010.001.M02.T02: an object without send is not a channel."""
    assert not isinstance(object(), NotificationChannel)


# ── _telegram.py (M03) ───────────────────────────────────────────────────────

async def test_send_posts_sendmessage():
    """UT-INF-010.001.M03.T01: send POSTs sendMessage with chat id and text."""
    captured: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        channel = TelegramChannel("TESTTOKEN", "999", client)
        await channel.send(NotificationMessage("hello", "ToolStartedEvent"))

    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/botTESTTOKEN/sendMessage"
    assert b'"chat_id":"999"' in request.content
    assert b"hello" in request.content


async def test_send_raises_on_error_status():
    """UT-INF-010.001.M03.T02: a non-2xx response raises."""

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        channel = TelegramChannel("t", "c", client)
        with pytest.raises(httpx.HTTPStatusError):
            await channel.send(NotificationMessage("x", "ToolStartedEvent"))


# ── _dispatcher.py (M04) ─────────────────────────────────────────────────────

async def test_deliver_renders_and_sends():
    """UT-INF-010.001.M04.T01: a rendered event reaches an enabled channel."""
    channel = _RecordingChannel()
    dispatcher = _dispatcher([channel])
    message = default_registry().render(ToolStartedEvent(app_version="1.2"))
    await dispatcher.deliver(message)
    assert len(channel.received) == 1
    assert channel.received[0].text


async def test_channel_failure_isolated():
    """UT-INF-010.001.M04.T02: one channel failing still delivers to another."""
    bad = _FailingChannel(name="bad")
    good = _RecordingChannel(name="good")
    dispatcher = _dispatcher([bad, good], max_retries=0)
    await dispatcher.deliver(NotificationMessage("hi", "ToolStartedEvent"))
    assert len(good.received) == 1


async def test_retry_then_success():
    """UT-INF-010.001.M04.T03: a channel that fails once is retried."""
    flaky = _FailingChannel(name="flaky", fail_times=1)
    dispatcher = _dispatcher([flaky], max_retries=1)
    await dispatcher.deliver(NotificationMessage("hi", "ToolStartedEvent"))
    assert flaky.attempts == 2


async def test_retry_exhausted_logged_not_raised(caplog):
    """UT-INF-010.001.M04.T04: exhausted retries are logged, not raised."""
    always = _FailingChannel(name="always")
    dispatcher = _dispatcher([always], max_retries=1)
    with caplog.at_level("ERROR"):
        await dispatcher.deliver(NotificationMessage("hi", "ToolStartedEvent"))
    assert always.attempts == 2
    assert any("[Notify]" in r.message for r in caplog.records)


def test_dispatch_enqueues_without_blocking():
    """UT-INF-010.001.M04.T05: dispatch enqueues and returns immediately."""
    dispatcher = _dispatcher([_RecordingChannel()])
    dispatcher.dispatch(ToolStartedEvent())
    assert dispatcher.queue_size == 1


def test_dispatch_missing_formatter_swallowed(caplog):
    """UT-INF-010.001.M04.T06: an event with no formatter is dropped, not raised."""
    dispatcher = _dispatcher([_RecordingChannel()], registry=FormatterRegistry())
    with caplog.at_level("ERROR"):
        dispatcher.dispatch(ToolStartedEvent())  # empty registry -> no formatter
    assert dispatcher.queue_size == 0
    assert any("[Notify]" in r.message for r in caplog.records)


def test_dispatch_toggled_off_event_dropped():
    """UT-INF-010.001.M04.T07: an event kind toggled off is not enqueued."""
    dispatcher = _dispatcher(
        [_RecordingChannel()], event_toggles={"ToolStartedEvent": False}
    )
    dispatcher.dispatch(ToolStartedEvent())
    assert dispatcher.queue_size == 0


def test_dispatch_toggled_on_event_enqueued():
    """UT-INF-010.001.M04.T08: an event kind toggled on is enqueued."""
    dispatcher = _dispatcher(
        [_RecordingChannel()], event_toggles={"ToolStartedEvent": True}
    )
    dispatcher.dispatch(ToolStartedEvent())
    assert dispatcher.queue_size == 1


def test_dispatch_unknown_kind_defaults_on():
    """UT-INF-010.001.M04.T09: an event kind absent from the toggles map is sent."""
    dispatcher = _dispatcher(
        [_RecordingChannel()], event_toggles={"DayEndPnLEvent": False}
    )
    dispatcher.dispatch(ToolStartedEvent())  # not in the map -> default on
    assert dispatcher.queue_size == 1


# ── _formatters.py (M05) ─────────────────────────────────────────────────────

def test_render_screener_lists_symbols():
    """UT-INF-010.001.M05.T01: default registry lists the approved symbols."""
    message = default_registry().render(ScreenerApprovedEvent(symbols=("AAPL", "MSFT")))
    assert "AAPL" in message.text
    assert "MSFT" in message.text


def test_render_unregistered_raises_keyerror():
    """UT-INF-010.001.M05.T02: an unregistered event type raises KeyError."""
    registry = FormatterRegistry()
    with pytest.raises(KeyError, match="DayEndPnLEvent"):
        registry.render(DayEndPnLEvent())


def test_register_new_event_type():
    """UT-INF-010.001.M05.T03: a new event type renders without touching others."""

    @dataclasses.dataclass(frozen=True, slots=True)
    class _CustomEvent(NotificationEvent):
        note: str = ""

    registry = default_registry()
    registry.register(
        _CustomEvent,
        lambda e: NotificationMessage(f"custom: {e.note}", "_CustomEvent"),  # type: ignore[attr-defined]
    )
    assert registry.render(_CustomEvent(note="hi")).text == "custom: hi"
    assert "AAPL" in registry.render(ScreenerApprovedEvent(symbols=("AAPL",))).text


# ── _dto.py config (M06) ─────────────────────────────────────────────────────

def test_load_config_parses_telegram():
    """UT-INF-010.001.M06.T01: enabled telegram settings are parsed."""
    config = load_config(
        {
            "notifications": {
                "telegram": {"enabled": True, "bot_token": "abc", "chat_id": "123"},
                "events": {"ToolStartedEvent": True},
            }
        }
    )
    assert config == NotificationConfig(
        telegram_enabled=True,
        bot_token="abc",
        chat_id="123",
        event_toggles={"ToolStartedEvent": True},
    )


def test_load_config_missing_key_disabled():
    """UT-INF-010.001.M06.T02: missing notifications key yields a disabled config."""
    config = load_config({})
    assert config.telegram_enabled is False


def test_load_config_blank_token_disabled():
    """UT-INF-010.001.M06.T03: enabled with a blank token is treated as disabled."""
    config = load_config(
        {"notifications": {"telegram": {"enabled": True, "bot_token": "", "chat_id": "1"}}}
    )
    assert config.telegram_enabled is False


# ── __init__.py factory (M07) ────────────────────────────────────────────────

async def test_factory_enabled_builds_channel():
    """UT-INF-010.001.M07.T01: enabled config wires a Telegram channel."""
    config = NotificationConfig(
        telegram_enabled=True, bot_token="t", chat_id="c", event_toggles={}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200))
    ) as client:
        dispatcher, _bus = build_default_dispatcher(config, http=client)
        assert len(dispatcher.channels) == 1


def test_factory_disabled_no_channels_publish_noop():
    """UT-INF-010.001.M07.T02: disabled config has no channels; publish is a no-op."""
    config = load_config({})
    dispatcher, bus = build_default_dispatcher(config)
    assert dispatcher.channels == ()
    bus.publish(ToolStartedEvent())  # must not raise
    assert dispatcher.queue_size == 0


async def test_factory_passes_event_toggles_to_dispatcher():
    """UT-INF-010.001.M07.T03: a toggled-off event from config is dropped end-to-end."""
    config = NotificationConfig(
        telegram_enabled=True,
        bot_token="t",
        chat_id="c",
        event_toggles={"ToolStartedEvent": False},
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200))
    ) as client:
        dispatcher, bus = build_default_dispatcher(config, http=client)
        bus.publish(ToolStartedEvent())
        assert dispatcher.queue_size == 0
