"""
Re-exports CandleBuilder so cross-tool consumers (e.g. EXE) import through
core/ rather than reaching directly into analysis/.
"""
from us_swing.analysis.candle_builder import CandleBuilder

__all__ = ["CandleBuilder"]
