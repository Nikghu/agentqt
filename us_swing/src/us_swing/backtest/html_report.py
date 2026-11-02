"""
Module: MD-BKT-002.083.M15 — backtest/html_report.py
Parent SRD: SRD-BKT-002.083

One self-contained HTML page for a saved run in the trade analysis layout
(SRD-BKT-002.084): result header, edge / luck / quality boxes, P&L of every trade,
equity against the benchmark, hold time and exit groups, best and worst trades,
the trade list and all measures. One small inline script adds hover values to the
equity chart; there are no outside links, so the page opens offline.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape

import pandas as pd

from us_swing.backtest.steps.report import Report
from us_swing.core.dates import show_date

ET = "America/New_York"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_REASONS = {"strategy": "Exit rule", "stop": "Stop loss", "target": "Target",
            "end_time": "End time", "end_of_test": "Open at end"}
_HOLD_BUCKETS = (("Same day", 0, 1), ("1–13 d", 1, 14), ("2–4 wk", 14, 30),
                 ("1–2 mo", 30, 60), ("Over 2 mo", 60, 10**6))
_EQ_COLOR, _BENCH_COLOR = "#2a78d6", "#94a3b8"

_CSS = """
:root { --bg:#fff; --ink:#0f172a; --ink2:#64748b; --line:#e2e8f0; --soft:#f1f5f9;
        --pos:#15803d; --neg:#b91c1c; --accent:#2a78d6; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 13px/1.45 "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif; }
.page { max-width: 1040px; margin: 0 auto; padding: 0 32px 40px; }
.band { background: var(--soft); border-bottom: 1px solid var(--line); margin: 0 -32px 22px;
        padding: 22px 32px; }
h1 { font-size: 21px; margin: 0 0 6px; } h2 { font-size: 17px; margin: 34px 0 12px; }
h3 { font-size: 13px; margin: 0 0 2px; }
.mut { color: var(--ink2); } .small { font-size: 12px; }
.pos { color: var(--pos); } .neg { color: var(--neg); }
.facts { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 12px; }
.facts span { color: var(--ink2); margin-right: 5px; }
.result { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px;
          margin-bottom: 18px; }
.big { font-size: 30px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.row { display: grid; gap: 18px; margin-bottom: 18px; }
.r3 { grid-template-columns: repeat(3, 1fr); } .r2 { grid-template-columns: 1fr 1fr; }
.wide { grid-template-columns: 1.45fr 1fr; }
.box { border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; min-width: 0; }
.box > p { margin: 0 0 10px; font-size: 12px; color: var(--ink2); }
.box h3 + p { margin-top: 0; }
.box table + h3 { margin-top: 16px; }
table { border-collapse: collapse; width: 100%; }
th { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
     color: var(--ink2); text-align: left; }
th, td { padding: 5px 8px; border-bottom: 1px solid var(--line); }
.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.kv td { border: 0; padding: 4px 0; } .kv td:first-child { color: var(--ink2); }
tbody tr:hover td { background: #f8fafc; }
.tag { display: inline-block; font-size: 11px; padding: 0 8px; border-radius: 99px;
       border: 1px solid var(--line); color: var(--ink2); white-space: nowrap; }
.tag.open { border-color: var(--accent); color: var(--accent); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--ink2);
          margin-bottom: 6px; }
.legend i { display: inline-block; width: 14px; height: 2px; vertical-align: middle;
            margin-right: 6px; }
.legend i.dash { background: repeating-linear-gradient(90deg, var(--ink2) 0 4px,
                 transparent 4px 7px); }
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.tip { position: absolute; pointer-events: none; background: var(--ink); color: #f8fafc;
       font-size: 12px; padding: 6px 9px; border-radius: 6px; white-space: nowrap;
       transform: translate(-50%, -100%); display: none; }
.cols { columns: 2; column-gap: 32px; } .cols table { break-inside: avoid; }
@media print { .band { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
               tr, .box { break-inside: avoid; } }
"""

_SCRIPT = """
document.querySelectorAll("svg[data-dates]").forEach(function (svg) {
  var d = svg.dataset, dates = d.dates.split(","), names = d.names.split("|");
  var lines = d.values.split("|").map(function (s) { return s.split(",").map(Number); });
  var L = +d.l, R = +d.r, T = +d.t, B = +d.b, lo = +d.lo, hi = +d.hi, W = +d.w, n = dates.length;
  var tip = svg.parentNode.querySelector(".tip"), cx = svg.querySelector(".cx");
  var dots = svg.querySelectorAll(".dot");
  function x(i) { return L + i * (R - L) / Math.max(n - 1, 1); }
  function y(v) { return T + (hi - v) * (B - T) / (hi - lo); }
  function usd(v) { return (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  var hit = svg.querySelector(".hit");
  hit.addEventListener("mousemove", function (e) {
    var r = svg.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width;
    var i = Math.max(0, Math.min(n - 1, Math.round((sx - L) * (n - 1) / (R - L))));
    cx.setAttribute("x1", x(i)); cx.setAttribute("x2", x(i)); cx.style.display = "";
    var html = "<div>" + dates[i] + "</div>", top = B;
    lines.forEach(function (vals, k) {
      var v = vals[i];
      if (isNaN(v)) { dots[k].style.display = "none"; return; }
      dots[k].setAttribute("cx", x(i)); dots[k].setAttribute("cy", y(v));
      dots[k].style.display = ""; top = Math.min(top, y(v));
      html += "<div>" + names[k] + ": <b>" + usd(v) + "</b></div>";
    });
    tip.innerHTML = html; tip.style.display = "block";
    tip.style.left = (x(i) * r.width / W) + "px";
    tip.style.top = (top * r.height / svg.viewBox.baseVal.height - 10) + "px";
  });
  hit.addEventListener("mouseleave", function () {
    tip.style.display = "none"; cx.style.display = "none";
    dots.forEach(function (p) { p.style.display = "none"; });
  });
});
"""


@dataclass(frozen=True)
class _Trade:
    n: int
    strategy: str
    symbol: str
    entry: str
    entry_px: float
    qty: int
    exit: str
    exit_px: float
    hold: int
    move: float
    pnl: float
    reason: str


def fmt(value: float, kind: str) -> str:
    """Stat value as text: $ with sign, %, ratio, days or count; NaN as a dash."""
    if value is None or math.isnan(value):
        return "—"
    if kind == "usd":
        return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "ratio":
        return f"{value:.2f}"
    if kind == "days":
        return f"{value:.0f} days"
    if kind == "hours":
        return f"{value / 24:.0f} d" if value >= 24 else f"{value:.1f} h"
    return f"{value:,.0f}"


def _day(iso: str) -> str:
    """ISO date text as DD-MM-YYYY."""
    return show_date(pd.Timestamp(iso))


def _day_month(iso: str) -> str:
    return f"{iso[8:10]}-{iso[5:7]}"


def _signed(value: float) -> str:
    return "+" + fmt(value, "usd") if value > 0 else fmt(value, "usd")


def _tone(value: float) -> str:
    return "pos" if value > 0 else "neg" if value < 0 else ""


def _cls(*names: str) -> str:
    return " ".join(n for n in names if n)


def _usd_cell(value: float) -> str:
    return f'<td class="{_cls("n", _tone(value))}">{_signed(value)}</td>'


def _table(headers: Sequence[str], rows: Sequence[str], numeric: Sequence[bool]) -> str:
    """``rows`` are ready ``<tr>`` contents; ``numeric`` right-aligns header columns."""
    head = "".join(f'<th class="n">{escape(h)}</th>' if num else f"<th>{escape(h)}</th>"
                   for h, num in zip(headers, numeric))
    body = "".join(f"<tr>{r}</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _kv(rows: Sequence[tuple[str, str, str]]) -> str:
    """Label / value rows; the value is ready HTML with its own tone class."""
    body = "".join(f'<tr><td>{escape(k)}</td><td class="{_cls("n", tone)}">{v}</td></tr>'
                   for k, v, tone in rows)
    return f'<table class="kv"><tbody>{body}</tbody></table>'


def _ticks(low: float, high: float, count: int = 4) -> list[float]:
    raw = (high - low) / count or 1.0
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    first = math.floor(low / step) * step
    return [first + i * step for i in range(int(math.ceil((high - first) / step - 1e-9)) + 1)]


def _short_usd(value: float) -> str:
    return f"-${-value:,.0f}" if value < 0 else f"${value:,.0f}"


def _trade_rows(rep: Report) -> list[_Trade]:
    t = rep.trades
    if t.empty:
        return []
    entry = pd.to_datetime(t["entry_ts"], utc=True).dt.tz_convert(ET)
    exit_ = pd.to_datetime(t["exit_ts"], utc=True).dt.tz_convert(ET)
    holds = (exit_.dt.normalize() - entry.dt.normalize()).dt.days.astype(int).tolist()
    sign = [-1.0 if d == "SHORT" else 1.0 for d in t["direction"]]
    cols = zip(t["strategy"].astype(str), t["symbol"].astype(str), entry.dt.strftime("%Y-%m-%d"),
               t["entry_px"].astype(float).tolist(), t["qty"].astype(int).tolist(),
               exit_.dt.strftime("%Y-%m-%d"), t["exit_px"].astype(float).tolist(), holds, sign,
               t["net_pnl"].astype(float).tolist(), t["exit_reason"].astype(str))
    return [_Trade(i, st, sym, ent, epx, qty, ext, xpx, hold,
                   s * (xpx / epx - 1.0) if epx else math.nan, pnl, why)
            for i, (st, sym, ent, epx, qty, ext, xpx, hold, s, pnl, why)
            in enumerate(cols, start=1)]


def equity_svg(daily: pd.DataFrame, capital: float) -> str:
    """Equity (and benchmark when present) with axes, start-capital line and hover data."""
    if daily.empty:
        return '<p class="mut">No days to draw</p>'
    lines = [("This run", _EQ_COLOR, daily["equity"].astype(float).tolist())]
    bench = daily["benchmark"].astype(float).tolist() if "benchmark" in daily else []
    if any(not math.isnan(v) for v in bench):
        lines.append(("Benchmark", _BENCH_COLOR, bench))
    values = [v for _n, _c, arr in lines for v in arr if not math.isnan(v)] + [capital]
    ticks = _ticks(min(values), max(values))
    low, high = ticks[0], ticks[-1]
    width, height, left, right, top, bottom = 620, 280, 58, 548, 10, 254
    n = len(daily)

    def x(i: int) -> float:
        return left + i * (right - left) / max(n - 1, 1)

    def y(v: float) -> float:
        return top + (high - v) * (bottom - top) / ((high - low) or 1.0)

    parts = [f'<line x1="{left}" x2="{right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e2e8f0"/>'
             f'<text x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end" font-size="11" '
             f'fill="#64748b">{_short_usd(t)}</text>' for t in ticks]
    dates = [str(d) for d in daily["date"]]
    starts = [i for i, d in enumerate(dates) if i == 0 or d[5:7] != dates[i - 1][5:7]]
    for k, i in enumerate(starts[:: 2 if len(starts) > 7 else 1]):
        label = _MONTHS[int(dates[i][5:7]) - 1] + (f" {dates[i][2:4]}"
                                                   if k == 0 or dates[i][5:7] == "01" else "")
        parts.append(f'<text x="{x(i):.1f}" y="{height - 6}" text-anchor="middle" '
                     f'font-size="11" fill="#64748b">{label}</text>')
    parts.append(f'<line x1="{left}" x2="{right}" y1="{y(capital):.1f}" y2="{y(capital):.1f}" '
                 'stroke="#64748b" stroke-dasharray="4 4" opacity=".7"/>')
    ends: list[float] = []
    for k, (name, color, arr) in enumerate(lines):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(arr) if not math.isnan(v))
        if k == 0:
            parts.append(f'<polygon points="{x(0):.1f},{bottom} {pts} {x(n - 1):.1f},{bottom}" '
                         f'fill="{color}" opacity=".08"/>')
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                     f'stroke-width="{2 if k == 0 else 1.6}" stroke-linejoin="round"/>')
        last = next((v for v in reversed(arr) if not math.isnan(v)), math.nan)
        if not math.isnan(last):
            ly = y(last)
            if ends and abs(ly - ends[0]) < 26:
                ly = ends[0] + (26 if ly >= ends[0] else -26)
            ends.append(ly)
            parts.append(f'<circle cx="{right}" cy="{y(last):.1f}" r="3.5" fill="{color}"/>'
                         f'<text x="{right + 8}" y="{ly - 1:.1f}" font-size="11" '
                         f'font-weight="600" fill="#0f172a">{_short_usd(last)}</text>'
                         f'<text x="{right + 8}" y="{ly + 12:.1f}" font-size="10.5" '
                         f'fill="#64748b">{name}</text>')
    parts.append(f'<line class="cx" y1="{top}" y2="{bottom}" stroke="#64748b" opacity=".5" '
                 'style="display:none"/>')
    parts += [f'<circle class="dot" r="4" fill="{c}" stroke="#fff" stroke-width="2" '
              'style="display:none"/>' for _n, c, _a in lines]
    parts.append(f'<rect class="hit" x="{left}" y="{top}" width="{right - left}" '
                 f'height="{bottom - top}" fill="transparent"/>')
    data = (f'data-dates="{",".join(_day(d) for d in dates)}" '
            f'data-names="{"|".join(n for n, _c, _a in lines)}" '
            f'data-values="{"|".join(",".join(f"{v:.2f}" for v in a) for _n, _c, a in lines)}" '
            f'data-l="{left}" data-r="{right}" data-t="{top}" data-b="{bottom}" '
            f'data-lo="{low}" data-hi="{high}" data-w="{width}"')
    return (f'<div class="chart"><svg viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="Account value against the benchmark" {data}>{"".join(parts)}</svg>'
            '<div class="tip"></div></div>')


def trade_bars_svg(trades: Sequence[_Trade]) -> str:
    """One bar per trade in exit order; each bar's title gives stock, date and result."""
    if not trades:
        return '<p class="mut">No trades</p>'
    ordered = sorted(trades, key=lambda t: (t.exit, t.n))
    ticks = _ticks(min(0.0, *(t.pnl for t in ordered)), max(0.0, *(t.pnl for t in ordered)))
    low, high = ticks[0], ticks[-1]
    width, height, left, right, top, bottom = 960, 200, 58, 952, 8, 192
    slot = (right - left) / len(ordered)
    gap = max(1.0, slot * 0.2)

    def y(v: float) -> float:
        return top + (high - v) * (bottom - top) / ((high - low) or 1.0)

    parts = [f'<line x1="{left}" x2="{right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e2e8f0"/>'
             f'<text x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end" font-size="11" '
             f'fill="#64748b">{_short_usd(t)}</text>' for t in ticks]
    for i, t in enumerate(ordered):
        y0, y1 = sorted((y(0.0), y(t.pnl)))
        color = "#15803d" if t.pnl >= 0 else "#b91c1c"
        parts.append(
            f'<rect x="{left + i * slot + gap / 2:.1f}" y="{y0:.1f}" width="{slot - gap:.1f}" '
            f'height="{max(y1 - y0, 1.0):.1f}" rx="2" fill="{color}">'
            f"<title>{escape(t.symbol)} · {_day(t.exit)} · {_signed(t.pnl)} · {t.move:+.1%} · "
            f"{t.hold} d</title></rect>")
    parts.append(f'<line x1="{left}" x2="{right}" y1="{y(0.0):.1f}" y2="{y(0.0):.1f}" '
                 'stroke="#64748b"/>')
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="Profit or loss of each trade">{"".join(parts)}</svg>')


def _boxes(rep: Report, trades: Sequence[_Trade]) -> str:
    s = {st.name: st for st in rep.stats}

    def v(name: str) -> str:
        return fmt(s[name].value, s[name].kind) if name in s else "—"

    def tone(name: str) -> str:
        return _tone(s[name].value) if name in s else ""

    top5 = sum(sorted((t.pnl for t in trades), reverse=True)[:5])
    edge = _kv([("Expectancy", f"<b>{v('Expectancy')}</b>", tone("Expectancy")),
                ("Win rate", v("Win rate"), ""),
                ("Average win / loss", f"{v('Average win')} / {v('Average loss')}", ""),
                ("Payoff", v("Payoff") + "×", "")])
    luck = _kv([("Best 5 trades made", _signed(top5), _tone(top5)),
                ("Without them", f"<b>{v('P&L without top 5 trades')}</b>",
                 tone("P&L without top 5 trades")),
                ("First / second half", f"{v('First half P&L')} / {v('Second half P&L')}", ""),
                ("Longest loss streak", v("Longest loss streak") + " in a row", "")])
    quality = _kv([("Average best point (MFE)", v("Average MFE"), "pos"),
                   ("Average worst point (MAE)", v("Average MAE"), "neg"),
                   ("Profit given back", v("Profit given back"), ""),
                   ("Typical hold", v("Median hold"), "")])
    return ('<div class="row r3">'
            f'<div class="box"><h3>Edge per trade</h3><p>Average result of one trade</p>{edge}</div>'
            f'<div class="box"><h3>Luck check</h3><p>How much rests on a few trades</p>{luck}</div>'
            f'<div class="box"><h3>Trade quality</h3><p>Did trades give back gains?</p>{quality}'
            "</div></div>")


def _group_table(groups: Sequence[tuple[str, Sequence[_Trade]]]) -> str:
    rows = []
    for name, ts in groups:
        if not ts:
            continue
        won = sum(t.pnl > 0 for t in ts) / len(ts)
        rows.append(f"<td>{escape(name)}</td><td class=\"n\">{len(ts)}</td>"
                    f'<td class="n">{won:.0%}</td>{_usd_cell(sum(t.pnl for t in ts))}')
    return _table(["", "Trades", "Won", "Net P&L"], rows, [False, True, True, True])


def _groups(trades: Sequence[_Trade]) -> str:
    hold = [(name, [t for t in trades if lo <= t.hold < hi]) for name, lo, hi in _HOLD_BUCKETS]
    reasons = list(dict.fromkeys(t.reason for t in trades))
    exits = [(_REASONS.get(r, r), [t for t in trades if t.reason == r]) for r in reasons]
    html = ("<h3>By hold time</h3><p class=\"small mut\">Trades grouped by days held</p>"
            + _group_table(hold)
            + "<h3>By exit</h3><p class=\"small mut\">How each trade ended</p>"
            + _group_table(exits))
    strategies = list(dict.fromkeys(t.strategy for t in trades))
    if len(strategies) > 1:
        html += ("<h3>By strategy</h3><p class=\"small mut\">Each strategy's share</p>"
                 + _group_table([(s, [t for t in trades if t.strategy == s])
                                 for s in strategies]))
    return html


def _ranked(trades: Sequence[_Trade]) -> str:
    if not trades:
        return '<p class="mut">None</p>'
    rows = [f"<td><b>{escape(t.symbol)}</b></td>"
            f'<td class="n mut">{_day_month(t.entry)} → {_day_month(t.exit)}</td>'
            f'<td class="n mut">{t.hold} d</td>'
            f'<td class="{_cls("n", _tone(t.move))}">{t.move:+.1%}</td>{_usd_cell(t.pnl)}'
            for t in trades]
    return "<table><tbody>" + "".join(f"<tr>{r}</tr>" for r in rows) + "</tbody></table>"


def _all_trades(trades: Sequence[_Trade]) -> str:
    if not trades:
        return '<p class="mut">No trades</p>'
    rows = [f'<td class="n mut">{t.n}</td><td><b>{escape(t.symbol)}</b></td>'
            f"<td>{escape(t.strategy)}</td>"
            f'<td class="n">{_day(t.entry)}</td><td class="n">{t.entry_px:.2f}</td>'
            f'<td class="n">{t.qty}</td><td class="n">{_day(t.exit)}</td>'
            f'<td class="n">{t.exit_px:.2f}</td><td class="n">{t.hold} d</td>'
            f'<td class="{_cls("n", _tone(t.move))}">{t.move:+.1%}</td>{_usd_cell(t.pnl)}'
            f'<td><span class="{_cls("tag", "open" if t.reason == "end_of_test" else "")}">'
            f"{escape(_REASONS.get(t.reason, t.reason))}</span></td>"
            for t in trades]
    return _table(["#", "Stock", "Strategy", "Entry", "Entry $", "Shares", "Exit", "Exit $",
                   "Held", "Move", "Net P&L", "Exit"], rows,
                  [True, False, False, True, True, True, True, True, True, True, True, False])


def _all_stats(rep: Report) -> str:
    rows = [f"<td>{escape(s.name)}</td><td class=\"n\">{fmt(s.value, s.kind)}</td>"
            for s in rep.stats]
    half = (len(rows) + 1) // 2
    return ('<div class="cols">'
            + "".join("<table><tbody>" + "".join(f"<tr>{r}</tr>" for r in part)
                      + "</tbody></table>" for part in (rows[:half], rows[half:]))
            + "</div>")


def _variant(rep: Report, title: bool) -> str:
    trades = _trade_rows(rep)
    net, ret = rep.stat("Net P&L"), rep.stat("Return")
    bench = rep.daily["benchmark"].astype(float).dropna() if "benchmark" in rep.daily else None
    vs = (f" · benchmark {bench.iloc[-1] / rep.capital - 1:+.1%}"
          if bench is not None and len(bench) and rep.capital else "")
    wins = sorted((t for t in trades if t.pnl > 0), key=lambda t: -t.pnl)[:5]
    losses = sorted((t for t in trades if t.pnl < 0), key=lambda t: t.pnl)[:5]
    legend = ('<div class="legend"><span><i style="background:%s"></i>This run</span>%s'
              '<span><i class="dash"></i>Start capital</span></div>'
              % (_EQ_COLOR, f'<span><i style="background:{_BENCH_COLOR}"></i>Benchmark '
                            "(test stocks, equal weight)</span>" if vs else ""))
    won = sum(t.pnl > 0 for t in trades)
    return (
        (f"<h2>{escape(rep.label)}</h2>" if title else "")
        + '<div class="result"><div class="small mut">'
        f"{len(trades)} trades · {won} won · {len(trades) - won} lost</div>"
        f'<div style="text-align:right"><div class="small mut">Net P&amp;L</div>'
        f'<div class="big {_tone(net)}">{_signed(net)}</div>'
        f'<div class="small mut">{ret:+.1%} return{vs}</div></div></div>'
        + _boxes(rep, trades)
        + '<div class="box" style="margin-bottom:18px"><h3>Every trade, in exit order</h3>'
        "<p>One bar per trade. Hover a bar for stock, date and result.</p>"
        + trade_bars_svg(trades) + "</div>"
        + '<div class="row wide"><div class="box"><h3>Account value</h3>'
        + legend + equity_svg(rep.daily, rep.capital) + "</div>"
        + f'<div class="box">{_groups(trades)}</div></div>'
        + '<div class="row r2">'
        f'<div class="box"><h3>Best trades</h3><p>Top 5 winners</p>{_ranked(wins)}</div>'
        f'<div class="box"><h3>Worst trades</h3><p>Top 5 losers</p>{_ranked(losses)}</div></div>'
        + '<div class="box" style="margin-bottom:18px"><h3>All trades</h3>'
        "<p>\"Open at end\" means the test stopped before the exit rule fired.</p>"
        + _all_trades(trades) + "</div>"
        + f'<div class="box"><h3>All measures</h3><p>Every Step 4 measure</p>{_all_stats(rep)}'
        "</div>"
    )


def render(name: str, saved_at: str, facts: Sequence[tuple[str, str]],
           reports: Sequence[Report]) -> str:
    """The whole page (SRD-BKT-002.084); one section per variant, titled when there are more."""
    chips = "".join(f"<div><span>{escape(k)}</span>{escape(v)}</div>" for k, v in facts)
    body = "".join(_variant(rep, len(reports) > 1) for rep in reports) or (
        '<p class="mut">This run has no results</p>')
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(name)} · Backtest report</title><style>{_CSS}</style></head><body>"
        f'<div class="page"><div class="band"><div class="small mut">Backtest · trade analysis · '
        f"saved {escape(saved_at)}</div><h1>{escape(name)}</h1>"
        f'<div class="facts">{chips}</div></div>{body}</div>'
        f"<script>{_SCRIPT}</script></body></html>"
    )
