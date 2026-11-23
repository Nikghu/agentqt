"""
Module: MD-GUI-046.007.M03 — indicator project guides
Parent SRD: SRD-GUI-046.008, SRD-GUI-046.010

The USSwing indicator API reference (one text source: USSWING_API.md for AI helpers,
turned into USSWING_API.html for people) and the guide for AI helpers (CLAUDE.md).
"""
from __future__ import annotations

API_FILE = "USSWING_API.md"
API_HTML_FILE = "USSWING_API.html"
AI_FILE = "CLAUDE.md"


def api_guide(check: str) -> str:
    """The USSwing indicator API reference; ``check`` is the check command for this PC."""
    return _API.replace("<<CHECK>>", check)


def ai_guide(name: str, stem: str, cls: str, check: str, sdk: str, builtins: str) -> str:
    """The guide an AI helper in VS Code reads before changing the indicator."""
    return (_AI.replace("<<NAME>>", name).replace("<<STEM>>", stem).replace("<<CLS>>", cls)
            .replace("<<CHECK>>", check).replace("<<SDK>>", sdk)
            .replace("<<BUILTINS>>", builtins))


_API = '''# USSwing Indicator API

Write your own indicator in Python, check it, and use it in a strategy's trigger
condition like a built-in indicator.

## 1. Getting started

### What you need

| Tool | Needed for | How to get it |
|---|---|---|
| VS Code | Editing the indicator file | code.visualstudio.com |
| Claude Code | Optional: AI writes the indicator for you | VS Code > Extensions > search "Claude Code" |
| Python | Optional: only tests and the chart | USSwing > Settings > Indicators > Set up Python |

Writing and checking an indicator needs no Python. USSwing checks it for you.

### Your first indicator in 10 minutes

1. In USSwing open **Settings > Indicators > New indicator**, type a name such as `MY_ST`
   and press **Create**. VS Code opens the project.
2. Open `my_st.py`. It holds a working example. Change it, or ask Claude Code:
   *"Make a signal when the 3m close crosses above its 20 candle average."*
3. Check it: in VS Code **Terminal > Run Task > Check indicator**, or run the command
   in [Checking an indicator](#7-checking-an-indicator).
4. Fix each line that starts with ✘ and check again until it says `passed on N stock(s)`.
5. In USSwing open **Settings > Indicators > Import** and pick the file.
6. In a strategy, open the trigger condition popup: your indicator is at the end of the list.

## 2. The indicator file

A full working indicator. One file holds one indicator class.

```python
from usswing import Input, Number, USSwingIndicator


class MySt(USSwingIndicator):
    indicator_name = "MY_ST"
    description = "Distance of the close from its average"
    version = "1.0"
    output_type = "value"

    parameters = [
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
        self.debug_value("Average", average)
        return candles["close"] - average
```

In a strategy condition it is written with its options in order, text in single quotes:

```text
MY_ST('Spot', 20, '3m') > 0
```

## 3. Indicator class

### class USSwingIndicator

```python
from usswing import USSwingIndicator

class MySt(USSwingIndicator):
    ...
```

Base class of every indicator. Set these class fields:

| Field | Type | Meaning | Rule |
|---|---|---|---|
| `indicator_name` | str | Name in the popup and in conditions | 2 to 32 capital letters, numbers or `_`, starting with a letter; not a built-in name (SWING, VWAP, EMA, RSI, MACD, ADX, SUPERTREND, BOSS_ST, Price, Number, PNL) |
| `description` | str | One line shown to you | Not empty |
| `version` | str | Your own version, e.g. `"1.0"` | Not empty |
| `output_type` | str | `"value"`: a number per candle. `"signal"`: above 0 = up, below 0 = down, 0 = nothing | `"value"` or `"signal"` |
| `parameters` | list | The options in the popup, in order | `Number` and `Input` items, each label once |

### calculate(self)

```python
def calculate(self):
    candles = self.candles(symbol_type="Spot", timeframe="3m")
    return candles["close"].rolling(20).mean()
```

The method you write. It must return **one value per candle** of the first timeframe it
reads (the *main* timeframe).

| Returns | |
|---|---|
| pandas Series, list or numpy array | Same length as the main candles. Numbers or True/False. NaN (empty) is fine while there are not enough candles; infinite values are not |

## 4. Popup options

### Number(label, default, minimum, maximum, whole_number=False)

```python
Number("Candles", default=20, minimum=1, maximum=500, whole_number=True)
```

A number box in the popup that stays between `minimum` and `maximum`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `label` | str | required | Text in the popup; read it with `self.parameter(label)` |
| `default` | number | required | Value the popup starts with |
| `minimum` | number | required | Lowest allowed value |
| `maximum` | number | required | Highest allowed value |
| `whole_number` | bool | `False` | `True` for counts such as candles; values are then whole numbers |

### Input(label, options, default)

```python
Input("Price Swing", options=["High", "Low", "Range"], default="High")
```

A dropdown in the popup.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `label` | str | required | Text in the popup; read it with `self.parameter(label)` |
| `options` | list of str | required | The choices, in the order shown; no repeats |
| `default` | str | required | The choice the popup starts with; must be one of `options` |

## 5. Inside calculate()

### self.candles(symbol_type, timeframe)

```python
candles = self.candles(symbol_type="Spot", timeframe="15m")
closes = candles["close"]
```

The stock's closed candles, oldest first. The first timeframe you read is the main one.

| Parameter | Type | Meaning |
|---|---|---|
| `symbol_type` | str | `"Spot"` or `"RSP"`. RSP gives the stock's own candles for now, like built-in indicators |
| `timeframe` | str | `"3m"`, `"15m"`, `"30m"`, `"1d"` or `"1w"` |

| Returns | |
|---|---|
| pandas DataFrame | Columns `datetime` (when the candle opened), `open`, `high`, `low`, `close`, `volume`. A copy: changing it is safe |

### self.parameter(label)

```python
count = self.parameter("Candles")      # 20, or what the user chose
```

The value the user chose for an option: a number for `Number`, a text for `Input`.
An unknown label raises an error: `Unknown parameter 'Lookback'`.

### self.debug_value(name, series)

```python
self.debug_value("Average", average)
```

Keeps an extra series to look at in Check, the test table and the chart. It has no effect
on trading. The series needs one value per main candle, like the result.

## 6. Testing kit

Needs Python (USSwing > Settings > Indicators > Set up Python). Use these in tests and
scripts, not in the indicator file.

### usswing.testing.load_candles(symbol, timeframes=("3m",), days=30, start=None, end=None)

```python
from usswing.testing import load_candles

candles = load_candles("AAPL", ["3m", "15m"], days=5)
candles["3m"].tail()
```

Reads the candles USSwing has saved. The file is opened read-only.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `symbol` | str | required | Stock symbol, e.g. `"AAPL"` |
| `timeframes` | list of str | `["3m"]` | Any of 3m, 15m, 30m, 1d, 1w; the first sets the market days |
| `days` | int | `30` | Keep the last this many market days |
| `start`, `end` | str | `None` | Day range like `"2026-11-02"`, used instead of `days` |

| Returns | |
|---|---|
| dict | `{timeframe: DataFrame}` in the same shape as `self.candles()` |

### usswing.testing.run(indicator_class, candles, values=None)

```python
from usswing.testing import load_candles, run
from my_st import MySt

result = run(MySt, load_candles("AAPL", ["3m"], days=5), {"Candles": 10})
print(result.table().tail(20))
```

Runs the indicator the same way USSwing does. Options left out use their defaults.

| Returns: Result | |
|---|---|
| `.values` | pandas Series: one value per main candle |
| `.debug` | dict of the `debug_value` series |
| `.main_timeframe` | str, e.g. `"3m"` |
| `.table()` | DataFrame with `time`, `value` and one column per debug series |

### usswing.dev.preview(indicator_class, candles, values=None, path=None)

```python
from usswing.dev import preview
from usswing.testing import load_candles
from my_st import MySt

preview(MySt, load_candles("AAPL", ["3m"], days=5))
```

Saves one HTML chart and opens it in the browser: candles on top, the indicator and its
debug lines below; a signal indicator shows up and down arrows on the candles.
Never import `usswing.dev` in the indicator file itself; the check refuses it.

## 7. Checking an indicator

```powershell
<<CHECK>>
```

Run it in the project folder after every change, or use VS Code **Terminal > Run Task >
Check indicator**. It runs the same check as Import on the stocks you saved.

| Option | Example | Meaning |
|---|---|---|
| `--symbols` | `--symbols AAPL,MSFT` | Stocks to run on (default: 3 stocks with the most 3m candles) |
| `--days` | `--days 10` | Market days of candles (default 30) |
| `--trace` | `--trace out.csv` | Save every value and debug value as CSV |

Exit code 0 means it passed, 1 means refused. In USSwing, **Settings > Indicators > Check**
shows the last 20 values on any stock.

### Rules the check enforces

- **No future candles.** A value must not change when newer candles arrive: no negative
  `shift`, no `rolling(..., center=True)`.
- **Fast.** Under 2 seconds. Use pandas or numpy, not Python loops over many candles.
- **No `usswing.dev`** in the indicator file.
- No file or network access and no `sys.exit()`.
- When live, 3 failures in a row on a stock stop the strategies that use it, and you get an
  alert. A strategy whose indicator is missing does not start.

### Messages and fixes

| Message | Fix |
|---|---|
| `"version" is not set` (or another field) | Add the field at the top of the class |
| `"indicator_name" must be capital letters...` | Use a name like `MY_ST` |
| `name "SWING" is already used by a built-in indicator` | Pick another name |
| `name "X" is already used by another of your indicators` | Rename it, or Remove the old one first |
| `calculate() reads parameter "Lookback", but it is not in parameters` | Add it to `parameters`, or fix the spelling |
| `two parameters are labelled "Candles"` | Give each option its own label |
| `uses future candles ...` | Remove negative shifts and centred windows |
| `took 3.1 s on AAPL (limit 2 s)` | Use pandas or numpy instead of loops |
| `failed on AAPL: ... (line 31)` | The code raised an error on that line |
| `calculate() returned 120 values, but there are 390 candles` | Return one value per candle of the first timeframe you read |
| `uses testing tools (usswing.dev)...` | Move the chart code to a test or script |
| `no USSwingIndicator class found` / `one indicator per file` | Keep exactly one indicator class in the file |

## 8. Recipes

Paste a recipe into `calculate()`. Each one passes the check.

### Moving average distance (value)

```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
return c["close"] - c["close"].rolling(self.parameter("Candles")).mean()
```

### Close crosses its average (signal)

```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
above = (c["close"] > c["close"].rolling(self.parameter("Candles")).mean()).astype(int)
return above.diff().fillna(0)        # 1 = crossed up, -1 = crossed down, 0 = no cross
```

### Two timeframes: 3m close above the 15m average (value 1 or 0)

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

`datetime` is when a candle opens. Lining up by close time means each 3m candle only sees
15m candles that had already closed, so no future candles are used.

### Swing high of the last N closed candles (value)

```python
c = self.candles(symbol_type="Spot", timeframe=self.parameter("Timeframe"))
return c["high"].shift(1).rolling(self.parameter("Candles")).max()
```

## 9. Using it in USSwing

| Button in Settings > Indicators | What it does |
|---|---|
| Import | Checks a file and adds it |
| Export | Saves a copy of the file |
| Remove | Deletes it; strategies that use it are stopped first |
| Reload | Reads all your indicator files again |
| Check | Shows the last 20 values on a stock you pick |
| New indicator | Opens one of your projects or creates a new one in VS Code |
| Set up Python | Makes the Python that tests and the chart need |
| Help | Opens this guide |
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
`USSWING_API.md` section 7, "Messages and fixes".

## Tests and chart (optional, need the project's Python)

- Keep `test_<<STEM>>.py` passing: `python -m pytest`.
- `usswing.dev.preview(<<CLS>>, candles)` opens a chart (scripts only).
- The usswing library code, if you need details: `<<SDK>>`

## When it passes

Tell the user to add it in USSwing: Settings > Indicators > Import, and pick `<<STEM>>.py`.
'''
