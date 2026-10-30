"""
Module: MD-MCP-007.001.M01 — Backtest MCP tools
Parent SRD: SRD-MCP-007.001

``python -m us_swing.mcp`` runs the backtest MCP server over stdio.
"""
from __future__ import annotations

import logging
import sys


def main() -> None:
    """Log to stderr (stdout carries the MCP messages), then serve over stdio."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from us_swing.mcp.backtest_tools import build_server, default_tools  # noqa: PLC0415

    build_server(default_tools()).run(transport="stdio")


if __name__ == "__main__":
    main()
