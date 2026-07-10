# Revision Note — RN-INF-1.6.0-20260710

**Tool:** INF (+ GUI)
**Version:** 1.6.0
**Date:** 2026-07-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Enhancement + fix — Telegram bot polish (FO-INF-010) and a scheduler crash fix

---

## Summary

Pre-release polish for the Telegram bot plus one Windows crash fix:

1. **Command menu** — the bot now registers its commands with Telegram, so the chat
   shows the tap-to-run menu and `/` autocomplete.
2. **Professional replies** — command answers use HTML formatting (bold headers,
   status emojis, monospace tables) instead of flat text.
3. **Richer `/screener`** — each stock now shows its score, last price + day % change,
   and the preset that matched it, ranked and top-10 capped.
4. **Scheduler crash fix** — the TWS auto-login window finder no longer crashes on
   64-bit window handles.

## Design

- **Command registration (SRD-INF-010.012).** `TelegramPoller._register_commands`
  POSTs `setMyCommands` once when polling starts (best-effort: a failure only means the
  user misses the menu, never stops polling). A single `_COMMANDS` list is the source of
  truth for both the `/help` reply and the registration, so they can never drift.
- **HTML formatting.** Replies are sent with `parse_mode: "HTML"`; every dynamic value
  is `html.escape`d so a stray `&` or `<` cannot break rendering. `/status`, `/pnl`,
  `/positions`, `/signals`, `/screener`, `/cycles` gained bold titles, 🟢/🔴 status dots,
  and monospace `<pre>` tables where columns need to align.
- **`/screener` enrichment.** Results are sorted by score, capped at 10 (with a
  “+N more” line), and the last two daily bars per symbol are pulled in one
  `get_candles_bulk` round-trip to show last price and day % change; a symbol with no
  candle data shows “—”. A freshness header shows the run date/time.
- **Scheduler handle overflow.** `scheduler_dialog._user32()` declares proper
  `argtypes`/`restype` on the `user32` functions so 64-bit `HWND`s marshal as pointers
  rather than a default 32-bit C `int` (which raised `OverflowError: int too long to
  convert` on every enumerated window and truncated returned handles).

## Behaviour Changes

- The Telegram chat now shows a command menu, and command replies look formatted.
- `/screener` shows score, price, day change, and preset per stock (was bare symbols).
- TWS auto-login no longer spams handle-overflow errors and can actually find the window.

## Code Changes

| File | Change |
|---|---|
| `core/notifications/_inbound.py` | `_COMMANDS` source of truth; `_register_commands` (setMyCommands); `parse_mode: HTML` + escaped unknown-command hint; HTML `/help` header |
| `gui/telegram_commands.py` | HTML formatters for all six commands; `/screener` score/price/%chg/preset, ranked + top-10 |
| `gui/scheduler_dialog.py` | `_user32()` prototype configurator; routed the three `user32` acquisitions through it |

## Tests

| Check | Result |
|---|---|
| `tests/core/notifications/test_inbound.py` | +1 (setMyCommands payload) + parse_mode assertion; 9 pass |
| `tests/gui/test_telegram_commands.py` | +1 (`/screener` ranking, price, %chg, preset); formatter assertions updated; 4 pass |
| Full notification + Telegram suite | 49 passed |
| Scheduler fix | Verified live on Windows — `_find_tws_hwnd()` enumerates all windows with no `OverflowError` |
| `ruff` / `mypy --strict` | Clean on all changed files (`_inbound.py` strict-clean; GUI retains pre-existing debt) |

## Notes / Deviations

- Outbound event messages (tool started, screener approved, day-end P&L) are still plain
  text — a follow-up could give them the same HTML treatment.
- The scheduler fix lives in the GUI-tool `scheduler_dialog.py`; it is bundled here as a
  pre-release fix rather than carrying its own INF revision.

---

**Commit:** release branch `release/telegram-polish-scheduler-fix` — Refs: MD-INF-010.001.M10, M11
