"""
Module: MD-GUI-046.007.M03 — New indicator project
Parent SRD: SRD-GUI-046.007

Makes a VS Code project folder with an example indicator, a test file and VS Code
settings, and opens it in VS Code (or shows the folder when VS Code is not found).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

from us_swing.core.indicator_plugins import REGISTRY

_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")

_INDICATOR = '''"""
{name} — my custom indicator for USSwing.

Gives how far the close is from its average over the last N candles.
When it is ready, add it in USSwing: Settings > Indicators > Import.
"""
from usswing import Input, Number, USSwingIndicator


class {cls}(USSwingIndicator):
    """Close minus its average over the last N candles."""

    indicator_name = "{name}"
    description = "Distance of the close from its average over the last N candles"
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
'''

_TEST = '''"""
Tests for {name}. Run them with your own Python 3.11 and pandas: python -m pytest
"""
import numpy as np
import pandas as pd
from usswing.testing import run

from {stem} import {cls}


def made_up_candles(count=100):
    close = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0, 0.5, count)))
    times = pd.date_range("2026-11-02 14:30", periods=count, freq="3min", tz="UTC")
    frame = pd.DataFrame({{"datetime": times, "open": close, "high": close + 0.5,
                          "low": close - 0.5, "close": close, "volume": 1000.0}})
    return {{"3m": frame}}


def test_one_value_per_candle():
    result = run({cls}, made_up_candles())
    assert len(result.values) == 100
    assert result.values.iloc[:19].isna().all()
    assert not result.values.iloc[19:].isna().any()


# To try it on the tool's saved candles:
#     from usswing.testing import load_candles
#     print(run({cls}, load_candles("AAPL", ["3m"], days=5)).table().tail(20))
'''


def sdk_dir() -> Path:
    """Folder that holds the ``usswing`` library files shipped with the tool."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "sdk"
    import usswing

    return Path(usswing.__file__).resolve().parents[1]


def tool_command() -> list[str]:
    """How to start this tool from a VS Code task."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    import us_swing

    return [sys.executable, str(Path(us_swing.__file__).resolve().parents[2] / "run_gui.py")]


def projects_dir(user_id: int, root: Path | None = None) -> Path:
    return (root or REGISTRY.root) / str(user_id) / "projects"


def create_project(user_id: int, name: str, root: Path | None = None) -> Path:
    """Make the project folder for indicator ``name`` and return it.

    Raises:
        ValueError: the name is not capital letters, numbers and ``_``.
        FileExistsError: a project with this name already exists.
    """
    name = name.strip().upper()
    if not _NAME.match(name):
        raise ValueError("Use 2 to 32 capital letters, numbers or _, starting with a "
                         "letter, for example MY_ST")
    stem = name.lower()
    cls = "".join(part.capitalize() for part in stem.split("_") if part) or "MyIndicator"
    folder = projects_dir(user_id, root) / stem
    if folder.exists():
        raise FileExistsError(f"A project called {name} already exists in {folder}")
    vscode = folder / ".vscode"
    vscode.mkdir(parents=True)
    sdk = str(sdk_dir())
    command = tool_command()
    (folder / f"{stem}.py").write_text(_INDICATOR.format(name=name, cls=cls), encoding="utf-8")
    (folder / f"test_{stem}.py").write_text(_TEST.format(name=name, cls=cls, stem=stem),
                                             encoding="utf-8")
    (folder / ".env").write_text(f"PYTHONPATH={sdk}\n", encoding="utf-8")
    _write_json(vscode / "settings.json", {
        "python.analysis.extraPaths": [sdk],
        "python.envFile": "${workspaceFolder}/.env",
        "python.testing.pytestEnabled": True,
        "python.testing.pytestArgs": ["."],
    })
    _write_json(vscode / "tasks.json", {"version": "2.0.0", "tasks": [{
        "label": "Check indicator",
        "type": "process",
        "command": command[0],
        "args": [*command[1:], "indicator", "check", f"${{workspaceFolder}}/{stem}.py"],
        "group": {"kind": "test", "isDefault": True},
        "problemMatcher": [],
    }]})
    _write_json(vscode / "launch.json", {"version": "0.2.0", "configurations": [{
        "name": "Run tests",
        "type": "debugpy",
        "request": "launch",
        "module": "pytest",
        "args": ["-q"],
        "cwd": "${workspaceFolder}",
        "env": {"PYTHONPATH": sdk},
        "console": "integratedTerminal",
    }]})
    return folder


def open_project(folder: Path) -> bool:
    """Open ``folder`` in VS Code; show the folder instead when VS Code is not found.

    Returns:
        True when VS Code was started.
    """
    code = shutil.which("code")
    if code is not None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([code, str(folder)], creationflags=flags)  # noqa: S603
        return True
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    return False


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
