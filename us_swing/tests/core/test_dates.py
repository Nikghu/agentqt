"""Tests for MD-GUI-031.083.M14 — core/dates.py."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from us_swing.core.dates import show_date


def test_show_date_day_first() -> None:
    """UT-GUI-031.083.M14.T01: Dates show as DD-MM-YYYY for date, datetime and Timestamp."""
    assert show_date(date(2026, 3, 4)) == "04-03-2026"
    assert show_date(datetime(2026, 11, 2, 9, 30)) == "02-11-2026"
    assert show_date(pd.Timestamp("2025-12-31 16:00", tz="America/New_York")) == "31-12-2025"
