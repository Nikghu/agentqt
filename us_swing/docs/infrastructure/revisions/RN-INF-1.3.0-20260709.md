# Revision Note — RN-INF-1.3.0-20260709

**Tool:** INF (+ GUI wiring)
**Version:** 1.3.0
**Date:** 2026-07-09
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — FO-INF-010 wiring (producers + GUI so notifications actually send)

---

## Summary

RN-INF-1.2.0 built the notification library but nothing called it. This wires it
into the running app so the user actually receives Telegram messages for the three
events: tool started, screener approved (with filtered stock names), and day-end P&L.

## Design

- **No app-wide asyncio loop** (the app is Qt/`QThread`). So the async dispatcher runs
  in a dedicated `NotificationWorker(QThread)` with its own event loop + one
  `httpx.AsyncClient`. GUI-thread producers call `publish_event`, which marshals onto
  the loop with `call_soon_threadsafe` (`asyncio.Queue` is not thread-safe).
- **Token is a secret** → stored in the OS keychain via `keyring` (mirrors
  `screener/screeners/_api_key_store.py`), never in `users.json`. The non-secret enable
  flag + chat id ride in the user store.
- **Triggers** (SRD-INF-010.010): startup → `ToolStartedEvent`;
  `AppService._on_screener_results_updated` → `ScreenerApprovedEvent(symbols)` (boot
  reloads excluded); NYSE open→closed in `_refresh_market_status` → `DayEndPnLEvent`
  (from `AccountState.daily_pnl` + open positions).
- Notifications are best-effort: `_start_notifications` is guarded so a failure never
  blocks app startup; `publish_notification` no-ops when the worker isn't ready.

## Behaviour Changes

- System Settings gains a **Telegram Notifications** section: enable checkbox, bot
  token (masked), chat id, and a **Send Test** button that delivers a message
  immediately so the user can confirm setup.
- Saving reconfigures the worker live (no restart needed).
- New declared dependency behaviour: `keyring` (already a dep) now also stores the
  Telegram token; a mypy override for the untyped `keyring` module was added.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `gui/notification_worker.py` (new) | `NotificationWorker(QThread)` — async dispatcher host | SRD-INF-010.004, .010 |
| `gui/telegram_token_store.py` (new) | Per-user bot token in OS keychain | SRD-INF-010.011 |
| `gui/app_service.py` | Build/lifecycle worker; publish 3 events; reconfigure/send_test/shutdown | SRD-INF-010.010 |
| `gui/settings_panel.py` | Telegram settings section + save + Send Test | SRD-INF-010.010/.011 |
| `gui/user_store.py`, `data/models.py` | Round-trip `telegram_enabled` / `telegram_chat_id` | SRD-INF-010.011 |
| `gui/main_window.py` | `shutdown_notifications()` on close | SRD-INF-010.010 |
| `pyproject.toml` | mypy override for the untyped `keyring` module | — |

## Tests

| Check | Result |
|---|---|
| `tests/gui/test_telegram_settings.py` | 5 passed (token keychain round-trip via fake backend + user-store persistence) |
| `tests/core/notifications/` | 22 passed (unchanged) |
| `ruff check` | Clean on all new/changed modules (`app_service.py` retains only its pre-existing debt) |
| `mypy --strict` | Clean on `notification_worker.py` + `telegram_token_store.py` |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Tool-started message on launch | ✅ | `_on_notifications_ready` → `ToolStartedEvent` |
| Screener-approval message with stock names | ✅ | `_on_screener_results_updated` emit |
| Day-end P&L on market close | ✅ | `_refresh_market_status` open→closed emit |
| Token stored securely (keychain, not users.json) | ✅ | `telegram_token_store` + UT-…M08.T01–T03 |
| Settings survive restart | ✅ | UT-…M08.T04–T05 |
| Send Test delivers immediately | ✅ | `send_test_notification` + Send Test button |

## Notes / Deviations

- SRD-INF-010.006 named `settings_json`; the running GUI persists users via
  `gui/user_store.py` (flat file) + keychain, not the DB `settings_json` path — the
  secret-token rule in `user_store.py` mandates the keychain. `.011` records this.
- Full end-to-end against the real Telegram Bot API needs the user's own bot token +
  chat id; **Send Test** in System Settings is the hand-off point. The worker's own
  async loop is not covered by an automated network test (core dispatcher delivery is).
- Follow-ups: inbound two-way commands (SRD-INF-010.009); per-event toggles in the UI;
  a scheduled day-end independent of the app being open at 16:00 ET.

---

**Commit:** pending — Refs: MD-INF-010.001.M08–M09
