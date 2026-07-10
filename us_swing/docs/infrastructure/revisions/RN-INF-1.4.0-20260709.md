# Revision Note — RN-INF-1.4.0-20260709

**Tool:** INF (+ GUI wiring)
**Version:** 1.4.0
**Date:** 2026-07-09
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — FO-INF-010 inbound two-way commands (SRD-INF-010.012–.015; realises .009)

---

## Summary

Adds inbound Telegram commands so the user can query live app state from their chat.
Seven read-only commands are answered: `/help`, `/status`, `/pnl`, `/positions`,
`/signals`, `/screener`, `/cycles`. This turns the previously reserved inbound seam
(SRD-INF-010.009) into a working feature.

## Design

- **Receive = long-poll, not webhook (SRD-INF-010.012).** A desktop app has no public
  URL, so `TelegramPoller` calls `getUpdates` with a long timeout on the existing
  notification loop and tracks `offset = last_update_id + 1` so each message is handled
  once. It reuses the worker's shared `httpx.AsyncClient` and runs only when Telegram is
  enabled — mirroring how a dispatcher with no channels is a safe no-op.
- **Authorization (SRD-INF-010.013).** Only the configured `chat_id` is honored; every
  other sender is dropped and logged under `[Notify]`. The bot never answers or leaks
  state to an unconfigured chat.
- **Routing (SRD-INF-010.014).** `CommandRouter` parses the leading token (strips `/`
  and a trailing `@botname`, lowercases), dispatches through a table, answers `/help`
  statically, returns a help hint for unknown commands, and converts a handler error
  into a plain apology — never a stack trace. All commands are read-only.
- **Thread safety (SRD-INF-010.015).** The router depends only on a `CommandPort`
  Protocol, never on the GUI. The poller runs on the notification thread but app state
  lives on the GUI thread, so `TelegramCommandBridge` marshals every query onto the GUI
  thread with a blocking queued signal + a `concurrent.futures.Future`; the poller keeps
  its asyncio loop free via `run_in_executor`. A same-thread fast path avoids a deadlock
  when called on the GUI thread (and in tests).

## Behaviour Changes

- With Telegram enabled, the bot now also *listens*: sending `/pnl` (etc.) from the
  configured chat returns a live summary. No new configuration — the existing per-user
  bot token and chat id drive both outbound and inbound.
- No user-visible GUI change; inbound starts/stops with the notification worker.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `core/notifications/_inbound.py` (new) | `TelegramPoller` (getUpdates long-poll + chat auth) + `CommandRouter` (7-command dispatch) | SRD-INF-010.012, .013, .014 |
| `core/notifications/_protocols.py` | `CommandPort` read-only query Protocol | SRD-INF-010.014 |
| `core/notifications/__init__.py` | `build_command_poller` factory + exports | SRD-INF-010.012 |
| `gui/telegram_commands.py` (new) | `TelegramCommandBridge` — `CommandPort` adapter, GUI-thread marshalling + reply formatting | SRD-INF-010.015 |
| `gui/notification_worker.py` | Accepts a `CommandPort`; hosts the poller task alongside the dispatcher | SRD-INF-010.012 |
| `gui/app_service.py` | Builds the bridge and passes it to the worker | SRD-INF-010.015 |

## Tests

| Check | Result |
|---|---|
| `tests/core/notifications/test_inbound.py` | 8 passed (router dispatch, help, unknown, plain-text ignore, normalization, handler-error apology; poller reply + offset, unauthorized-chat drop) |
| `tests/gui/test_telegram_commands.py` | 3 passed (CommandPort conformance, positions formatting, flat-account P&L) |
| `tests/core/notifications/` + `tests/gui/test_telegram_settings.py` | 35 passed (no regressions) |
| `ruff check` | Clean on all new/changed modules (`app_service.py` retains only its pre-existing debt) |
| `mypy --strict` | Clean on `_inbound.py`, `_protocols.py`, `telegram_commands.py`, `notification_worker.py`, `__init__.py` |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| `/pnl` returns the current P&L summary | ✅ | `TelegramCommandBridge._pnl` + UT-…M11.T03 |
| `/help` lists every command | ✅ | UT-…M10.T02 |
| Unknown command points at `/help` | ✅ | UT-…M10.T03 |
| Only the configured chat is answered | ✅ | UT-…M10.T08 (unauthorized chat dropped) |
| Each update handled once (offset advances) | ✅ | UT-…M10.T07 |
| Handlers run safely off the notification thread | ✅ | GUI-thread marshalling in `TelegramCommandBridge` |

## Notes / Deviations

- The `getUpdates`/`sendMessage` loop is unit-tested against `httpx.MockTransport`;
  full end-to-end against the real Bot API still needs the user's own token + chat id.
- The reserved `CommandChannel` Protocol from the original DD sketch was dropped in
  favour of the single used seam `CommandPort` (avoids speculative dead code); SRD-INF-
  010.009 is recorded as realised by .012–.015.
- Per-event notification toggles (the second half of the original request) remain a
  follow-up: `NotificationConfig.event_toggles` is parsed but not yet enforced, and the
  Settings UI has no per-event switches.

---

**Commit:** pending — Refs: MD-INF-010.001.M10–M11
