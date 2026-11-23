"""
Module: MD-GUI-046.007.M03 — New indicator project
Parent SRD: SRD-GUI-046.007

Makes a VS Code project folder with an example indicator, a test file, VS Code
settings, the API guide and a guide for AI helpers (SRD-GUI-046.008, .010, .012);
adds missing support files when an old project is opened (SRD-GUI-046.011); opens it
in VS Code (or shows the folder when VS Code is not found).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

from us_swing.core.indicator_plugins import REGISTRY, builtin_names
from us_swing.gui.indicator_guides import AI_FILE, API_FILE, ai_guide, api_guide

_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")
INTERPRETER_KEY = "python.defaultInterpreterPath"
RECOMMENDED_EXTENSIONS = ["ms-python.python", "anthropic.claude-code"]

_INDICATOR = '''"""
{name} - my custom indicator for USSwing.

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
Tests for {name}. They need the project's Python (USSwing: Settings > Indicators >
Set up Python). Run them with the Testing panel in VS Code, or: python -m pytest
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
#
# To see it on a chart in the browser (only in tests or scripts, never in {stem}.py):
#     from usswing.dev import preview
#     preview({cls}, load_candles("AAPL", ["3m"], days=5))
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


def check_command(file_name: str) -> str:
    """The PowerShell command that checks ``file_name`` from its project folder."""
    return "& " + " ".join(f'"{part}"' for part in tool_command()) + \
        f" indicator check {file_name}"


def projects_dir(user_id: int, root: Path | None = None) -> Path:
    return (root or REGISTRY.root) / str(user_id) / "projects"


def python_env_dir(root: Path | None = None) -> Path:
    """The one Python environment shared by all indicator projects (SRD-GUI-046.013)."""
    return (root or REGISTRY.root) / "python"


def env_python(root: Path | None = None) -> Path:
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    name = "python.exe" if sys.platform == "win32" else "python"
    return python_env_dir(root) / scripts / name


def list_projects(user_id: int, root: Path | None = None) -> list[Path]:
    """The user's indicator project folders, by name (SRD-GUI-046.009)."""
    folder = projects_dir(user_id, root)
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name)


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
    folder = projects_dir(user_id, root) / stem
    if folder.exists():
        raise FileExistsError(f"A project called {name} already exists in {folder}")
    folder.mkdir(parents=True)
    cls = _class_name(stem)
    (folder / f"{stem}.py").write_text(_INDICATOR.format(name=name, cls=cls), encoding="utf-8")
    (folder / f"test_{stem}.py").write_text(_TEST.format(name=name, cls=cls, stem=stem),
                                             encoding="utf-8")
    ensure_project_files(folder, root)
    return folder


def ensure_project_files(folder: Path, root: Path | None = None) -> list[str]:
    """Add the guides and VS Code files a project is missing; the user's code is not touched.

    Returns:
        The files that were added or changed, relative to ``folder``.
    """
    stem = folder.name
    name = stem.upper()
    sdk = str(sdk_dir())
    command = tool_command()
    check = check_command(f"{stem}.py")
    vscode = folder / ".vscode"
    vscode.mkdir(parents=True, exist_ok=True)
    wanted: dict[str, str] = {
        ".env": f"PYTHONPATH={sdk}\n",
        AI_FILE: ai_guide(name, stem, _class_name(stem), check, sdk,
                          ", ".join(sorted(builtin_names()))),
        API_FILE: api_guide(check),
        ".vscode/tasks.json": _json({"version": "2.0.0", "tasks": [{
            "label": "Check indicator",
            "type": "process",
            "command": command[0],
            "args": [*command[1:], "indicator", "check", f"${{workspaceFolder}}/{stem}.py"],
            "group": {"kind": "test", "isDefault": True},
            "problemMatcher": [],
        }]}),
        ".vscode/launch.json": _json({"version": "0.2.0", "configurations": [{
            "name": "Run tests",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["-q"],
            "cwd": "${workspaceFolder}",
            "env": {"PYTHONPATH": sdk},
            "console": "integratedTerminal",
        }]}),
        ".vscode/extensions.json": _json({"recommendations": RECOMMENDED_EXTENSIONS}),
    }
    added = [rel for rel, text in wanted.items() if _write_new(folder / rel, text)]
    if _update_settings(folder, root):
        added.append(".vscode/settings.json")
    return added


def point_projects_at_python(root: Path | None = None) -> int:
    """Set every user's projects to use the shared Python; returns how many changed."""
    base = root or REGISTRY.root
    folders = sorted(base.glob("*/projects/*")) if base.is_dir() else []
    return sum(_update_settings(f, root) for f in folders if f.is_dir())


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


def _class_name(stem: str) -> str:
    return "".join(part.capitalize() for part in stem.split("_") if part) or "MyIndicator"


def _update_settings(folder: Path, root: Path | None) -> bool:
    """Write the project's VS Code settings, keeping the user's own keys."""
    path = folder / ".vscode" / "settings.json"
    try:
        settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    before = dict(settings)
    settings.setdefault("python.analysis.extraPaths", [str(sdk_dir())])
    settings.setdefault("python.envFile", "${workspaceFolder}/.env")
    settings.setdefault("python.testing.pytestEnabled", True)
    settings.setdefault("python.testing.pytestArgs", ["."])
    python = env_python(root)
    if python.is_file():
        settings[INTERPRETER_KEY] = str(python)
    if settings == before and path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json(settings), encoding="utf-8")
    return True


def _write_new(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _json(data: object) -> str:
    return json.dumps(data, indent=2) + "\n"
