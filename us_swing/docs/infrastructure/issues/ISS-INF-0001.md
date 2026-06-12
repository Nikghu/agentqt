# Issue Report — ISS-INF-0001

**Tool:** INF (Infrastructure) — auto-update stub (installer-tool utility)
**Severity:** High
**Status:** Resolved
**Date Opened:** 2026-06-10
**Date Resolved:** 2026-06-10
**Reporter:** User (USSwing)
**Resolution:** RN-INF-1.0.2-20260610

---

## Symptom

The v1.1.6 installed app did not detect the released v1.1.7 update. No error or
message was shown — the app behaved as if it were already up to date. No code
change to the updater existed between 1.1.6 and 1.1.7.

## Root Cause

`updater_stub.check_update_available()` called `_stamp_check_time()` **before**
fetching the update manifest from GitHub. The 24-hour throttle timestamp
(`.last_update_check`, written next to the executable) was therefore recorded even
when the subsequent fetch failed.

`_fetch_github_manifest()` swallows every exception and returns `None` at
`log.debug` level (invisible to the user). GitHub's unauthenticated REST API is
limited to **60 requests/hour per IP**; any 403 (rate limit), network blip, or SSL
error makes the fetch return `None`. Because the timestamp was already stamped, the
app would not re-poll for the full `interval_hours` (default 24) — turning a
transient failure into a silent day-long blackout.

## Diagnosis Evidence

- GitHub release v1.1.7 verified correct: `Latest`, not draft/prerelease, with
  `USSwing_1.1.7_Setup.exe` + `.sha256` assets; `/releases/latest` returns it.
- Baked `updater_config.json` for 1.1.6 correct: `enabled:true`,
  `github_repo:Nikghu/agentqt`, pattern `_Setup.exe`, `current_version:"1.1.6"`.
- Live reproduction: `_fetch_github_manifest("Nikghu/agentqt", cfg)` returned
  `None`; direct API call returned `HTTP 403 rate limit exceeded`;
  `/rate_limit` showed unauthenticated core `remaining: 0, used: 60`.
- Version compare logic itself is correct (`1.1.7 > 1.1.6`).

## Fix

Move `_stamp_check_time()` to run **only after** the manifest fetch succeeds (i.e.
the source actually answered — whether an update exists or the app is up to date).
A failed/unreachable poll no longer stamps the throttle, so the next launch retries
instead of going silent. Also raised the swallowed `releases/latest` fetch-failure
log from `debug` to `warning` so failures are visible.

Applied to both copies: `us_swing/src/updater_stub.py` (bundled into the app) and
`installer/updater_stub.py` (the canonical source copied at build time).

## Affected Artifacts

| Artifact | Change |
|---|---|
| `us_swing/src/updater_stub.py` | `check_update_available` stamps only after a successful fetch; GitHub fetch-failure log → `warning` |
| `installer/updater_stub.py` | Same fix mirrored (gitignored; on-disk for next build) |
| `us_swing/tests/infrastructure/test_updater_stub.py` | New — 3 regression tests (Pass) |

## Notes / Deviations

- The updater stub is a shared **installer-tool** utility, not part of the formal
  INF FO→SRD→…→UTCD chain (no existing SRD/MD/TRACE rows). Per the docs-separation
  rule it was not given a fabricated INF SRD row; this issue + the RN are the
  traceability record. The `installer/` directory is gitignored, so only the
  `us_swing/src` copy and the test are version-controlled.
- Pre-existing, out-of-scope: `updater_stub.py` has 10 `mypy --strict` errors in the
  RSA-verify / fetch helpers (crypto stub typing) that predate this fix.
