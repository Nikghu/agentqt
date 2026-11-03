"""
Module: MD-GUI-006 — tests (ISS-GUI-0014)
Parent SRD: SRD-GUI-006.020

Candle data looked "up to date" as soon as one stock had the newest bar, so
Update now stayed off while most stocks were a day behind.  Retry Failed also
wiped the resume point of an unfinished update.
"""
from __future__ import annotations

import asyncio
import datetime
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from us_swing.gui import app_service as svc_mod


def _db(path: Path, lasts: dict[str, str]) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    svc_mod._ensure_candle_tables(c)
    c.executemany(
        "INSERT INTO price_1d VALUES (?,?,?,?,?,?,?)",
        [(sym, f"{day}T00:00:00", 1.0, 1.0, 1.0, 1.0, 1) for sym, day in lasts.items()],
    )
    c.commit()
    return c


def test_oldest_last_date_decides(tmp_path: Path) -> None:
    """UT-GUI-006.001.M01.T20: the oldest last date among index stocks is the data date."""
    conn = _db(tmp_path / "c.db", {"AAA": "2026-11-02", "BBB": "2026-10-30"})

    assert svc_mod._oldest_last_candle_date(conn, ["AAA", "BBB"]) == "2026-10-30"


def test_stocks_outside_list_do_not_hold_date_back(tmp_path: Path) -> None:
    """UT-GUI-006.001.M01.T21: out-of-index and failed stocks are left out."""
    conn = _db(tmp_path / "c.db",
               {"AAA": "2026-11-02", "OLD": "2026-09-01", "KVUE": "2026-10-29"})

    assert svc_mod._oldest_last_candle_date(conn, ["AAA"]) == "2026-11-02"


def test_status_partial_when_most_stocks_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: Any
) -> None:
    """UT-GUI-006.001.M01.T22: one current stock does not make the database current."""
    db = tmp_path / "candles.db"
    _db(db, {"AAA": "2026-11-02", "BBB": "2026-10-30"}).close()
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", db)
    monkeypatch.setattr(svc_mod, "_compute_last_trading_day",
                        lambda: datetime.date(2026, 11, 2))
    worker = svc_mod._CandleDbStatusWorker(universe_size=2, symbols=["AAA", "BBB"])
    infos: list[Any] = []
    worker.done.connect(infos.append)

    worker.run()

    assert infos[0].status == svc_mod.CandleDbStatus.PARTIAL
    assert infos[0].last_candle_date == "2026-10-30"


class _FakeIB:
    async def reqHistoricalDataAsync(self, contract: Any, **kwargs: Any) -> list[SimpleNamespace]:
        return [SimpleNamespace(date=datetime.date(2026, 11, 2), open=1.0, high=1.0,
                                low=1.0, close=1.0, volume=1)]

    def isConnected(self) -> bool:
        return True


def test_retry_failed_keeps_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: Any
) -> None:
    """UT-GUI-006.001.M01.T23: a Retry Failed run leaves the resume point untouched."""
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text('{"mode": "delta"}', encoding="utf-8")
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", tmp_path / "candles.db")
    monkeypatch.setattr(svc_mod, "_CHECKPOINT_PATH", checkpoint)
    monkeypatch.setattr(svc_mod, "_CANDLE_SYMBOL_PAUSE_S", 0.0)
    worker = svc_mod._CandleDownloadWorker(
        symbols=["KVUE"], start_date=datetime.date(2026, 11, 3),
        end_date=datetime.date(2026, 11, 2), mode="fix", ibkr_host="127.0.0.1",
        ibkr_port=7497, ibkr_client_id=1, benchmark_symbol="",
    )

    asyncio.run(worker._download_all(_FakeIB()))

    assert checkpoint.read_text(encoding="utf-8") == '{"mode": "delta"}'
