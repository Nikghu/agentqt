"""
Module: MD-GUI-046.007.M03 — indicator project guides
Parent SRD: SRD-GUI-046.008, SRD-GUI-046.010

The plain-language API guide (USSWING_API.md) and the guide for AI helpers
(CLAUDE.md) written into each indicator project.
"""
from __future__ import annotations

API_FILE = "USSWING_API.md"
AI_FILE = "CLAUDE.md"


def api_guide(check: str) -> str:
    """The USSwing indicator API guide; ``check`` is the check command for this PC."""
    return _API.replace("<<CHECK>>", check)


def ai_guide(name: str, stem: str, cls: str, check: str, sdk: str, builtins: str) -> str:
    """The guide an AI helper in VS Code reads before changing the indicator."""
    return (_AI.replace("<<NAME>>", name).replace("<<STEM>>", stem).replace("<<CLS>>", cls)
            .replace("<<CHECK>>", check).replace("<<SDK>>", sdk)
            .replace("<<BUILTINS>>", builtins))


_API = '''# USSwing custom indicators - how to write one

This guide explains, in plain words, how to make your own indicator for USSwing
and use it in a strategy's trigger condition.

## 1. What you need

| Tool | Needed for | How to get it |
|---|---|---|
| VS Code | Editing the indicator file | code.visualstudio.com |
| Claude Code (VS Code extension) | Optional: let AI write the indicator for you | In VS Code: Extensions, search "Claude Code" |
| Python | Optional: only the test file and the chart | In USSwing: Settings > Indicators > Set up Python |

Writing and checking an indicator needs no Python. USSwing checks it for you.

## 2. Your first indicator in 10 minutes

1. In USSwing open **Settings > Indicators > New indicator**, type a name such as
   `MY_ST` and press **Create**. VS Code opens the new project.
2. Open `my_st.py`. It already holds a working example. Change it, or ask Claude Code:
   *"Make a signal when the 3m close crosses above its 20 candle average."*
3. Check it. In VS Code: **Terminal > Run Task > Check indicator**, or run:

   ```
   <<CHECK>>
   ```

4. Fix every line that starts with ✘ and check again until it says
   `passed on N stock(s)`.
5. In USSwing open **Settings > Indicators > Import** and pick the file.
6. In a strategy, open the trigger condition popup: your indicator is at the end of the
   list, with your own options.

## 3. The indicator file

```python
from usswing import Input, Number, USSwingIndicator


class MySt(USSwingIndicator):
    indicator_name = "MY_ST"          # the name in the popup and in conditions
    description = "What it does, in one line"
    version = "1.0"
    output_type = "value"             # "value" or "signal"

    parameters = [                    # every option in the popup, in this order
        Input("Symbol Type", options=["Spot", "RSP"], default="Spot"),
        Number("Candles", default=20, minimum=2, maximum=500, whole_number=True),
        Input("Timeframe", options=["3m", "15m", "30m", "1d"], default="3m"),
    ]

    def calculate(self):
        candles = self.candles(
            symbol_type=self.parameter("Symbol Type"),
            timeframe=self.parameter("Timeframe"),
        )
        average = candles["close"].rolling(self.parameter("Candles")).mean()
        self.debug_value("Average", average)       # optional: shown in Check and the chart
        return candles["close"] - average           # one value per candle
```

One file holds one indicator class.

## 4. The details at the top

| Field | Meaning | Rule |
|---|---|---|
| `indicator_name` | Name in the popup and in conditions, e.g. `MY_ST(...)` | 2 to 32 capital letters, numbers or `_`, starting with a letter. Not a built-in name such as SWING, VWAP, EMA, RSI, MACD, ADX, SUPERTREND, BOSS_ST, Price, Number, PNL |
| `description` | One line shown to you | Not empty |
| `version` | Your own version, e.g. `"1.0"` | Not empty |
| `output_type` | `"value"`: a number per candle. `"signal"`: above 0 = up, below 0 = down, 0 = nothing | One of the two |

## 5. Options in the popup (`parameters`)

| Type | Popup shows | Example |
|---|---|---|
| `Number(label, default, minimum, maximum, whole_number=False)` | A number box that stays between minimum and maximum | `Number("Candles", default=20, minimum=1, maximum=500, whole_number=True)` |
| `Input(label, options, default)` | A dropdown | `Input("Price", options=["High", "Low"], default="High")` |

- The popup shows the options in the order of the list.
- In a strategy condition the values follow the same order, text in single quotes:
  `MY_ST('Spot', 20, '3m') > 0`.
- Every label must be different.

## 6. Inside `calculate()`

| Call | What you get |
|---|---|
| `self.parameter("Candles")` | The value the user chose for that option (a number or a text) |
| `self.candles(symbol_type=..., timeframe=...)` | The stock's closed candles as a table, oldest first. Columns: `datetime`, `open`, `high`, `low`, `close`, `volume`. Timeframes: 3m, 15m, 30m, 1d, 1w |
| `self.debug_value("Name", series)` | Keeps an extra line for Check and the chart. No effect on trading |

- The **first** timeframe you read is the main one. Return exactly one value per candle
  of it: a pandas Series, a list or a numpy array.
- NaN (empty) is fine while there are not enough candles yet. Infinite values are not.
- "Symbol Type" RSP gives the stock's own candles for now, the same as built-in indicators.

## 7. Rules the check enforces

- **No future candles.** A value must not change when newer candles arrive. Do not use
  `shift(-1)` (any negative shift) or `rolling(..., center=True)`.
- **Fast.** It must finish in under 2 seconds. Use pandas or numpy, not Python loops over
  many candles.
- **No `usswing.dev` in the indicator file.** Use the chart only in tests or scripts.
- No file or network access and no `sys.exit()` in the indicator.
- When live, 3 failures in a row on a stock stop the strategies that use it, and you get
  an alert. A strategy whose indicator is missing does not start.

## 8. Ready recipes (paste into `calculate()`)

**Moving average distance (value)**
```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
return c["close"] - c["close"].rolling(self.parameter("Candles")).mean()
```

**Close crosses its average (signal)**
```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
above = (c["close"] > c["close"].rolling(self.parameter("Candles")).mean()).astype(int)
return above.diff().fillna(0)        # 1 = crossed up, -1 = crossed down, 0 = no cross
```

**Two timeframes: 3m close above the 15m average (value 1 or 0)**
```python
import pandas as pd                                            # at the top of the file

fast = self.candles(symbol_type="Spot", timeframe="3m")        # main timeframe: read first
slow = self.candles(symbol_type="Spot", timeframe="15m")
slow_avg = slow["close"].rolling(20).mean()
slow_avg.index = slow["datetime"] + pd.Timedelta(minutes=15)   # when each 15m candle closed
fast_closed = fast["datetime"] + pd.Timedelta(minutes=3)       # when each 3m candle closed
lined_up = slow_avg.reindex(fast_closed, method="ffill").to_numpy()
return (fast["close"].to_numpy() > lined_up).astype(float)
```
`datetime` is the time a candle opens. Lining up by close time means each 3m candle only
sees 15m candles that had already closed, so no future candles are used.

**Swing high of the last N closed candles (value)**
```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
return c["high"].shift(1).rolling(self.parameter("Candles")).max()
```

## 9. Checking

Run the check after every change:

```
<<CHECK>>
```

Add `--symbols AAPL,MSFT` to pick stocks, `--days 10` for fewer days, and
`--trace out.csv` to save every value. In USSwing, **Settings > Indicators > Check**
shows the last 20 values on any stock.

| Message | Fix |
|---|---|
| `"version" is not set` (or another field) | Add the field at the top of the class |
| `"indicator_name" must be capital letters...` | Use a name like `MY_ST` |
| `name "SWING" is already used by a built-in indicator` | Pick another name |
| `name "X" is already used by another of your indicators` | Rename it, or Remove the old one first |
| `calculate() reads parameter "Lookback", but it is not in parameters` | Add it to `parameters`, or fix the label's spelling |
| `two parameters are labelled "Candles"` | Give each option its own label |
| `uses future candles ...` | Remove negative shifts and centred windows |
| `took 3.1 s on AAPL (limit 2 s)` | Use pandas or numpy instead of loops |
| `failed on AAPL: ... (line 31)` | The code raised an error on that line |
| `calculate() returned 120 values, but there are 390 candles` | Return one value per candle of the first timeframe you read |
| `uses testing tools (usswing.dev)...` | Move the chart code to a test or script |
| `no USSwingIndicator class found` / `one indicator per file` | Keep exactly one indicator class in the file |

## 10. Tests and chart (need Python: Settings > Indicators > Set up Python)

```python
from usswing.testing import load_candles, run
from usswing.dev import preview          # in tests or scripts only
from my_st import MySt

candles = load_candles("AAPL", ["3m"], days=5)    # the tool's saved candles, read-only
result = run(MySt, candles, {"Candles": 10})      # missing options use their defaults
print(result.table().tail(20))                    # time, value and debug columns
preview(MySt, candles)                             # opens a chart in the browser
```

| Call | What it does |
|---|---|
| `load_candles(symbol, timeframes=("3m",), days=30, start=None, end=None)` | Saved candles of one stock; `start`/`end` like `"2026-11-02"` |
| `run(indicator_class, candles, values=None)` | Runs it like the tool; gives `.values`, `.debug`, `.main_timeframe`, `.table()` |
| `preview(indicator_class, candles, values=None, path=None)` | Saves and opens an HTML chart |

Run the tests in VS Code with **Testing** (the flask icon) or `python -m pytest`.

## 11. Managing your indicators in USSwing

**Settings > Indicators**: Import (adds a checked file), Export (saves a copy), Remove
(stops the strategies that use it), Reload (reads all files again), Check (last 20
values on a stock), New indicator (open or create a VS Code project), Set up Python,
Help (this guide).
'''

_AI = '''# <<NAME>> - guide for AI helpers

This folder is a custom indicator for the USSwing trading tool. The indicator is
`<<STEM>>.py`. Change that file to do what the user asks, then check it as below.
The full API with examples is in `USSWING_API.md` in this folder; read it first.

## Rules (the tool refuses the file if one is broken)

- One class per file that extends `USSwingIndicator`
  (`from usswing import Input, Number, USSwingIndicator`). pandas and numpy are fine.
- Set all of these on the class:
  - `indicator_name`: 2 to 32 capital letters, numbers or `_`, starting with a letter.
    Keep `<<NAME>>` unless the user asks for another name.
  - `description` and `version`: not empty.
  - `output_type`: `"value"` (a number per candle) or `"signal"` (above 0 = up,
    below 0 = down, 0 = nothing).
- `indicator_name` must not be a built-in name: <<BUILTINS>>.
- `parameters` lists every popup option, in popup order, each label once, using
  `Number(label, default, minimum, maximum, whole_number=...)` and
  `Input(label, options=[...], default=...)`.
- In `calculate()`:
  - Read each option with `self.parameter("Label")`; every label read must be in
    `parameters`.
  - Read candles with `self.candles(symbol_type=..., timeframe=...)`: a pandas DataFrame
    with columns datetime, open, high, low, close, volume, oldest first.
    Timeframes: 3m, 15m, 30m, 1d, 1w.
  - The first timeframe read is the main one. Return one value per main candle.
    NaN is fine while there are not enough candles; infinite values are not.
  - Never use future candles: no negative `shift`, no `rolling(..., center=True)`.
  - Optional: `self.debug_value("Name", series)` for the test table and chart.
  - Finish in under 2 seconds: pandas or numpy, not Python loops over many candles.
- Do not import `usswing.dev` in `<<STEM>>.py`. Use it only in tests or scripts.
- No file or network access and no `sys.exit()` in the indicator.

## Check it (after every change)

Run this in the terminal from this folder (PowerShell):

```
<<CHECK>>
```

A line with ✘ gives a reason; fix it and run the check again until it ends with
"passed on N stock(s)". Exit code 0 means it passed. The fixes for each message are in
`USSWING_API.md` section 9.

## Tests and chart (optional, need the project's Python)

- Keep `test_<<STEM>>.py` passing: `python -m pytest`.
- `usswing.dev.preview(<<CLS>>, candles)` opens a chart (scripts only).
- The usswing library code, if you need details: `<<SDK>>`

## When it passes

Tell the user to add it in USSwing: Settings > Indicators > Import, and pick `<<STEM>>.py`.
'''
