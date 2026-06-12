# Revision Note — RN-INF-1.0.2-20260610

**Tool:** INF
**Version:** 1.0.2
**Date:** 2026-06-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bugfix — ISS-INF-0001 (auto-update silent 24-hour blackout)

---

## Summary

Fixes the in-app auto-updater so a **failed update check no longer suppresses
updates for 24 hours**. The v1.1.6 app was not detecting the v1.1.7 release because
`check_update_available()` stamped its once-per-day throttle **before** contacting
GitHub; when that fetch failed (GitHub 60-req/hr rate limit, network blip, SSL) the
exception was swallowed silently but the throttle was already burned, so the app
would not re-poll until the interval elapsed.

## Behaviour Changes

- The throttle timestamp (`.last_update_check`) is now written **only after the
  update source actually answers** (update found *or* already up to date). A failed
  or unreachable poll leaves the throttle unstamped, so the next app launch retries.
- The swallowed `releases/latest` fetch failure now logs at **WARNING** (was DEBUG),
  so a blocked/failed check is visible instead of silent.
- No change to version comparison, download, checksum verification, or the publish
  pipeline — those were already correct.

## Code Changes

| File | Change |
|---|---|
| `us_swing/src/updater_stub.py` | Move `_stamp_check_time()` to after a successful manifest fetch; GitHub fetch-failure log `debug` → `warning`; docstring updated |
| `installer/updater_stub.py` | Same fix mirrored (canonical source copied at build time; gitignored — on-disk only) |
| `us_swing/tests/infrastructure/test_updater_stub.py` | New — 3 regression tests |

## Tests

| Check | Result |
|---|---|
| `tests/infrastructure/test_updater_stub.py` | 3 passed (failed-fetch no-stamp, update stamps, up-to-date stamps) |
| `tests/infrastructure/` full | 44 passed |
| `ruff check` | Clean on changed files |
| `mypy --strict` | No new errors (10 pre-existing crypto-helper typing errors unchanged) |

## Notes / Deviations

- The updater stub is a shared **installer-tool** utility, outside the formal INF
  FO→SRD→…→UTCD chain (no existing SRD/MD/TRACE rows). No fabricated SRD row was
  added; ISS-INF-0001 + this RN are the traceability record.
- Operational note for the user: the unauthenticated GitHub API allows 60 req/hr per
  IP. On a shared/NAT'd network this can still 403; with this fix the app simply
  retries next launch instead of going dark for a day.

---

**Commit:** pending — Refs: ISS-INF-0001
