"""
Module: MD-EXE-022.017.M07 — usswing chart preview
Parent SRD: SRD-EXE-022.017

Draw an indicator on its candles in the browser, for tests and scripts only.
An indicator file that imports this module is refused by the tool.

Example::

    from usswing.dev import preview
    from usswing.testing import load_candles
    from my_st import MySt

    preview(MySt, load_candles("AAPL", ["3m"], days=5))
"""
from __future__ import annotations

import html
import json
import math
import tempfile
import webbrowser
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from usswing._indicator import USSwingIndicator
from usswing.testing import run

__all__ = ["preview"]

_SCRIPT = "lightweight-charts.standalone.production.js"
_CDN = "https://unpkg.com/lightweight-charts@5.0.5/dist/" + _SCRIPT
_MARKET_TZ = "America/New_York"
_COLOURS = ("#f5a623", "#4aa3ff", "#b07cff", "#2ec4b6", "#ff6b9a", "#c5d86d")


def preview(indicator_class: type[USSwingIndicator], candles: Mapping[str, pd.DataFrame],
            values: Mapping[str, Any] | None = None, *, path: Path | str | None = None) -> Path:
    """Write one HTML chart of the candles, the indicator and its debug values, then open it.

    Args:
        indicator_class: Your indicator class.
        candles: ``{timeframe: frame}``, for example from ``usswing.testing.load_candles``.
        values: Parameter values; missing ones use the defaults.
        path: Where to save the HTML file; a temp file by default.

    Returns:
        The saved HTML file.
    """
    result = run(indicator_class, candles, values)
    main = candles[result.main_timeframe]
    times = _chart_times(result.times, result.main_timeframe)
    name = indicator_class.indicator_name or indicator_class.__name__
    data = {
        "title": f"{name} {indicator_class.version} — {result.main_timeframe}".strip(),
        "candles": [{"time": t, "open": float(o), "high": float(h), "low": float(lo),
                     "close": float(c)}
                    for t, o, h, lo, c in zip(times, main["open"], main["high"], main["low"],
                                              main["close"], strict=True)],
        "markers": _markers(times, result.values) if indicator_class.output_type == "signal"
        else [],
        "lines": ([] if indicator_class.output_type == "signal"
                  else [_line(name, times, result.values, _COLOURS[0])])
        + [_line(label, times, series, _COLOURS[(i + 1) % len(_COLOURS)])
           for i, (label, series) in enumerate(result.debug.items())],
    }
    target = Path(path) if path is not None else Path(tempfile.gettempdir()) / f"{name}.html"
    target.write_text(_page(data), encoding="utf-8")
    webbrowser.open(target.resolve().as_uri())
    return target


def _chart_times(times: pd.Series | None, timeframe: str) -> list[int]:
    """Chart time of each candle in New York wall-clock seconds (the chart has no time zone)."""
    if times is None:
        raise ValueError("The candles need a datetime column to draw a chart")
    stamps = pd.to_datetime(times)
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")
    if timeframe not in ("1d", "1w"):
        stamps = stamps.dt.tz_convert(_MARKET_TZ)
    wall = stamps.dt.tz_localize(None)
    return [int(stamp.timestamp()) for stamp in wall]


def _points(times: list[int], series: pd.Series) -> list[dict[str, float]]:
    return [{"time": t, "value": float(v)}
            for t, v in zip(times, series, strict=True) if not math.isnan(v)]


def _line(label: str, times: list[int], series: pd.Series, colour: str) -> dict[str, Any]:
    return {"name": label, "colour": colour, "points": _points(times, series)}


def _markers(times: list[int], series: pd.Series) -> list[dict[str, Any]]:
    marks: list[dict[str, Any]] = []
    for t, v in zip(times, series, strict=True):
        if math.isnan(v) or v == 0:
            continue
        up = v > 0
        marks.append({"time": t, "position": "belowBar" if up else "aboveBar",
                      "shape": "arrowUp" if up else "arrowDown",
                      "color": "#26a69a" if up else "#ef5350"})
    return marks


def _script_tag() -> str:
    """The tool's own chart script, read from the install; the web copy when not found."""
    here = Path(__file__).resolve()
    for root in here.parents[1:3]:
        for folder in ("us_swing/gui/resources", "src/us_swing/gui/resources"):
            script = root / folder / _SCRIPT
            if script.is_file():
                return f"<script>\n{script.read_text(encoding='utf-8')}\n</script>"
    return f'<script src="{_CDN}"></script>'


def _page(data: dict[str, Any]) -> str:
    payload = json.dumps(data).replace("</", "<\\/")
    return (_HTML.replace("__TITLE__", html.escape(data["title"]))
            .replace("__DATA__", payload)
            .replace("__SCRIPT__", _script_tag()))


_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; height: 100%; background: #0f1115; color: #d7dae0;
               font: 13px "Segoe UI", sans-serif; }
  #head { padding: 8px 12px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  #head b { font-size: 14px; }
  .key { display: inline-flex; align-items: center; gap: 6px; }
  .key i { width: 14px; height: 3px; display: inline-block; }
  #chart { position: absolute; top: 40px; bottom: 0; left: 0; right: 0; }
</style>
__SCRIPT__
</head>
<body>
<div id="head"><b>__TITLE__</b><span id="keys"></span></div>
<div id="chart"></div>
<script>
const data = __DATA__;
const chart = LightweightCharts.createChart(document.getElementById('chart'), {
  autoSize: true,
  layout: { background: { color: '#0f1115' }, textColor: '#d7dae0',
            panes: { separatorColor: '#2a2e36' } },
  grid: { vertLines: { color: '#1c1f26' }, horzLines: { color: '#1c1f26' } },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  timeScale: { timeVisible: true, secondsVisible: false },
});
const candles = chart.addSeries(LightweightCharts.CandlestickSeries, {
  upColor: '#26a69a', downColor: '#ef5350', borderUpColor: '#26a69a',
  borderDownColor: '#ef5350', wickUpColor: '#26a69a', wickDownColor: '#ef5350',
});
candles.setData(data.candles);
if (data.markers.length) {
  LightweightCharts.createSeriesMarkers(candles, data.markers);
}
const keys = document.getElementById('keys');
for (const line of data.lines) {
  const series = chart.addSeries(LightweightCharts.LineSeries,
    { color: line.colour, lineWidth: 2, title: line.name }, 1);
  series.setData(line.points);
  const key = document.createElement('span');
  key.className = 'key';
  key.innerHTML = '<i></i>';
  key.firstChild.style.background = line.colour;
  key.appendChild(document.createTextNode(line.name));
  keys.appendChild(key);
}
chart.timeScale().fitContent();
</script>
</body>
</html>
"""
