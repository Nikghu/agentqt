"""Module: MD-GUI-011.001.M01 — chart_panel.py
Parent SRD: SRD-GUI-011.001

Candle Chart Viewer panel — allows the operator to select any symbol from the
local candle database and inspect its OHLCV data as a TradingView Lightweight
Chart.  Used primarily to verify data quality after a download.

Chart engine: TradingView Lightweight Charts v5 (Apache 2.0)
  bundled at: gui/resources/lightweight-charts.standalone.production.js
Embedded via: PyQt6.QtWebEngineWidgets.QWebEngineView (already in deps).
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, QStringListModel, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.theme import C

# Path to the bundled Lightweight Charts JS (downloaded once at install time)
_RESOURCES = Path(__file__).parent / "resources"
_LWCHART_JS = _RESOURCES / "lightweight-charts.standalone.production.js"


def _build_html(
    candle_data: list[dict],
    volume_data: list[dict],
    symbol: str,
    timeframe: str,
    show_reset_menu: bool = False,
) -> str:
    """Return a self-contained HTML page with a TradingView Lightweight Chart."""
    candle_json = json.dumps(candle_data)
    volume_json = json.dumps(volume_data)

    # Read the bundled JS inline so the page works fully offline
    if _LWCHART_JS.exists():
        js_source = _LWCHART_JS.read_text(encoding="utf-8")
        script_tag = f"<script>\n{js_source}\n</script>"
    else:
        # Fallback to CDN when bundle is missing
        script_tag = (
            '<script src="https://unpkg.com/lightweight-charts@5.0.5/'
            'dist/lightweight-charts.standalone.production.js"></script>'
        )

    title = f"{symbol} — {timeframe.upper()}"

    ctx_menu_css = (
        f"""  #ctx-menu {{
    display: none;
    position: fixed;
    z-index: 9999;
    background: {C.SURFACE};
    border: 1px solid {C.OVERLAY};
    border-radius: 4px;
    padding: 4px 0;
    min-width: 160px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
  }}
  #ctx-menu div {{
    padding: 6px 14px;
    color: {C.TEXT};
    cursor: pointer;
    white-space: nowrap;
  }}
  #ctx-menu div:hover {{
    background: {C.OVERLAY};
  }}"""
    ) if show_reset_menu else ""

    ctx_menu_html = (
        '<div id="ctx-menu"><div id="ctx-reset">Reset to today</div></div>'
    ) if show_reset_menu else ""

    ctx_menu_js = (
        """  // ── Right-click context menu ──────────────────────────────────────────────
  const ctxMenu = document.getElementById('ctx-menu');
  function _hideCtx() { ctxMenu.style.display = 'none'; }

  chartEl.addEventListener('contextmenu', e => {
    e.preventDefault();
    ctxMenu.style.left = e.clientX + 'px';
    ctxMenu.style.top  = e.clientY + 'px';
    ctxMenu.style.display = 'block';
  });
  document.getElementById('volume-container').addEventListener('contextmenu', e => {
    e.preventDefault();
    ctxMenu.style.left = e.clientX + 'px';
    ctxMenu.style.top  = e.clientY + 'px';
    ctxMenu.style.display = 'block';
  });
  document.addEventListener('click', _hideCtx);
  document.addEventListener('contextmenu', e => {
    if (!chartEl.contains(e.target) && !document.getElementById('volume-container').contains(e.target)) _hideCtx();
  });

  document.getElementById('ctx-reset').addEventListener('click', () => {
    _zoomToLastDay();
    _hideCtx();
  });
"""
    ) if show_reset_menu else ""

    initial_zoom_js = (
        "_zoomToLastDay();"
        if show_reset_menu
        else "chart.timeScale().fitContent();\n  volChart.timeScale().fitContent();"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: {C.BG};
    color: {C.TEXT};
    font-family: 'Consolas', 'Monaco', monospace;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }}
  #header {{
    padding: 6px 12px;
    background: {C.SURFACE};
    border-bottom: 1px solid {C.OVERLAY};
    font-size: 11px;
    color: {C.MUTED};
    letter-spacing: 0.5px;
  }}
  #header span {{
    color: {C.TEXT};
    font-weight: bold;
    font-size: 13px;
    margin-right: 12px;
  }}
  #chart-container {{
    flex: 1;
    min-height: 0;
    position: relative;
  }}
  #measure-overlay {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: 10;
  }}
  #measure-rect {{
    display: none;
    position: absolute;
    border: 1px dashed #ffffff66;
    background: rgba(255,255,255,0.04);
    pointer-events: none;
  }}
  #measure-label {{
    display: none;
    position: absolute;
    background: {C.SURFACE};
    border: 1px solid #ffffff33;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-family: 'Consolas', 'Monaco', monospace;
    white-space: nowrap;
    pointer-events: none;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
  }}
  #volume-container {{
    height: 80px;
    background: {C.BG};
  }}
  #no-data {{
    display: none;
    color: {C.MUTED};
    font-size: 14px;
    text-align: center;
    margin-top: 60px;
  }}
{ctx_menu_css}
</style>
{script_tag}
</head>
<body>
<div id="header">
  <span>{title}</span>
  <span id="bar-info">Hover over a candle to see OHLCV</span>
</div>
<div id="chart-container">
  <div id="measure-overlay">
    <div id="measure-rect"></div>
    <div id="measure-label"></div>
  </div>
</div>
<div id="volume-container"></div>
<div id="no-data">No candle data found for this symbol.</div>
{ctx_menu_html}

<script>
(function() {{
  let candleData = {candle_json};
  let volumeData = {volume_json};

  if (!candleData || candleData.length === 0) {{
    document.getElementById('no-data').style.display = 'block';
    return;
  }}

  // ── Candle chart ─────────────────────────────────────────────────────────
  const chartEl = document.getElementById('chart-container');
  const chart = LightweightCharts.createChart(chartEl, {{
    layout: {{
      background: {{ color: '{C.BG}' }},
      textColor: '{C.TEXT}',
    }},
    grid: {{
      vertLines: {{ color: '{C.OVERLAY}' }},
      horzLines: {{ color: '{C.OVERLAY}' }},
    }},
    crosshair: {{
      mode: LightweightCharts.CrosshairMode.Normal,
    }},
    rightPriceScale: {{
      borderColor: '{C.OVERLAY}',
    }},
    timeScale: {{
      borderColor: '{C.OVERLAY}',
      timeVisible: true,
      secondsVisible: false,
    }},
    watermark: {{
      visible: true,
      fontSize: 18,
      horzAlign: 'left',
      vertAlign: 'bottom',
      color: '{C.OVERLAY2}',
      text: 'US Swing | {title}',
    }},
  }});

  const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
    upColor:   '#26a69a',
    downColor: '#ef5350',
    borderUpColor:   '#26a69a',
    borderDownColor: '#ef5350',
    wickUpColor:   '#26a69a',
    wickDownColor: '#ef5350',
  }});
  candleSeries.setData(candleData);

  // ── Volume chart ─────────────────────────────────────────────────────────
  const volEl = document.getElementById('volume-container');
  const volChart = LightweightCharts.createChart(volEl, {{
    layout: {{
      background: {{ color: '{C.BG}' }},
      textColor: '{C.MUTED}',
    }},
    grid: {{
      vertLines: {{ color: 'transparent' }},
      horzLines: {{ color: '{C.OVERLAY}' }},
    }},
    rightPriceScale: {{
      borderColor: '{C.OVERLAY}',
      scaleMargins: {{ top: 0.1, bottom: 0 }},
    }},
    timeScale: {{
      borderColor: '{C.OVERLAY}',
      visible: false,
    }},
    handleScroll: false,
    handleScale: false,
  }});

  const volSeries = volChart.addSeries(LightweightCharts.HistogramSeries, {{
    priceFormat: {{ type: 'volume' }},
    priceScaleId: '',
  }});
  volSeries.priceScale().applyOptions({{
    scaleMargins: {{ top: 0.1, bottom: 0 }},
  }});
  volSeries.setData(volumeData);

  // ── Sync time scales ──────────────────────────────────────────────────────
  chart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
    if (range !== null) volChart.timeScale().setVisibleLogicalRange(range);
  }});
  volChart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
    if (range !== null) chart.timeScale().setVisibleLogicalRange(range);
  }});

  // ── Crosshair tooltip in header ────────────────────────────────────────────
  chart.subscribeCrosshairMove(param => {{
    if (!param || !param.time) {{
      document.getElementById('bar-info').textContent = 'Hover over a candle to see OHLCV';
      return;
    }}
    const bar = param.seriesData.get(candleSeries);
    if (!bar) return;
    const d = new Date(param.time * 1000).toISOString().slice(0,10);
    const vol = param.seriesData.get(volSeries);
    const vStr = vol ? (' · Vol ' + Math.round(vol.value).toLocaleString()) : '';
    document.getElementById('bar-info').textContent =
      `${{d}}  O ${{bar.open.toFixed(2)}}  H ${{bar.high.toFixed(2)}}  L ${{bar.low.toFixed(2)}}  C ${{bar.close.toFixed(2)}}${{vStr}}`;
  }});

  // ── Zoom to last trading day ──────────────────────────────────────────────
  function _zoomToLastDay() {{
    if (!candleData.length) return;
    const lastTime = candleData[candleData.length - 1].time;
    const lastDate = new Date(lastTime * 1000);
    const startOfDay = Date.UTC(
      lastDate.getUTCFullYear(), lastDate.getUTCMonth(), lastDate.getUTCDate()
    ) / 1000;
    chart.timeScale().setVisibleRange({{ from: startOfDay, to: lastTime + 300 }});
  }}
  {initial_zoom_js}

{ctx_menu_js}
  // ── Resize observer ───────────────────────────────────────────────────────
  const ro = new ResizeObserver(() => {{
    chart.applyOptions({{ width: chartEl.clientWidth, height: chartEl.clientHeight }});
    volChart.applyOptions({{ width: volEl.clientWidth, height: volEl.clientHeight }});
  }});
  ro.observe(chartEl);
  ro.observe(volEl);

  // ── Measure tool (long-press to activate) ───────────────────────────────────
  // States: IDLE → PENDING (mousedown) → MEASURING (held 450 ms) → SHOWN
  // Moving > 6 px before the timer fires cancels PENDING (normal chart pan).
  // Clicking anywhere while SHOWN clears the measurement.
  const LONG_MS  = 450;
  const CANCEL_PX = 6;

  let msState   = 'IDLE';   // 'IDLE' | 'PENDING' | 'MEASURING' | 'SHOWN'
  let msTimer   = null;
  let msOrigin  = null;     // {{x, y}} chart-relative coords at press start
  let msCurrent = null;

  const overlay = document.getElementById('measure-overlay');
  const mRect   = document.getElementById('measure-rect');
  const mLabel  = document.getElementById('measure-label');

  function _msFreeze(on) {{
    chart.applyOptions({{ handleScroll: !on, handleScale: !on }});
  }}

  function _msClear() {{
    clearTimeout(msTimer);
    mRect.style.display  = 'none';
    mLabel.style.display = 'none';
    overlay.style.pointerEvents = 'none';
    overlay.style.cursor = '';
    chartEl.style.cursor = '';
    _msFreeze(false);
    msState = 'IDLE'; msOrigin = null; msCurrent = null;
  }}

  function _msRender(origin, current) {{
    const x1 = Math.min(origin.x, current.x);
    const y1 = Math.min(origin.y, current.y);
    const w  = Math.abs(current.x - origin.x);
    const h  = Math.abs(current.y - origin.y);

    mRect.style.display = 'block';
    mRect.style.left = x1 + 'px'; mRect.style.top    = y1 + 'px';
    mRect.style.width = w + 'px'; mRect.style.height = h  + 'px';

    const p1 = candleSeries.coordinateToPrice(origin.y);
    const p2 = candleSeries.coordinateToPrice(current.y);
    if (p1 === null || p2 === null) return;

    const delta = p2 - p1;
    const pct   = (delta / Math.abs(p1)) * 100;
    const up    = delta >= 0;
    const sign  = up ? '+' : '';

    const t1 = chart.timeScale().coordinateToTime(origin.x);
    const t2 = chart.timeScale().coordinateToTime(current.x);
    let bars = 0;
    if (t1 !== null && t2 !== null) {{
      const lo = Math.min(t1, t2), hi = Math.max(t1, t2);
      bars = candleData.filter(c => c.time >= lo && c.time <= hi).length;
    }}

    const barsStr = bars > 0 ? `  ${{bars}} bar${{bars !== 1 ? 's' : ''}}` : '';
    mLabel.textContent       = `${{sign}}${{delta.toFixed(2)}}  (${{sign}}${{pct.toFixed(2)}}%)${{barsStr}}`;
    mLabel.style.color       = up ? '#26a69a' : '#ef5350';
    mLabel.style.borderColor = up ? '#26a69a66' : '#ef535066';
    mRect.style.borderColor  = up ? '#26a69a88' : '#ef535088';
    mRect.style.background   = up ? 'rgba(38,166,154,0.08)' : 'rgba(239,83,80,0.08)';

    const labelTop  = y1 > 36 ? y1 - 28 : y1 + h + 4;
    mLabel.style.top    = labelTop + 'px';
    mLabel.style.left   = Math.max(4, x1 + w / 2 - 80) + 'px';
    mLabel.style.display = 'block';
  }}

  // Start long-press detection on the chart (pointer-events fall through overlay)
  chartEl.addEventListener('mousedown', function(e) {{
    if (e.button !== 0) return;
    if (msState === 'SHOWN') {{ _msClear(); return; }}
    if (msState !== 'IDLE') return;
    msOrigin = {{ x: e.offsetX, y: e.offsetY }};
    msState  = 'PENDING';
    msTimer  = setTimeout(function() {{
      if (msState !== 'PENDING') return;
      msState = 'MEASURING';
      _msFreeze(true);
      overlay.style.pointerEvents = 'auto';
      overlay.style.cursor = 'crosshair';
    }}, LONG_MS);
  }});

  // Cancel if the mouse moves too much before the timer fires
  chartEl.addEventListener('mousemove', function(e) {{
    if (msState !== 'PENDING') return;
    const dx = e.offsetX - msOrigin.x, dy = e.offsetY - msOrigin.y;
    if (dx*dx + dy*dy > CANCEL_PX * CANCEL_PX) {{
      clearTimeout(msTimer);
      msState = 'IDLE'; msOrigin = null;
    }}
  }});

  // Drag updates come from the overlay (pointer-events: auto once MEASURING)
  overlay.addEventListener('mousemove', function(e) {{
    if (msState !== 'MEASURING') return;
    msCurrent = {{ x: e.offsetX, y: e.offsetY }};
    _msRender(msOrigin, msCurrent);
  }});

  document.addEventListener('mouseup', function() {{
    if (msState === 'PENDING') {{ clearTimeout(msTimer); msState = 'IDLE'; return; }}
    if (msState === 'MEASURING') {{
      overlay.style.cursor = '';
      if (msCurrent) {{ msState = 'SHOWN'; }}
      else           {{ _msClear(); }}
    }}
  }});

  overlay.addEventListener('mousedown', function(e) {{
    if (msState === 'SHOWN') {{ _msClear(); e.stopPropagation(); }}
  }});

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') _msClear();
  }});

  // ── Live data update — called from Python via runJavaScript ───────────────
  // Replaces candle + volume data without reloading the page, so the user's
  // current zoom / scroll position is preserved.
  window.updateChartData = function(newCandleData, newVolumeData) {{
    if (!newCandleData || newCandleData.length === 0) return;
    const range = chart.timeScale().getVisibleLogicalRange();
    candleData  = newCandleData;
    volumeData  = newVolumeData;
    candleSeries.setData(candleData);
    volSeries.setData(volumeData);
    if (range !== null) {{
      chart.timeScale().setVisibleLogicalRange(range);
    }}
  }};

}})();
</script>
</body>
</html>
"""


class CandleChartPanel(QWidget):
    """FO-GUI-011 — Candle Chart Viewer.

    Displays OHLCV candlestick data from the local candles.db for any
    symbol available in the database.  Uses TradingView Lightweight Charts
    v5 (Apache 2.0) rendered via QWebEngineView.
    """

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._current_symbol: str = ""
        self._current_tf: str = "1d"

        self._build_ui()

        # Populate symbol list on first show
        self._refresh_symbol_list()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet(
            f"background:{C.SURFACE}; border-bottom:1px solid {C.OVERLAY};"
        )
        trow = QHBoxLayout(toolbar)
        trow.setContentsMargins(12, 0, 12, 0)
        trow.setSpacing(10)

        lbl = QLabel("Symbol:")
        lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        trow.addWidget(lbl)

        self._sym_combo = QComboBox()
        self._sym_combo.setFixedWidth(120)
        self._sym_combo.setEditable(True)
        self._sym_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._sym_combo.setStyleSheet(
            f"QComboBox {{ background:{C.BG}; color:{C.TEXT}; border:1px solid {C.OVERLAY};"
            f" border-radius:4px; padding:2px 6px; font-size:8pt; outline:none; }}"
            f"QComboBox:focus {{ border:1px solid {C.BLUE}; outline:none; }}"
            f"QComboBox::drop-down {{ border:none; }}"
            f"QComboBox QAbstractItemView {{ background:{C.SURFACE}; color:{C.TEXT};"
            f" selection-background-color:{C.OVERLAY}; }}"
        )
        # Autocomplete: case-insensitive contains match on all DB symbols
        self._sym_completer = QCompleter(self)
        self._sym_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._sym_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._sym_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._sym_completer.setMaxVisibleItems(12)
        self._sym_completer.popup().setStyleSheet(
            f"QAbstractItemView {{ background:{C.SURFACE}; color:{C.TEXT};"
            f" border:1px solid {C.OVERLAY}; selection-background-color:{C.OVERLAY};"
            f" font-size:8pt; }}"
        )
        self._sym_combo.setCompleter(self._sym_completer)
        trow.addWidget(self._sym_combo)

        tf_lbl = QLabel("Timeframe:")
        tf_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        trow.addWidget(tf_lbl)

        self._tf_combo = QComboBox()
        self._tf_combo.setFixedWidth(70)
        self._tf_combo.addItems(["1d", "1w"])
        self._tf_combo.setStyleSheet(
            f"QComboBox {{ background:{C.BG}; color:{C.TEXT}; border:1px solid {C.OVERLAY};"
            f" border-radius:4px; padding:2px 6px; font-size:8pt; outline:none; }}"
            f"QComboBox:focus {{ border:1px solid {C.BLUE}; outline:none; }}"
            f"QComboBox::drop-down {{ border:none; }}"
            f"QComboBox QAbstractItemView {{ background:{C.SURFACE}; color:{C.TEXT};"
            f" selection-background-color:{C.OVERLAY}; }}"
        )
        trow.addWidget(self._tf_combo)

        bars_lbl = QLabel("Bars:")
        bars_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        trow.addWidget(bars_lbl)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(20, 2000)
        self._limit_spin.setValue(500)
        self._limit_spin.setSingleStep(50)
        self._limit_spin.setFixedWidth(70)
        self._limit_spin.setStyleSheet(
            f"QSpinBox {{ background:{C.BG}; color:{C.TEXT}; border:1px solid {C.OVERLAY};"
            f" border-radius:4px; padding:2px 6px; font-size:8pt; outline:none; }}"
            f"QSpinBox:focus {{ border:1px solid {C.BLUE}; outline:none; }}"
        )
        trow.addWidget(self._limit_spin)

        self._load_btn = QPushButton("Load Chart")
        self._load_btn.setFixedHeight(28)
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}22; color:{C.BLUE}; border:1px solid {C.BLUE}55;"
            f" border-radius:5px; padding:0 14px; font-size:8pt; }}"
            f"QPushButton:hover {{ background:{C.BLUE}44; }}"
            f"QPushButton:pressed {{ background:{C.BLUE}66; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        self._load_btn.clicked.connect(self._on_load)
        trow.addWidget(self._load_btn)

        trow.addStretch()

        self._status_lbl = QLabel("Select a symbol and click Load Chart")
        self._status_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        trow.addWidget(self._status_lbl)

        self._refresh_btn = QPushButton("↺ Refresh List")
        self._refresh_btn.setFixedHeight(26)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.MUTED}; border:1px solid {C.OVERLAY};"
            f" border-radius:4px; padding:0 8px; font-size:7pt; }}"
            f"QPushButton:hover {{ color:{C.TEXT}; border-color:{C.TEXT}; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        self._refresh_btn.clicked.connect(self._refresh_symbol_list)
        trow.addWidget(self._refresh_btn)

        root.addWidget(toolbar)

        # ── WebEngine view ─────────────────────────────────────────────────────
        self._web = QWebEngineView()
        self._web.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._web.setStyleSheet(f"background:{C.BG};")
        root.addWidget(self._web, 1)

        # Show placeholder on first load
        self._show_placeholder()

        # Wire enter key on combo
        self._sym_combo.lineEdit().returnPressed.connect(self._on_load)  # type: ignore[union-attr]
        self._tf_combo.currentIndexChanged.connect(self._auto_reload_if_loaded)
        self._limit_spin.editingFinished.connect(self._auto_reload_if_loaded)

    # ── Logic ──────────────────────────────────────────────────────────────────

    def _refresh_symbol_list(self) -> None:
        """Repopulate the symbol dropdown from candles.db."""
        current = self._sym_combo.currentText()
        self._sym_combo.blockSignals(True)
        self._sym_combo.clear()
        symbols = self._svc.get_candle_symbols()
        self._sym_combo.addItems(symbols)
        if current in symbols:
            self._sym_combo.setCurrentText(current)
        elif symbols:
            self._sym_combo.setCurrentIndex(0)
        self._sym_completer.setModel(QStringListModel(symbols, self._sym_completer))
        self._sym_combo.blockSignals(False)
        count = len(symbols)
        if count:
            self._status_lbl.setText(f"{count} symbols in DB — select one and click Load Chart")
        else:
            self._status_lbl.setText("No candle data in DB yet")

    def _on_load(self) -> None:
        symbol = self._sym_combo.currentText().strip().upper()
        if not symbol:
            return
        tf = self._tf_combo.currentText()
        limit = self._limit_spin.value()
        self._load_chart(symbol, tf, limit)

    def _auto_reload_if_loaded(self) -> None:
        if self._current_symbol:
            self._on_load()

    def _load_chart(self, symbol: str, timeframe: str, limit: int) -> None:
        self._status_lbl.setText(f"Loading {symbol} ({timeframe.upper()})…")
        candles = self._svc.get_candles_for_symbol(symbol, timeframe, limit)
        if not candles:
            self._status_lbl.setText(f"No data for {symbol} ({timeframe.upper()})")
            self._show_no_data(symbol, timeframe)
            return

        volume_data = [
            {
                "time": c["time"],
                "value": c["volume"],
                "color": "#26a69a55" if c["close"] >= c["open"] else "#ef535055",
            }
            for c in candles
        ]

        html = _build_html(candles, volume_data, symbol, timeframe)
        self._web.setHtml(html, QUrl("about:blank"))
        self._current_symbol = symbol
        self._current_tf = timeframe
        self._status_lbl.setText(
            f"{symbol} · {timeframe.upper()} · {len(candles)} bars"
        )

    def _show_placeholder(self) -> None:
        placeholder = f"""<!DOCTYPE html><html><body style="
          margin:0; background:{C.BG}; display:flex; align-items:center;
          justify-content:center; height:100vh; font-family:monospace;">
          <div style="text-align:center; color:{C.OVERLAY2};">
            <div style="font-size:48px; margin-bottom:16px;">📈</div>
            <div style="font-size:16px; color:{C.MUTED};">Select a symbol and click <b style="color:{C.TEXT}">Load Chart</b></div>
            <div style="font-size:11px; margin-top:8px; color:{C.OVERLAY2};">
              Powered by TradingView Lightweight Charts (Apache 2.0)
            </div>
          </div>
        </body></html>"""
        self._web.setHtml(placeholder)

    def _show_no_data(self, symbol: str, timeframe: str) -> None:
        html = f"""<!DOCTYPE html><html><body style="
          margin:0; background:{C.BG}; display:flex; align-items:center;
          justify-content:center; height:100vh; font-family:monospace;">
          <div style="text-align:center; color:{C.OVERLAY2};">
            <div style="font-size:36px; margin-bottom:12px;">⚠</div>
            <div style="font-size:14px; color:{C.MUTED};">
              No <b style="color:{C.TEXT}">{timeframe.upper()}</b> data found for
              <b style="color:{C.YELLOW}">{symbol}</b>
            </div>
            <div style="font-size:11px; margin-top:8px;">
              Download candle data from Settings → Database.
            </div>
          </div>
        </body></html>"""
        self._web.setHtml(html)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Refresh symbol list every time the tab becomes visible."""
        super().showEvent(event)
        self._refresh_symbol_list()
