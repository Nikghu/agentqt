# Revision Note — RN-INF-1.2.0-20260709

**Tool:** INF
**Version:** 1.2.0
**Date:** 2026-07-09
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — FO-INF-010 (Telegram Notification Integration)

---

## Summary

Added a scalable, outbound notification service so the user gets live product
updates (tool started, screener approval with filtered stock names, day-end
P&L) on Telegram. It is a **business-event** service, intentionally separate
from FO-INF-005's log-level `AlertDispatcher`. The design is built for growth:
adding a new notification type or a new channel (email, Slack, SMS) never edits
existing code. Two-way bot commands are reserved as a documented design seam but
not implemented this phase.

## Architecture

Lives in `src/us_swing/core/notifications/` (in `core/` so the screener,
execution, and infrastructure tools all emit events without cross-tool imports).
Mirrors the `core/monitoring_session/` CQRS-lite pattern — frozen DTOs,
`Protocol`-typed seams, an in-process bus, a factory in `__init__`, concrete
classes not re-exported.

- **Events** (`_events.py`): frozen `NotificationEvent` variants —
  `ToolStartedEvent`, `ScreenerApprovedEvent(symbols)`, `DayEndPnLEvent`. A new
  notification kind is a new frozen subclass plus one formatter registration.
- **Formatter registry** (`_formatters.py`): maps event type → message renderer;
  new events register without touching the dispatcher.
- **Channel** (`_protocols.py`, `_telegram.py`): `NotificationChannel` Protocol
  with async `send`; `TelegramChannel` delivers via the Telegram Bot API over
  HTTP using an injected `httpx.AsyncClient` (no heavy SDK).
- **Dispatcher** (`_dispatcher.py`): subscribes to the bus, renders, enqueues
  (producer never blocks), and a worker fans out to every channel with per-chat
  rate limiting, bounded retry-with-backoff, and per-channel failure isolation —
  one channel's failure never affects another or the caller.
- **Config** (`_dto.py`): per-user `NotificationConfig` parsed from the existing
  `settings_json` (FO-INF-006); a half-configured Telegram (blank token/chat id)
  reads as disabled.
- **Factory** (`__init__.py`): `build_default_dispatcher(config, http=...)` wires
  only the channels the config enables; disabled Telegram → zero channels and a
  no-op publish.

## Behaviour Changes

- New standalone package; nothing else in the app calls it yet. Producer wiring
  (AppService emitting events, running `dispatcher.run()`) is a follow-up.
- New declared dependency: `httpx>=0.27` (was already present transitively via
  `openai`).

## Code Changes

| File | Change | SRD |
|---|---|---|
| `core/notifications/_events.py` | Frozen event variants + `_InProcessBus` | SRD-INF-010.001 |
| `core/notifications/_protocols.py` | `NotificationChannel`, `NotificationBus` Protocols | SRD-INF-010.002 |
| `core/notifications/_telegram.py` | `TelegramChannel` over Bot API HTTP | SRD-INF-010.003 |
| `core/notifications/_dispatcher.py` | `NotificationDispatcher` — queue, rate limit, retry, isolation | SRD-INF-010.004, .007 |
| `core/notifications/_formatters.py` | `FormatterRegistry` + default formatters | SRD-INF-010.005 |
| `core/notifications/_dto.py` | `NotificationMessage`, `NotificationConfig`, `load_config` | SRD-INF-010.006 |
| `core/notifications/__init__.py` | Public surface + `build_default_dispatcher` | SRD-INF-010.008 |
| `pyproject.toml` | Declare `httpx>=0.27` | — |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Tool-started / screener-approval / day-end PnL events render | ✅ | M01/M05 tests |
| Pluggable channel abstraction; new channel needs no dispatcher edit | ✅ | Protocol + factory design; M02 |
| Telegram delivery via Bot API with token + chat id | ✅ | UT-…M03.T01 |
| New event type without editing existing code | ✅ | UT-…M05.T03 |
| Per-user config from settings_json | ✅ | UT-…M06.T01–T03 |
| Delivery failure never crashes the caller | ✅ | UT-…M04.T02, .T04, .T06 |
| Inbound command seam reserved, not implemented | ✅ | Documented in DD-INF-010.001.D01 (SRD-INF-010.009) |

## Tests

| Check | Result |
|---|---|
| `tests/core/notifications/test_notifications.py` | 22 passed |
| `ruff check` (src + tests) | Clean |
| `mypy --strict` (7 source files) | No issues |

## Notes / Deviations

- SRD-INF-010.009 (inbound two-way command seam) is Approved but deliberately
  left unimplemented this phase — the `CommandChannel`/`CommandRouter` shape is
  documented in the DD so it slots in later without reworking the outbound path.
- Follow-up (not this phase): wire producers (AppService → `bus.publish(...)`),
  run `dispatcher.run()` as a background task, and add a GUI settings field for
  the per-user bot token/chat id.

---

**Commit:** pending — Refs: MD-INF-010.001.M01–M07
