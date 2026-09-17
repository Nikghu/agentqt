"""
Module: MD-EXE-018.001.M02 — gui/strategy_store.py direction tests
Parent SRD: SRD-EXE-018.001
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
import sqlalchemy as sa

from us_swing.gui import strategy_store as store
from us_swing.gui.strategy_store import StrategyConfig


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "candles.db"
    monkeypatch.setattr(store, "_DB_PATH", path)
    monkeypatch.setattr(store, "_engine_cache", None)
    yield path
    if store._engine_cache is not None:
        store._engine_cache.dispose()


def _cfg(**overrides: object) -> StrategyConfig:
    values: dict[str, object] = {
        "name": "FADE",
        "mode": "manual",
        "capital_max": 25,
        "start_time": "09:30",
        "end_time": "15:30",
        "start_date": "2026-09-17",
        "end_date": "2027-03-17",
        "days": ["Mon"],
        "entry_condition": "",
        "exit_condition": "",
    }
    values.update(overrides)
    return StrategyConfig(**values)  # type: ignore[arg-type]


def test_short_direction_round_trips(db_path: Path) -> None:
    """UT-EXE-018.001.M02.T01: a SHORT strategy saves and loads as SHORT."""
    store.save_strategies([_cfg(direction="SHORT")])
    loaded = store.load_strategies()
    assert [c.direction for c in loaded] == ["SHORT"]


def test_legacy_table_migrates_to_long(db_path: Path) -> None:
    """UT-EXE-018.001.M02.T02: a strategies table without direction gains it; rows read LONG."""
    legacy_meta = sa.MetaData()
    legacy = sa.Table(
        "strategies",
        legacy_meta,
        *(
            sa.Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
            for c in store.strategies.columns
            if c.name != "direction"
        ),
    )
    eng = sa.create_engine(f"sqlite:///{db_path}")
    legacy_meta.create_all(eng)
    values = {k: v for k, v in store._cfg_to_values(_cfg()).items() if k != "direction"}
    with eng.begin() as conn:
        conn.execute(sa.insert(legacy), [values])
    eng.dispose()

    loaded = store.load_strategies()

    assert [c.direction for c in loaded] == ["LONG"]


def test_unknown_direction_falls_back_to_long(
    db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """UT-EXE-018.001.M02.T03: an unknown stored direction loads as LONG with one warning."""
    store.save_strategies([_cfg(direction="SIDEWAYS")])

    with caplog.at_level(logging.WARNING, logger=store.__name__):
        loaded = store.load_strategies()

    assert [c.direction for c in loaded] == ["LONG"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].getMessage().startswith("[Strategy]")
