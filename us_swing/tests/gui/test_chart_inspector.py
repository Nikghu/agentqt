"""Tests for the Charts Inspector (FO-GUI-026, MD-GUI-026.005.M03)."""
from __future__ import annotations

import numpy as np
import pytest
import talib
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel, QWidget

from us_swing.gui.chart_inspector import (
    SECTIONS,
    ChartContext,
    IndicatorsSection,
    Inspector,
    TradePlan,
    TradePlanSection,
    indicator_values,
    plan_rr,
    plan_size,
)


def _candles(n: int, last_volume: float = 1_000.0) -> list[dict[str, float]]:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": c - 0.5, "high": c + 1.0,
         "low": c - 1.5, "close": float(c), "volume": 1_000.0}
        for i, c in enumerate(close)
    ]
    bars[-1]["volume"] = last_volume
    return bars


@pytest.fixture()
def settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "charts.ini"), QSettings.Format.IniFormat)


class _FakeSection(QWidget):
    key = "fake"
    title = "Fake"

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        self.seen.append(ctx.symbol)


def test_one_header_per_section_and_open_state_remembered(qtbot, settings):
    """UT-GUI-026.005.M03.T01: One header per registry entry; open state remembered."""
    inspector = Inspector(settings)
    qtbot.addWidget(inspector)
    titles = [box.header.text() for box in inspector.boxes]
    assert titles == [factory().title.upper() for factory in SECTIONS]
    assert inspector.is_open("indicators")
    inspector.boxes[1].header.click()
    again = Inspector(settings)
    qtbot.addWidget(again)
    assert again.is_open("plan") and not again.is_open("indicators")


def test_extra_section_plugs_in(qtbot, settings):
    """UT-GUI-026.005.M03.T02: Extra section plugs in."""
    inspector = Inspector(settings, sections=[*SECTIONS, _FakeSection])
    qtbot.addWidget(inspector)
    assert inspector.boxes[-1].header.text() == "FAKE"
    inspector.update_context(ChartContext("NVDA", "1d", _candles(30)))
    fake = inspector.sections[-1]
    assert isinstance(fake, _FakeSection) and fake.seen == ["NVDA"]


def test_rr_and_size():
    """UT-GUI-026.006.M03.T01: R:R and size."""
    assert round(plan_rr(129.8, 124.5, 141.0) or 0, 1) == 2.1
    assert plan_size(129.8, 124.5, 40_000, 1.0) == 75


def test_invalid_plan_shows_dashes(qtbot):
    """UT-GUI-026.006.M03.T02: Invalid plan shows dashes."""
    assert plan_rr(129.8, 131.0, 141.0) is None
    assert plan_size(129.8, 131.0, 40_000, 1.0) == 0
    section = TradePlanSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", _candles(5),
                                     TradePlan(129.8, 131.0, 141.0), 1.0, 40_000))
    assert section.rows.values["rr"].text() == "—"
    assert section.rows.values["size"].text() == "—"
    section.set_context(ChartContext("NVDA", "1d", _candles(5)))
    assert all(label.text() == "—" for label in section.rows.values.values())


def test_plan_values_shown(qtbot):
    """UT-GUI-026.006.M03.T03: Plan values, R:R and size are shown."""
    section = TradePlanSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", _candles(5),
                                     TradePlan(129.8, 124.5, 141.0), 1.0, 40_000))
    values = section.rows.values
    assert [values[k].text() for k in ("entry", "stop", "target", "rr", "size")] == [
        "129.80", "124.50", "141.00", "2.1", "75 sh"]
    assert section.rows.names[4].text() == "Size (1% risk)"


def test_edit_updates_values_and_emits(qtbot):
    """UT-GUI-026.006.M03.T04: Edit updates values and lines."""
    section = TradePlanSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", _candles(5),
                                     TradePlan(129.8, 124.5, 141.0), 1.0, 40_000))
    section.edit_btn.click()
    assert section.editing
    section.spins["stop"].setValue(125.0)
    with qtbot.waitSignal(section.plan_changed) as blocker:
        section.edit_btn.click()
    assert blocker.args[0] == TradePlan(129.8, 125.0, 141.0)
    assert section.rows.values["stop"].text() == "125.00"
    assert not section.editing


def test_indicator_values_match_talib(qtbot):
    """UT-GUI-026.007.M03.T01: Indicator values."""
    bars = _candles(60, last_volume=2_000.0)
    high = np.array([b["high"] for b in bars])
    low = np.array([b["low"] for b in bars])
    close = np.array([b["close"] for b in bars])
    values = indicator_values(bars)
    assert values["rsi"] == pytest.approx(talib.RSI(close, 14)[-1])
    assert values["atr"] == pytest.approx(talib.ATR(high, low, close, 14)[-1])
    assert values["adx"] == pytest.approx(talib.ADX(high, low, close, 14)[-1])
    assert values["rel_volume"] == pytest.approx(2.0)
    section = IndicatorsSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", bars))
    assert section.rows.values["rel_volume"].text() == "2.0×"


def test_too_few_bars(qtbot):
    """UT-GUI-026.007.M03.T02: Too few bars."""
    assert indicator_values(_candles(5)) == {
        "rsi": None, "atr": None, "adx": None, "rel_volume": None}
    section = IndicatorsSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", _candles(5)))
    assert all(isinstance(v, QLabel) and v.text() == "—" for v in section.rows.values.values())
