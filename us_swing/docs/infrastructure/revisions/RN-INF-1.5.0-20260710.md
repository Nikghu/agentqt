# Revision Note — RN-INF-1.5.0-20260710

**Tool:** INF (+ GUI wiring)
**Version:** 1.5.0
**Date:** 2026-07-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature follow-up — FO-INF-010 per-event toggles (SRD-INF-010.006) + day-end delivery (SRD-INF-010.010)

---

## Summary

Closes the three remaining FO-INF-010 follow-ups:

1. **Per-event toggles are now enforced.** The user can choose which of the three
   notifications they receive (tool started, screener approved, day-end P&L).
2. **The day-end P&L summary is delivered at market close**, once per trading day,
   whenever the app is open — no longer dependent on catching the exact status flip.
3. **A latent bug** that always reported unrealised P&L as `0.0` is fixed.

## Design

- **Toggle enforcement (SRD-INF-010.006).** `NotificationDispatcher` gains an
  `event_toggles` map. After rendering, `dispatch()` drops any message whose
  `event_kind` is toggled off; an unknown kind defaults to on, so a new event type is
  never silently swallowed. `build_default_dispatcher` passes `config.event_toggles`
  straight through — no other call site changes.
- **Per-user storage.** Three flat `UserProfile` booleans
  (`notify_tool_started`, `notify_screener_approved`, `notify_day_end_pnl`, all default
  **True**) mirror the existing `telegram_enabled`/`telegram_chat_id` fields and
  round-trip through `user_store`. `AppService._build_notification_config` maps them into
  the `notifications.events` dict that `load_config` already parses. Settings → Telegram
  gains a "Notify on:" row with three checkboxes.
- **Day-end at market close (SRD-INF-010.010).** `_refresh_market_status` (60 s tick)
  calls `_maybe_publish_day_end` whenever the exchange is in the `after_hours` window
  (16:00–20:00 ET). `after_hours` only occurs on real trading days, so weekends and
  holidays are excluded for free. A `_day_end_sent_date` guard sends exactly once per
  day, and the send is skipped (guard not consumed) until the notification worker is up,
  so a summary is never lost during startup. In-app only — the app must be open at close,
  which the user confirmed is the intended scope.

## Behaviour Changes

- Settings → Telegram now has three "Notify on:" switches. Existing users keep all three
  on (default True) so nothing changes for them after upgrade.
- The day-end P&L message now shows a correct unrealised figure and arrives reliably at
  market close while the app is open.
- **Known interaction:** *Send Test* fires a `ToolStartedEvent`; if "Tool started" is
  toggled off and saved, Send Test is dropped. Left as-is pending a user decision.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `core/notifications/_dispatcher.py` | `event_toggles` param; drop toggled-off events in `dispatch` | SRD-INF-010.006 |
| `core/notifications/__init__.py` | Factory passes `config.event_toggles` to the dispatcher | SRD-INF-010.006 |
| `data/models.py` | Three `notify_*` bool fields on `UserProfile` (default True) | SRD-INF-010.006 |
| `gui/user_store.py` | Round-trip the three toggle fields | SRD-INF-010.006 |
| `gui/settings_panel.py` | "Notify on:" row with three checkboxes; save handler writes them | SRD-INF-010.006 |
| `gui/app_service.py` | `_build_notification_config` maps toggles into `events`; `_maybe_publish_day_end` guarded once-per-day trigger on `after_hours`; fixed `unrealised_pnl` spelling | SRD-INF-010.006, .010 |

## Tests

| Check | Result |
|---|---|
| `tests/core/notifications/test_notifications.py` | +4 (M04.T07–09 toggle enforcement, M07.T03 factory pass-through) |
| `tests/gui/test_telegram_settings.py` | +2 (M08.T06–07 toggle round-trip + legacy default) |
| `tests/gui/test_day_end_notification.py` (new) | +3 (M09.T01–03 once-per-day guard + worker-not-ready skip) |
| Full notification + telegram suite | 36 passed |
| `ruff check` | Clean on all touched files (`app_service.py` retains only its pre-existing debt) |
| `mypy --strict` | Clean on `core/notifications/` |

## Notes / Deviations

- The day-end trigger uses the existing 60 s market-status poll rather than a second
  timer — the exchange already flips to `after_hours` at 16:00 ET, so no extra timer is
  needed and the summary arrives within a minute of close.
- 9 failures in `tests/gui/test_app_service_tick.py` are **pre-existing on clean HEAD**
  (real Yahoo `^GSPC` data leaks into the tick tests) and are unrelated to this change.
- Full end-to-end against the real Bot API still needs the user's own token + chat id.

---

**Commit:** pending — Refs: MD-INF-010.001.M04, M09
