"""
Launcher: python us_swing/run_gui.py
Adds the src directory to sys.path and starts the GUI.
Run from the workspace root: f:\\USMarket_Backtesting
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the us_swing package is importable
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from us_swing.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
