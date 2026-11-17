"""Tests for AI Desk v3 M5 GUI: MD-GUI-034.016.M15 (switch), 034.078.M40 (tiles), 035.018.M06."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pytestqt.qtbot import QtBot

from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_day import (
    mark_huddle,
    save_call,
    save_day_end,
    save_results,
    save_standup,
)
from us_swing.gui.ai_desk_day import DayStrip, DayTiles
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm
from us_swing.market.store import MarketStore, RegimeViewRow, SectorViewRow

NY = ZoneInfo("America/New_York")
DAY = "2026-11-12"
NOW = datetime(2026, 11, 13, 11, 0, tzinfo=NY)


def _on(home: Path, on: bool = True) -> None:
    save_settings(DeskAiSettings(company_day_on=on), home)


def _roster(home: Path) -> None:
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS roster (id TEXT PRIMARY KEY, name TEXT, "
                    "skill TEXT)")
        con.execute("INSERT INTO roster VALUES ('emp-r', 'Ray', 'regime_view')")
        con.execute("INSERT INTO roster VALUES ('emp-s', 'Sam', 'sector_flow_view')")
    con.close()


def _call(home: Path) -> None:
    store = MarketStore(home)
    store.write_regime_view(RegimeViewRow(DAY, "Choppy", 0.6, "[]", "b", "Choppy", True))
    store.replace_day("sector_view", DAY, [SectorViewRow(
        DAY, '["Information Technology"]', "[]", "r", "b")])
    store.close()
    _roster(home)
    mark_huddle(home, DAY, "clash", NOW)
    save_call(home, DAY, "Uptrend", ["Information Technology"], "", "2026-11-19", NOW)
    save_results(home, DAY, "right", "right", 1.5, 2.5,
                 {"regime_view": "wrong", "sector_flow_view": "right"}, "2026-11-19")


def test_company_day_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.077.M15.T01: Ticking Company day saves company_day_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.company_day_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).company_day_on is True


def test_switch_left_off(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.077.M15.T02: With no file the box is unticked and saves off."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.company_day_on.isChecked()
    assert form.save()
    assert load_settings(tmp_path).company_day_on is False


def test_day_call_tile(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.078.M40.T01: The tile names the call, who agreed, the huddle and the result."""
    _on(tmp_path)
    _call(tmp_path)
    tiles = DayTiles()
    qtbot.addWidget(tiles)
    tiles.refresh(tmp_path)
    text = tiles.call_label.text()
    for part in ("Uptrend · Information Technology", "Agreed: Sam", "Disagreed: Ray",
                 "Huddle", "right"):
        assert part in text, part
    assert not tiles.isHidden()


def test_handover_tile(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.078.M40.T02: The tile shows the latest handover lines and their day."""
    _on(tmp_path)
    save_day_end(tmp_path, DAY, ["NVDA in trade", "Watch CPI"], [], "s", NOW)
    tiles = DayTiles()
    qtbot.addWidget(tiles)
    tiles.refresh(tmp_path)
    text = tiles.handover_label.text()
    assert "NVDA in trade<br>Watch CPI" in text and DAY in text
    save_day_end(tmp_path, "2026-11-13", ["R&D <5% drop"], [], "s", NOW)
    tiles.refresh(tmp_path)
    assert "R&amp;D &lt;5% drop" in tiles.handover_label.text()


def test_tiles_hidden(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.078.M40.T03: With the day off the tiles stay hidden."""
    _on(tmp_path, False)
    save_day_end(tmp_path, DAY, ["NVDA in trade"], [], "s", NOW)
    tiles = DayTiles()
    qtbot.addWidget(tiles)
    tiles.refresh(tmp_path)
    assert tiles.isHidden()


def test_day_strip(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.018.M06.T01: Stand-up and plan times, huddle skipped, market open, day-end waiting."""
    _on(tmp_path)
    MarketStore(tmp_path).close()
    save_standup(tmp_path, DAY, "Stand-up", datetime(2026, 11, 13, 8, 10, tzinfo=NY))
    save_call(tmp_path, DAY, "Choppy", ["Energy"], "", "2026-11-19",
              datetime(2026, 11, 13, 8, 12, tzinfo=NY))
    strip = DayStrip()
    qtbot.addWidget(strip)
    strip.refresh(tmp_path, NOW)
    texts = {name: label.text() for name, label in strip.labels.items()}
    assert "08:10" in texts["Stand-up"] and "08:12" in texts["Plan"]
    assert "skipped" in texts["Huddle"] and "open" in texts["Market hours"]
    assert "waiting" in texts["Day-end"]
    assert not strip.isHidden()


def test_strip_hidden(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.018.M06.T02: With the day off the strip stays hidden."""
    _on(tmp_path, False)
    save_standup(tmp_path, DAY, "Stand-up", NOW)
    strip = DayStrip()
    qtbot.addWidget(strip)
    strip.refresh(tmp_path, NOW)
    assert strip.isHidden()


def test_task_cards_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.080.M15.T01: Ticking Task cards saves task_cards_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.task_cards_on.isChecked()
    form.messages_on.setChecked(True)
    form.task_cards_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).task_cards_on is True


def test_task_cards_needs_messages(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.080.M15.T02: Task cards box is greyed while agent messages are off."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.task_cards_on.isEnabled()
    form.messages_on.setChecked(True)
    assert form.task_cards_on.isEnabled()
    form.messages_on.setChecked(False)
    assert not form.task_cards_on.isEnabled()


def test_today_block_folds_long_handover(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.092.M41.T01: A long handover shows 2 lines and More; More shows all, Less folds."""
    _on(tmp_path)
    save_day_end(tmp_path, DAY, ["One", "Two", "Three", "Four"], [], "s", NOW)
    block = DayTiles()
    qtbot.addWidget(block)
    block.refresh(tmp_path)
    assert "One<br>Two …" in block.handover_label.text()
    assert "Three" not in block.handover_label.text()
    assert not block.more_btn.isHidden() and block.more_btn.text() == "More"
    block.more_btn.click()
    assert "Three<br>Four" in block.handover_label.text()
    assert block.more_btn.text() == "Less"
    block.more_btn.click()
    assert "Three" not in block.handover_label.text()


def test_today_block_in_feed_not_desk_header(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.092.M41.T02: The Today block sits in the AI feed; the AI Desk has no day tiles."""
    from us_swing.gui.ai_desk import AiDeskWorkspace
    from us_swing.gui.desk_control import DeskPoller
    from us_swing.gui.floor_feed import AiFeedColumn

    feed = AiFeedColumn()
    qtbot.addWidget(feed)
    assert isinstance(feed.day_block, DayTiles)
    page = AiDeskWorkspace(DeskPoller(tmp_path))
    qtbot.addWidget(page)
    assert not page.findChildren(DayTiles)
