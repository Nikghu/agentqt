"""Tests for MD-EXE-022.005.M02 — core/indicator_plugins/_check.py."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.execution.plugin_helpers import SWING_PLUS, frames, swing_plus_source, write_plugin
from us_swing.core.indicator_plugins import _check as check_module
from us_swing.core.indicator_plugins import check_file
from us_swing.core.indicator_plugins._check import DEV_REASON, FUTURE_REASON


def _probe() -> list[tuple[str, dict]]:
    return [("AAA", frames(120, 1)), ("BBB", frames(120, 2)), ("CCC", frames(120, 3))]


def _check(path: Path, **kwargs: object) -> tuple[bool, list[str]]:
    report = check_file(path, **kwargs)  # type: ignore[arg-type]
    return report.ok, list(report.reasons)


def test_swing_example_passes() -> None:
    """UT-EXE-022.005.M02.T01: The SWING_PLUS example passes, with its 5 parameters in order."""
    report = check_file(SWING_PLUS, builtin_names={"SWING", "EMA"}, candle_probe=_probe)

    assert report.ok, report.reasons
    assert report.spec is not None
    assert report.spec.name == "SWING_PLUS"
    assert [p.label for p in report.spec.parameters] == [
        "Symbol Type", "Candles", "Price Swing", "Window", "Timeframe"]


def test_no_class_or_two_classes(tmp_path: Path) -> None:
    """UT-EXE-022.005.M02.T02: A file needs exactly one USSwingIndicator class."""
    none = write_plugin(tmp_path, "none.py", "x = 1\n")
    two = write_plugin(tmp_path, "two.py", swing_plus_source() + (
        "\n\nclass Other(SwingPlus):\n    indicator_name = \"OTHER\"\n"))

    assert _check(none) == (False, ["no USSwingIndicator class found"])
    assert _check(two) == (False, ["one indicator per file — found SwingPlus, Other"])


def test_missing_field_gives_hint(tmp_path: Path) -> None:
    """UT-EXE-022.005.M02.T03: A field set under a near name gets a "did you mean" hint."""
    path = write_plugin(tmp_path, "named.py", swing_plus_source(
        ('indicator_name = "SWING_PLUS"', 'name = "SWING_PLUS"')))

    ok, reasons = _check(path)

    assert not ok
    assert reasons == ['"indicator_name" is not set (found "name" — did you mean '
                       '"indicator_name"?)']


def test_duplicate_label_or_taken_name(tmp_path: Path) -> None:
    """UT-EXE-022.005.M02.T04: Repeated labels, built-in names and the user's own names."""
    twice = write_plugin(tmp_path, "twice.py", swing_plus_source(
        ('Input("Window"', 'Input("Candles"')))
    builtin = write_plugin(tmp_path, "ema.py", swing_plus_source(
        ('indicator_name = "SWING_PLUS"', 'indicator_name = "EMA"')))

    assert 'two parameters are labelled "Candles"' in _check(twice)[1]
    assert _check(builtin, builtin_names={"EMA"})[1] == [
        'name "EMA" is already used by a built-in indicator']
    assert _check(SWING_PLUS, taken_names={"swing_plus"})[1] == [
        'name "SWING_PLUS" is already used by another of your indicators']


def test_dev_import_refused(tmp_path: Path) -> None:
    """UT-EXE-022.005.M02.T05: A file that imports usswing.dev is refused."""
    path = write_plugin(tmp_path, "dev.py", swing_plus_source(
        ("from usswing import", "from usswing.dev import preview\nfrom usswing import")))

    ok, reasons = _check(path)

    assert not ok and reasons[0] == DEV_REASON


def test_file_fails_to_load(tmp_path: Path) -> None:
    """UT-EXE-022.005.M02.T06: A syntax error is refused with its message and line."""
    lines = ["from usswing import USSwingIndicator", "", "", "", "", "",
             "class Broken(USSwingIndicator)", "    pass"]
    path = write_plugin(tmp_path, "broken.py", "\n".join(lines) + "\n")

    ok, reasons = _check(path)

    assert not ok
    assert len(reasons) == 1 and reasons[0].startswith("syntax error on line 7")


def test_reads_undeclared_label(tmp_path: Path) -> None:
    """UT-EXE-022.006.M02.T01: Reading a label that is not declared is refused by name."""
    path = write_plugin(tmp_path, "label.py", swing_plus_source(
        ('self.parameter("Candles")', 'self.parameter("Lookback")')))

    assert _check(path) == (False, [
        'calculate() reads parameter "Lookback", but it is not in parameters'])


def test_declared_labels_pass() -> None:
    """UT-EXE-022.006.M02.T02: Every label SWING_PLUS reads is declared."""
    assert _check(SWING_PLUS) == (True, [])


def test_dry_run_error(tmp_path: Path) -> None:
    """UT-EXE-022.007.M02.T01: An error in calculate() names the stock, the error and the line."""
    path = write_plugin(tmp_path, "zero.py", swing_plus_source(
        ('count = self.parameter("Candles")', 'count = self.parameter("Candles") / 0')))

    ok, reasons = _check(path, candle_probe=_probe)

    assert not ok
    assert reasons[0].startswith("failed on AAA: division by zero (line ")


def test_dry_run_too_slow() -> None:
    """UT-EXE-022.007.M02.T02: A stock that takes more than 2 s is refused."""
    times: Iterator[float] = iter([0.0, 3.4])

    ok, reasons = _check(SWING_PLUS, candle_probe=_probe, clock=lambda: next(times))

    assert (ok, reasons) == (False, ["took 3.4 s on AAA (limit 2 s)"])


def test_uses_future_candles(tmp_path: Path) -> None:
    """UT-EXE-022.007.M02.T03: Values that change when newer candles arrive are refused."""
    path = write_plugin(tmp_path, "future.py", swing_plus_source(
        ("swing_high = highs.rolling(count).max()", 'swing_high = candles["close"].shift(-1)')))

    assert _check(path, candle_probe=_probe) == (False, [FUTURE_REASON])


def test_empty_values_at_start_are_fine() -> None:
    """UT-EXE-022.007.M02.T04: NaN for the first candles (not enough history) is allowed."""
    report = check_file(SWING_PLUS, candle_probe=lambda: [("AAA", frames(25, 1))])

    assert report.ok, report.reasons


def test_dry_run_passes_on_three_stocks() -> None:
    """UT-EXE-022.007.M02.T05: The dry run covers 3 stocks, each inside the time limit."""
    seen: list[int] = []

    def probe() -> list[tuple[str, dict]]:
        stocks = _probe()
        seen.append(len(stocks))
        return stocks

    ok, reasons = _check(SWING_PLUS, candle_probe=probe)

    assert (ok, reasons) == (True, [])
    assert seen == [3]


def test_hang_while_loading_or_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-022.007.M02.T02 (review fix): Code that never finishes is cut off, not waited for."""
    monkeypatch.setattr(check_module, "LOAD_LIMIT_S", 0.2)
    monkeypatch.setattr(check_module, "TIME_LIMIT_S", 0.2)
    load = write_plugin(tmp_path, "load.py", "import time\ntime.sleep(3)\n")
    run = write_plugin(tmp_path, "run.py", swing_plus_source(
        ('count = self.parameter("Candles")',
         'count = self.parameter("Candles")\n        __import__("time").sleep(3)')))

    assert _check(load) == (False, ["did not finish loading in 0.2 s"])
    assert _check(run, candle_probe=_probe) == (False, ["did not finish in 0.2 s on AAA"])


def test_sys_exit_in_calculate(tmp_path: Path) -> None:
    """UT-EXE-022.007.M02.T01 (review fix): sys.exit() in calculate() is a reason, not an exit."""
    path = write_plugin(tmp_path, "exit.py", swing_plus_source(
        ('count = self.parameter("Candles")', 'count = __import__("sys").exit(1)')))

    assert _check(path, candle_probe=_probe) == (False, ["failed on AAA: called sys.exit()"])


def test_fails_with_fewer_candles(tmp_path: Path) -> None:
    """UT-EXE-022.007.M02.T03 (review fix): An indicator that breaks on fewer candles is refused."""
    path = write_plugin(tmp_path, "fewer.py", swing_plus_source(
        ('count = self.parameter("Candles")',
         'count = self.parameter("Candles")\n'
         '        if len(candles) < 120:\n            raise ValueError("need 120 candles")')))

    ok, reasons = _check(path, candle_probe=_probe)

    assert not ok and reasons[0].startswith("fails with fewer candles: need 120 candles")


def test_no_candle_data_loads_with_note() -> None:
    """UT-EXE-022.007.M02.T04 (review fix): With no candle data the file loads with a note."""
    report = check_file(SWING_PLUS, candle_probe=lambda: [])

    assert report.ok and report.notes == (check_module.NOT_CHECKED_NOTE,)


def test_changed_file_runs_new_code(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T02 (review fix): A file changed in the same second loads its new code."""
    path = write_plugin(tmp_path, "same.py", swing_plus_source())
    first = check_file(path)
    path.write_text(swing_plus_source(('version = "1.0"', 'version = "2.0"')), encoding="utf-8")
    second = check_file(path)

    assert first.spec is not None and second.spec is not None
    assert (first.spec.version, second.spec.version) == ("1.0", "2.0")


@pytest.mark.parametrize("field", ["description", "version"])
def test_empty_text_field(tmp_path: Path, field: str) -> None:
    """UT-EXE-022.005.M02.T03 (part): Empty description or version is refused."""
    old = {"description": 'description = "Swing high, swing low or swing range over the last '
                          'N candles"',
           "version": 'version = "1.0"'}[field]
    path = write_plugin(tmp_path, f"{field}.py", swing_plus_source((old, f'{field} = ""')))

    assert _check(path) == (False, [f'"{field}" must not be empty'])
