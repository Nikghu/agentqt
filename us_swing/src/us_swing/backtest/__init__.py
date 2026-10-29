"""Backtest tool (BKT) — historical candle store and downloader for backtesting."""
from __future__ import annotations

from pathlib import Path

DEFAULT_ROOT: Path = Path.home() / ".usswing" / "backtest"
