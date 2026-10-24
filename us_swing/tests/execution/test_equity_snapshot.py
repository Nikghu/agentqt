"""Tests for account equity snapshots (FO-EXE-020)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from us_swing.execution.equity_snapshot import (
    EquitySnapshot,
    EquitySnapshotRepository,
    slot_iso,
)
from us_swing.gui.app_service import AppService

_T0 = datetime(2026, 10, 24, 13, 30, tzinfo=timezone.utc)   # 09:30 ET


def _at(minute: int, day: int = 24, second: int = 0) -> datetime:
    return datetime(2026, 10, day, 13 + minute // 60, minute % 60, second, tzinfo=timezone.utc)


@pytest.fixture()
def repo() -> EquitySnapshotRepository:
    return EquitySnapshotRepository(sa.create_engine("sqlite:///:memory:", future=True))


def test_table_created():
    """UT-EXE-020.001.M01.T01: Repository creates the table and its index."""
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    EquitySnapshotRepository(engine)
    inspector = sa.inspect(engine)
    assert "equity_snapshots" in inspector.get_table_names()
    assert {c["name"] for c in inspector.get_columns("equity_snapshots")} == {
        "user_id", "taken_at", "equity", "cash", "unrealised_pnl"}


def test_slot_floors_to_five_minutes():
    """UT-EXE-020.002.M01.T01: Times are floored to their 5-minute slot in UTC."""
    assert slot_iso(_at(34, second=59)) == "2026-10-24T13:30:00"
    assert slot_iso(_at(35)) == "2026-10-24T13:35:00"


def test_same_slot_keeps_latest(repo):
    """UT-EXE-020.002.M01.T02: A second save in the same slot replaces the first."""
    repo.record(1, 25_000.0, 13_000.0, 10.0, _at(31))
    repo.record(1, 25_050.0, 13_000.0, 60.0, _at(33))
    points = repo.between("2026-10-24T00:00:00")
    assert points == (EquitySnapshot("2026-10-24T13:30:00", 25_050.0, 13_000.0, 60.0),)


def test_half_hour_gives_seven_points(repo):
    """UT-EXE-020.003.M01.T01: 09:30–10:00 every 5 minutes gives 7 points in time order."""
    for minute in range(30, 61, 5):
        repo.record(1, 25_000.0 + minute, 13_000.0, 0.0, _at(minute))
    points = repo.between("2026-10-24T00:00:00", user_id=1)
    assert len(points) == 7
    assert [p.taken_at for p in points] == sorted(p.taken_at for p in points)
    assert points[-1].equity == 25_060.0


def test_all_users_summed_per_slot(repo):
    """UT-EXE-020.003.M01.T02: No user sums every user in each slot; one user is filtered."""
    repo.record(1, 25_000.0, 10_000.0, 5.0, _at(30))
    repo.record(2, 10_000.0, 4_000.0, -2.0, _at(30))
    repo.record(2, 10_100.0, 4_000.0, 8.0, _at(35))
    every = repo.between("2026-10-24T00:00:00")
    assert every[0] == EquitySnapshot("2026-10-24T13:30:00", 35_000.0, 14_000.0, 3.0)
    assert [p.equity for p in repo.between("2026-10-24T00:00:00", user_id=1)] == [25_000.0]


def test_range_limits(repo):
    """UT-EXE-020.003.M01.T03: Points outside the start and end are left out; empty is empty."""
    for minute in (30, 35, 40):
        repo.record(1, 1.0, 1.0, 0.0, _at(minute))
    points = repo.between("2026-10-24T13:35:00", "2026-10-24T13:35:00")
    assert [p.taken_at for p in points] == ["2026-10-24T13:35:00"]
    assert repo.between("2026-10-25T00:00:00") == ()


def test_prune_removes_old_rows(repo):
    """UT-EXE-020.005.M01.T01: Rows older than 30 days are deleted, newer rows stay."""
    repo.record(1, 1.0, 1.0, 0.0, datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc))
    repo.record(1, 2.0, 1.0, 0.0, _at(30))
    assert repo.prune(_T0) == 1
    assert [p.equity for p in repo.between("2000-01-01T00:00:00")] == [2.0]
    assert repo.prune(_T0) == 0


# ── AppService wiring (SRD-EXE-020.004 / .006) ────────────────────────────────


def _svc(repo, nyse: str = "open", live: bool = False) -> SimpleNamespace:
    positions = {1: [SimpleNamespace(unrealised_pnl=12.5)],
                 2: [SimpleNamespace(unrealised_pnl=-2.5)]}
    svc = SimpleNamespace(
        _equity_store=repo, _equity_last_slot="", _equity_warned_slot="",
        _equity_was_open=False, _equity_pruned_on=None, _market_status={"nyse": nyse},
        _ibkr_acct=object() if live else None, _active_uid=2, _viewing_uid=None,
        _users=[SimpleNamespace(user_id=1), SimpleNamespace(user_id=2)],
        get_account_state=lambda uid: SimpleNamespace(equity=1000.0 * uid,
                                                      total_cash_value=500.0),
        get_positions=lambda uid: positions[uid],
    )
    svc._prune_equity_daily = lambda store, moment: AppService._prune_equity_daily(
        svc, store, moment)   # type: ignore[arg-type]
    return svc


def _read(svc, since: str = "2026-10-24T00:00:00"):
    return AppService.get_equity_snapshots(svc, since)   # type: ignore[arg-type]


def test_saves_each_user_once_per_slot(repo):
    """UT-EXE-020.004.M02.T01: Market open saves every user once per slot."""
    svc = _svc(repo)
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    AppService._record_equity_snapshots(svc, _at(33))   # same slot, skipped
    AppService._record_equity_snapshots(svc, _at(36))
    assert [p.equity for p in repo.between("2026-10-24T00:00:00")] == [3000.0, 3000.0]
    assert repo.between("2026-10-24T00:00:00", user_id=1)[0].unrealised_pnl == 12.5


def test_no_save_when_market_closed(repo):
    """UT-EXE-020.004.M02.T02: Nothing is saved while NYSE is not open."""
    svc = _svc(repo, nyse="after_hours")
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    assert repo.between("2000-01-01T00:00:00") == ()


def test_live_account_saved_once(repo):
    """UT-EXE-020.004.M02.T03: A live broker account is saved once, under the active user."""
    svc = _svc(repo, live=True)
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    assert repo.between("2000-01-01T00:00:00", user_id=1) == ()
    assert repo.between("2000-01-01T00:00:00", user_id=2)[0].equity == 2000.0


def test_failed_save_logs_and_retries(repo, caplog):
    """UT-EXE-020.004.M02.T04: A failed save logs a warning and the slot is tried again."""
    svc = _svc(repo)
    svc.get_account_state = lambda uid: (_ for _ in ()).throw(RuntimeError("db locked"))
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    AppService._record_equity_snapshots(svc, _at(32))   # type: ignore[arg-type]
    assert caplog.text.count("[Equity] Could not save the equity snapshot") == 1
    assert svc._equity_last_slot == ""


def test_read_for_viewing_scope(repo):
    """UT-EXE-020.006.M02.T01: Reads follow the viewing user; no store gives empty."""
    svc = _svc(repo)
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    assert _read(svc)[0].equity == 3000.0
    svc._viewing_uid = 1
    assert _read(svc)[0].equity == 1000.0
    svc._equity_store = None
    assert _read(svc) == ()


def test_closing_point_saved_once(repo):
    """UT-EXE-020.004.M02.T05: The first check after the close saves the 16:00 slot, then stops."""
    svc = _svc(repo)
    AppService._record_equity_snapshots(svc, _at(415))   # 15:55 ET, open  # type: ignore[arg-type]
    svc._market_status = {"nyse": "after_hours"}
    AppService._record_equity_snapshots(svc, _at(420))   # 16:00 ET  # type: ignore[arg-type]
    AppService._record_equity_snapshots(svc, _at(425))   # type: ignore[arg-type]
    assert [p.taken_at for p in _read(svc)] == ["2026-10-24T19:55:00", "2026-10-24T20:00:00"]


def test_partial_slot_not_saved(repo):
    """UT-EXE-020.002.M01.T03: All users of a slot are saved together or not at all."""
    svc = _svc(repo)
    state = svc.get_account_state
    svc.get_account_state = lambda uid: state(uid) if uid == 1 else 1 / 0
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    assert _read(svc) == ()


def test_prune_runs_once_a_day(repo, caplog):
    """UT-EXE-020.005.M02.T01: Old rows are pruned on the first check of each day only."""
    import logging
    caplog.set_level(logging.INFO)
    repo.record(1, 1.0, 1.0, 0.0, datetime(2026, 9, 1, 14, 0, tzinfo=timezone.utc))
    svc = _svc(repo)
    AppService._record_equity_snapshots(svc, _at(31))   # type: ignore[arg-type]
    AppService._record_equity_snapshots(svc, _at(36))   # type: ignore[arg-type]
    assert caplog.text.count("[Equity] Removed 1 equity snapshot(s)") == 1
    assert repo.between("2000-01-01T00:00:00", "2026-10-01T00:00:00") == ()


def test_naive_time_taken_as_utc():
    """UT-EXE-020.002.M01.T04: A time without a zone is read as UTC."""
    assert slot_iso(datetime(2026, 10, 24, 13, 33)) == "2026-10-24T13:30:00"


def test_create_and_drop_schema_include_table():
    """UT-EXE-020.001.M01.T02: create_schema makes the table and drop_schema removes it."""
    from us_swing.db.schema import create_schema, drop_schema
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    create_schema(engine)
    assert "equity_snapshots" in sa.inspect(engine).get_table_names()
    drop_schema(engine)
    assert "equity_snapshots" not in sa.inspect(engine).get_table_names()
