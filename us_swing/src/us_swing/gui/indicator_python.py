"""
Module: MD-GUI-046.013.M04 — Python for indicator projects
Parent SRD: SRD-GUI-046.013

Makes one Python environment, shared by all indicator projects, with pandas, numpy
and pytest, from the Python already installed on the PC, and points every project's
VS Code settings at it. Only the test file and the chart preview need it.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from us_swing.gui.indicator_project import env_python, point_projects_at_python, python_env_dir

PACKAGES = ("pandas", "numpy", "pytest")
DOWNLOAD_URL = "https://www.python.org/downloads/"
MIN_VERSION = (3, 10)

Runner = Callable[[list[str], float], tuple[int, str]]


class PythonSetupError(RuntimeError):
    """The Python environment could not be made; the message tells the user what to do."""


def run_command(args: list[str], timeout: float) -> tuple[int, str]:
    """Run a program without a console window; returns its exit code and output."""
    try:
        done = subprocess.run(  # noqa: S603
            args, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return 1, f"did not finish in {timeout:g} s"
    except OSError as exc:
        return 1, str(exc)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def find_base_python(run: Runner = run_command) -> list[str] | None:
    """A Python 3.10 or newer installed on this PC, as a command; None when there is none."""
    candidates: list[list[str]] = []
    if shutil.which("py"):
        candidates += [["py", "-3.11"], ["py", "-3.12"], ["py", "-3"]]
    for name in ("python", "python3"):
        path = shutil.which(name)
        if path and "WindowsApps" not in path:
            candidates.append([path])
    probe = "import sys; print(sys.version_info[0] * 100 + sys.version_info[1])"
    for command in candidates:
        code, out = run([*command, "-c", probe], 30)
        version = out.strip().splitlines()[-1] if out.strip() else ""
        if code == 0 and version.isdigit() and int(version) >= MIN_VERSION[0] * 100 + \
                MIN_VERSION[1]:
            return command
    return None


def python_ready(root: Path | None = None) -> bool:
    return env_python(root).is_file()


def setup_python(root: Path | None = None, run: Runner = run_command,
                 step: Callable[[str], None] = lambda _text: None) -> Path:
    """Make (or repair) the shared environment and point the projects at it.

    Returns:
        The environment's python.exe.

    Raises:
        PythonSetupError: no Python found, or a step failed.
    """
    base = find_base_python(run)
    if base is None:
        raise PythonSetupError(
            f"Python 3.10 or newer was not found on this PC. Install it from {DOWNLOAD_URL} "
            "(tick \"Add python.exe to PATH\"), then press Set up again")
    step("Making the Python environment")
    code, out = run([*base, "-m", "venv", str(python_env_dir(root))], 300)
    if code != 0:
        raise PythonSetupError(f"Could not make the Python environment: {_last_line(out)}")
    python = env_python(root)
    step("Installing pandas, numpy and pytest (about a minute; needs internet)")
    code, out = run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                     *PACKAGES], 1200)
    if code != 0:
        raise PythonSetupError("Could not install pandas, numpy and pytest; check the "
                               f"internet connection: {_last_line(out)}")
    step("Pointing your indicator projects at it")
    point_projects_at_python(root)
    return python


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "no details"
