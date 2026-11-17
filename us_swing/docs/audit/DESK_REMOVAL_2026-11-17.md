# AI Desk Removal — Decision Note

**Date:** 2026-11-17 · **Decided by:** user · **Restore point:** git tag `desk-final` (main 969e9fe4)

The AI Desk was not built correctly, so it is being removed. The Market Floor is removed with it, because all of its real data comes from `desk.db`, which only the desk writes.

## User Decisions

| # | Decision |
|---|---|
| 1 | Remove the AI Desk and the Market Floor completely. |
| 2 | Keep the Telegram AI notes (FO-GUI-033). They use `core/notifications/_ai_client.py`, which uses no desk code. |
| 3 | Delete the old "AI Desk" strategy and its trade cycles and pending signals. |
| 4 | Delete the desk docs for good. The `desk-final` tag keeps a copy. |
| 5 | One PR per step (6 steps). |

## FOs Removed (43)

| Tool | FO IDs | Docs |
|---|---|---|
| DSK | FO-DSK-001 – FO-DSK-013 | `docs/desk/` (whole folder) |
| MKT | FO-MKT-001 – FO-MKT-021 | `docs/market/` (whole folder) |
| GUI | FO-GUI-034 – FO-GUI-041 | Rows inside `docs/gui/*.md` |
| EXE | FO-EXE-021 | Rows inside `docs/execution/*.md` |
| AGT | — | `docs/agt/` (whole folder) |

The user approved removing these FOs and all their SRDs, including the Approved, Implemented and Verified ones.

## FOs Kept

| FO | Reason |
|---|---|
| FO-GUI-033 AI Notes Settings | Telegram AI notes; no desk code |
| INF notification service, day-end P&L message | Not desk; `_briefs.py` only shares the "day end" name |

## Steps

| Step | Work | PR |
|---|---|---|
| 0 | Tag `desk-final`; back up `~/.usswing/desk` to `~/.usswing/desk_backup_20261117` | Done (no PR) |
| 1 | This note + TODO rows | `chore/desk-removal-requirements` |
| 2 | Cut desk and Floor links from `main_window`, `app_service`, `broker_adapter`, `strategy_engine/_engine`, `__main__` | — |
| 3 | Delete `desk/`, `market/`, `core/desk_*`, GUI desk and Floor files, `execution/desk_signals.py`, and their tests | — |
| 4 | Clean `USSwing.spec`, installer files, `pyproject.toml` (`pypdf`), MODULE_MAP files | — |
| 5 | Delete `docs/desk`, `docs/market`, `docs/agt`; remove the GUI and EXE rows above and TRACE rows; write the RN | — |
| 6 | Delete the "AI Desk" strategy, its cycles and pending signals, and the `~/.usswing/desk` folder | — |

Each step must pass ruff, mypy --strict, the full pytest run, and an app start check before its PR.
