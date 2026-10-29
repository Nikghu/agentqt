"""
Launcher: python us_swing/run_gui.py
Adds the src directory to sys.path and starts the GUI.
Run from the workspace root: f:\\USMarket_Backtesting
"""
from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

# Ensure the us_swing package is importable
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Before pandas / keyring load: no console window flash on Windows (SRD-GUI-000.007).
from us_swing.gui.quiet_platform import install as _quiet_platform  # noqa: E402

_quiet_platform()

from us_swing.__main__ import main  # noqa: E402

if __name__ == "__main__":
    # Backtest worker processes start from this file in the frozen app.
    multiprocessing.freeze_support()
    main()
