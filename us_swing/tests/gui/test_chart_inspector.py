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
    KeyLevelsSection,
    PatternsSection,
    TradePlan,
    TradePlanSection,
    indicator_values,
    key_levels,
    pattern_hits,
    plan_rr,
    plan_size,
)


def _bar(i: int, o: float, c: float) -> dict[str, float]:
    return {"time": i, "open": o, "high": max(o, c) + 0.2, "low": min(o, c) - 0.2,
            "close": c, "volume": 1_000.0}


def _engulfing(bars_after: int) -> list[dict[str, float]]:
    """A steady fall, a small red bar, a bullish engulfing bar, then ``bars_after`` bars."""
    bars = [_bar(i, 120 - i * 0.8, 119.5 - i * 0.8) for i in range(30)]
    p = bars[-1]["close"]
    bars += [_bar(30, p, p - 1.0), _bar(31, p - 1.5, p + 1.0)]
    for k in range(bars_after):
        bars.append(_bar(32 + k, p + 1.0 + k * 0.2, p + 1.2 + k * 0.2))
    return bars


def _levels_bars() -> list[dict[str, float]]:
    bars = [{"time": i, "open": 125.0, "high": 125.0, "low": 125.0, "close": 125.0,
             "volume": 1_000.0} for i in range(40)]
    bars[10]["high"] = 135.0
    bars[20]["low"] = 110.0
    bars[30]["low"] = 120.0
    return bars


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
    next(b for b in inspector.boxes if b.section.key == "indicators").header.click()
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


def test_pattern_hits_on_recent_bars(qtbot):
    """UT-GUI-026.008.M03.T01: Pattern hits on recent bars."""
    bars = _engulfing(bars_after=2)
    hit = next(h for h in pattern_hits(bars) if h.name == "Bullish Engulfing")
    assert hit.bars_ago == 2 and hit.direction.value == "bullish" and hit.time == 31
    section = PatternsSection()
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.markers_changed) as blocker:
        section.set_context(ChartContext("NVDA", "1d", bars))
    markers = blocker.args[0]
    engulf = next(m for m in markers if m["text"] == "Bullish Engulfing")
    assert engulf["position"] == "belowBar" and engulf["shape"] == "arrowUp"
    assert [m["time"] for m in markers] == sorted(m["time"] for m in markers)
    assert any("Bullish Engulfing" in label.text() and "2 bars ago" in label.text()
               for label in section.lines)


def test_old_pattern_not_listed():
    """UT-GUI-026.008.M03.T02: Old pattern not listed."""
    names = [h.name for h in pattern_hits(_engulfing(bars_after=10))]
    assert "Bullish Engulfing" not in names


def test_nearest_swing_levels(qtbot):
    """UT-GUI-026.009.M03.T01: Nearest swing levels."""
    assert key_levels(_levels_bars()) == ([135.0], [120.0, 110.0])
    section = KeyLevelsSection()
    qtbot.addWidget(section)
    sent: list[list[float]] = []
    section.levels_changed.connect(sent.append)
    section.set_context(ChartContext("NVDA", "1d", _levels_bars()))
    assert section.above_lbl.text() == "135.00" and section.below_lbl.text() == "120.00, 110.00"
    assert sent[-1] == []
    section.show_box.setChecked(True)
    assert sent[-1] == [135.0, 120.0, 110.0]


def test_key_levels_too_few_bars():
    """UT-GUI-026.009.M03.T02: Too few bars give no levels."""
    assert key_levels(_levels_bars()[:5]) == ([], [])


def test_too_few_bars(qtbot):
    """UT-GUI-026.007.M03.T02: Too few bars."""
    assert indicator_values(_candles(5)) == {
        "rsi": None, "atr": None, "adx": None, "rel_volume": None}
    section = IndicatorsSection()
    qtbot.addWidget(section)
    section.set_context(ChartContext("NVDA", "1d", _candles(5)))
    assert all(isinstance(v, QLabel) and v.text() == "—" for v in section.rows.values.values())
