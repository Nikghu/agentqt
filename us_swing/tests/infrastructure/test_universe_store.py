"""Tests for MD-INF-013.001.M01 — universe/store.py membership dates."""
from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.universe import store
from us_swing.universe.store import Sp500Record

_TODAY = date(2026, 11, 27)


@pytest.fixture(autouse=True)
def tmp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(store, "_APP_DIR", tmp_path)
    monkeypatch.setattr(store, "_UNIVERSE_CSV", tmp_path / "sp500_universe.csv")
    monkeypatch.setattr(store, "_META_JSON", tmp_path / "sp500_meta.json")
    return tmp_path


def _rec(sym: str, name: str = "", added: str = "", left: str = "") -> Sp500Record:
    return Sp500Record(sym, sym, name or sym, "Tech", 1e9, added, left)


def test_fetch_reads_date_added(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-013.001.M01.T01: The page's Date added is saved as an ISO date; a blank stays empty."""
    table = pd.DataFrame({"Symbol": ["MMM", "NEW"], "Security": ["3M", "New Co"],
                          "GICS Sector": ["Industrials", "Tech"],
                          "Date added": ["1957-03-04", None]})

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: _Resp(b"<html/>"))
    monkeypatch.setattr(pd, "read_html", lambda *_a, **_k: [table])
    monkeypatch.setattr(store, "_fetch_market_caps", lambda _s: {})

    records = store._fetch_from_wikipedia()

    assert [(r.symbol, r.date_added) for r in records] == [("MMM", "1957-03-04"), ("NEW", "")]


def test_old_csv_loads_without_dates(tmp_store: Path) -> None:
    """UT-INF-013.001.M01.T02: A list saved before this change loads with empty dates."""
    with (tmp_store / "sp500_universe.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Symbol", "IbkrSymbol", "Name", "Sector", "MarketCap"])
        w.writerow(["AAPL", "AAPL", "Apple", "Tech", "3e12"])

    [rec] = store._load_from_csv()

    assert (rec.symbol, rec.date_added, rec.left_on) == ("AAPL", "", "")


def test_removed_stock_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-013.002.M01.T01: A stock missing from the fresh list is kept, left today, fields kept."""
    monkeypatch.setattr(store, "_MIN_FRESH_SHARE", 0.0)
    saved = [_rec("AAA", added="2001-01-02"), _rec("BBB", name="Bee Inc", added="2010-05-06")]

    merged = store._merge(saved, [_rec("AAA")], _TODAY)

    gone = {r.symbol: r for r in merged}["BBB"]
    assert (gone.left_on, gone.name, gone.date_added) == ("2026-11-27", "Bee Inc", "2010-05-06")
    assert {r.symbol: r for r in merged}["AAA"].date_added == "2001-01-02"


def test_left_date_not_overwritten() -> None:
    """UT-INF-013.002.M01.T02: A stock that already left keeps its first left date."""
    merged = store._merge([_rec("AAA"), _rec("BBB", left="2026-11-01")], [_rec("AAA")], _TODAY)

    assert {r.symbol: r.left_on for r in merged} == {"AAA": "", "BBB": "2026-11-01"}


def test_cut_page_marks_nobody_left() -> None:
    """UT-INF-013.002.M01.T03: A fresh list far smaller than the saved one marks no stock as left."""
    saved = [_rec(f"S{i:02d}") for i in range(20)]

    merged = store._merge(saved, [_rec(f"S{i:02d}") for i in range(5)], _TODAY)

    assert len(merged) == 20 and all(not r.left_on for r in merged)


def test_returning_stock_left_cleared() -> None:
    """UT-INF-013.003.M01.T01: A stock listed again loses its left date and takes fresh fields."""
    merged = store._merge([_rec("BBB", name="Old", left="2026-11-01")],
                          [_rec("BBB", name="Bee Inc", added="2026-11-20")], _TODAY)

    assert [(r.name, r.date_added, r.left_on) for r in merged] == [("Bee Inc", "2026-11-20", "")]


def test_current_and_full_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-013.004.M01.T01: Current list leaves out left stocks; full list keeps them; meta counts current."""
    store._save_to_csv([_rec("AAA"), _rec("BBB")])
    monkeypatch.setattr(store, "_fetch_from_wikipedia", lambda: [_rec("AAA")])
    monkeypatch.setattr(store, "_MIN_FRESH_SHARE", 0.0)

    current = store.refresh()

    assert [r.symbol for r in current] == ["AAA"]
    assert [r.symbol for r in store.load_sp500()] == ["AAA"]
    assert [(r.symbol, bool(r.left_on)) for r in store.load_sp500_all()] == [
        ("AAA", False), ("BBB", True)]
    assert store.get_meta().count == 1
