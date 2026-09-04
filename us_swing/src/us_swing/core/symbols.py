"""
Module: MD-INF-007.001.M03 — core/symbols.py
Parent SRD: SRD-INF-007.006

Vendor symbol notation for class shares.

The project's canonical symbol uses a dot (``BRK.B``). Vendors spell it
differently, so an outbound call converts and everything stored stays dotted.
"""
from __future__ import annotations

__all__ = ["yahoo_symbol"]


def yahoo_symbol(symbol: str) -> str:
    """Return *symbol* in Yahoo Finance notation (BRK.B → BRK-B).

    Yahoo keys class shares with a hyphen. The dotted form resolves to nothing
    and comes back as an empty frame rather than an error, so a caller that
    skips this sees a silent miss instead of a failure.
    """
    return symbol.replace(".", "-")
