"""
Module: MD-GUI-031.083.M14 — core/dates.py
Parent SRD: SRD-GUI-031.083

One date format for every date shown to the user (DD-MM-YYYY). Stored data,
cache keys and file names keep ISO dates.
"""
from __future__ import annotations

from datetime import date

DATE_FMT = "%d-%m-%Y"
DATE_TIME_FMT = "%d-%m-%Y %H:%M"
QT_DATE_FMT = "dd-MM-yyyy"


def show_date(day: date) -> str:
    """``day`` as DD-MM-YYYY; a datetime or pandas Timestamp shows its date part."""
    return day.strftime(DATE_FMT)
