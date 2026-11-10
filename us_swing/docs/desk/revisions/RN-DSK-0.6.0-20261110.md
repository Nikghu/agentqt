# Revision Note — RN-DSK-0.6.0-20261110

**Version:** 0.6.0
**Date:** 2026-11-10
**Tool:** DSK (with GUI)
**Artifact:** FO-DSK-008 / SRD-DSK-008.001–.009
**Type:** Feature

---

## Summary

Each AI employee is now one `employee.md` file: settings in a YAML block at the top, the system prompt below. Old `job.yaml` and `soul.md` pairs move into `history/` once, on desk seed and when Team setup opens. Every save checks the file, raises the version by one and keeps the old file as `history/v<N>.md`; restore saves an old version as the next version. A changed prompt can be tried on the employee's last recorded run with `desk replay RUN --employee ID --draft FILE --out FILE`, without saving.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-008.001.M22 | `core/desk_employee.py` (new) | Employee file rules, read and write, migration, versions, restore, draft test, known models; `JobSpec` moved here |
| MD-DSK-002.002.M09 | `desk/registry.py` | Rules from core (`JobSpec` re-exported); reads `employee.md`; migrates on seed; version hash taken from `employee.md` text |
| MD-DSK-006.001.M18 | `core/desk_hiring.py` | Hires write `employee.md` from the skill's default employee |
| MD-DSK-005.005.M17 | `desk/replay.py`, `desk/cli.py` | `--draft FILE` and `--out FILE` on `desk replay`; skips when the source is off |
| — | `market/employees/*/employee.md` | Shipped default employees as `employee.md` files, copied only when missing |
| MD-GUI-035.002.M02 | `core/desk_team.py` | Reads employee settings through `read_employee` |
| — | `desk/gateway.py` | Model default taken from the single `DEFAULT_MODEL` in core |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-008.001 | One `employee.md` per employee: YAML settings, prompt body | Implemented |
| SRD-DSK-008.002 | Job rules and file read and write live in core; app never imports desk | Implemented |
| SRD-DSK-008.003 | Old `job.yaml` and `soul.md` move to `employee.md` once; version unchanged | Implemented |
| SRD-DSK-008.004 | Shipped defaults are `employee.md`, copied only when missing | Implemented |
| SRD-DSK-008.005 | Save checks the file, raises version, keeps `history/v<N>.md`; refused save writes nothing | Implemented |
| SRD-DSK-008.006 | Restore saves the old version as the next version; history never deleted | Implemented |
| SRD-DSK-008.007 | Starting a hire writes `employee.md`; status shadow as before | Implemented |
| SRD-DSK-008.008 | `desk replay --draft` resends the recorded question with the draft prompt; no views, picks or briefs written | Implemented |
| SRD-DSK-008.009 | Level change refused when the new level's seats are full | Implemented |

---

## Design Decisions

- One `employee.md` per employee; the same check runs in the desk and the app (core).
- Save keeps every version in `history/v<N>.md`; restore never deletes history.
- Files are written atomically; header comment lines are kept on save.
- Restore keeps the current status (it does not wake or sleep the employee).
- Seat caps (SRD-DSK-006.002) apply to a level change as well as to a hire.
- Known: the first desk load after the upgrade logs one "files changed but version is still N" warning per employee, because the hash is now taken from the `employee.md` text.

---

## Issues Resolved

None

---

## Test Coverage

UT-DSK-008.001–.009: 17 cases, 19 test runs (including parametrized cases) in `tests/desk/test_employee_file.py`, all Pass. Desk and market suites: no new failures against a clean baseline of the previous commit (41 failures and errors already there, mostly a missing `langgraph` module and two news tests that fail to collect).
