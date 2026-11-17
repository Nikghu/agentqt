"""
Module: MD-GUI-025.022.M06 — tests
Parent SRD: SRD-GUI-025.022

Sector Rotation tab: sector moves against RSP, the bar view, the Market Watch tile
tabs, the daily closes read and the sector candle download.
"""
from __future__ import annotations

import asyncio
import datetime
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from us_swing.gui import app_service as svc_mod
from us_swing.gui.sector_rotation import (
    SECTOR_SYMBOLS,
    SectorMove,
    SectorRotationView,
    sector_moves,
)

_DAYS = ["2026-11-10", "2026-11-11", "2026-11-12"]


def _closes(**series: list[float]) -> dict[str, dict[str, float]]:
    return {sym: dict(zip(_DAYS, values, strict=True)) for sym, values in series.items()}


def test_moves_ranked_against_rsp() -> None:
    """UT-GUI-025.022.M06.T01: Sector move minus RSP move, strongest first, with the end date."""
    closes = _closes(RSP=[100, 101, 102], XLK=[100, 103, 105], XLE=[100, 100, 99])

    moves, as_of = sector_moves(closes, 2)

    assert [m.symbol for m in moves] == ["XLK", "XLE"]
    assert moves[0].relative_pct == pytest.approx(3.0)
    assert moves[1].relative_pct == pytest.approx(-3.0)
    assert as_of == "2026-11-12"


def test_too_few_rsp_closes_gives_nothing() -> None:
    """UT-GUI-025.022.M06.T02: RSP with no more closes than the range gives no moves."""
    closes = _closes(RSP=[100, 101, 102], XLK=[100, 103, 105])

    assert sector_moves(closes, 3) == ([], "")
    assert sector_moves({}, 1) == ([], "")


def test_sector_without_start_close_left_out() -> None:
    """UT-GUI-025.022.M06.T03: A sector missing the start day is left out."""
    closes = _closes(RSP=[100, 101, 102], XLK=[100, 103, 105])
    closes["XLF"] = {"2026-11-11": 50.0, "2026-11-12": 51.0}

    moves, _as_of = sector_moves(closes, 2)

    assert [m.symbol for m in moves] == ["XLK"]


def test_view_shows_bars_and_date(qtbot: Any) -> None:
    """UT-GUI-025.022.M06.T04: Bars scale to the largest move; date shown as DD-MM-YYYY."""
    view = SectorRotationView()
    qtbot.addWidget(view)

    view.show_moves([SectorMove("XLK", "Technology", 4.0),
                     SectorMove("XLE", "Energy", -1.0)], "2026-11-12")

    assert [b.fraction for b in view.bars] == pytest.approx([1.0, -0.25])
    assert "12-11-2026" in view.note_lbl.text()
    assert view.empty_lbl.isHidden()


def test_view_empty_text(qtbot: Any) -> None:
    """UT-GUI-025.022.M06.T05: No moves shows the empty text and no bars."""
    view = SectorRotationView()
    qtbot.addWidget(view)

    view.show_moves([], "")

    assert not view.empty_lbl.isHidden()
    assert view.bars == []


def test_daily_closes_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-025.022.M07.T01: Last N daily closes per symbol by date; missing symbol left out."""
    db = tmp_path / "candles.db"
    conn = sqlite3.connect(db)
    svc_mod._ensure_candle_tables(conn)
    conn.executemany(
        "INSERT INTO price_1d VALUES (?,?,?,?,?,?,?)",
        [("RSP", f"{day}T00:00:00", 1.0, 1.0, 1.0, close, 1)
         for day, close in zip(_DAYS, (10.0, 11.0, 12.0), strict=True)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", db)

    closes = svc_mod.AppService.get_daily_closes(
        None, ("RSP", "XLK"), 2  # type: ignore[arg-type]
    )

    assert closes == {"RSP": {"2026-11-11": 11.0, "2026-11-12": 12.0}}


def test_download_fetches_rsp_and_sectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-025.023.M07.T01: A candle update fetches SPY, RSP and the 11 sector ETFs."""
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", tmp_path / "candles.db")
    monkeypatch.setattr(svc_mod, "_CHECKPOINT_PATH", tmp_path / "checkpoint.json")
    worker = svc_mod._CandleDownloadWorker(
        symbols=[], start_date=datetime.date(2026, 11, 3),
        end_date=datetime.date(2026, 11, 12), mode="delta", ibkr_host="127.0.0.1",
        ibkr_port=7497, ibkr_client_id=1, benchmark_symbol="SPY",
    )
    fetched: list[str] = []

    async def record(_ib: object, symbol: str) -> None:
        fetched.append(symbol)

    monkeypatch.setattr(worker, "_download_benchmark", record)

    asyncio.run(worker._download_all(object()))

    assert fetched == ["SPY", *SECTOR_SYMBOLS]
    assert len(fetched) == 13
