"""
Module: MD-INF-007.001.M03 — tests/core/test_symbols.py
Parent SRD: SRD-INF-007.006

Vendor symbol notation for class shares (ISS-INF-0003).
"""
from __future__ import annotations

import pytest

from us_swing.core.symbols import yahoo_symbol


@pytest.mark.parametrize(
    ("canonical", "expected"),
    [
        ("BRK.B", "BRK-B"),
        ("BF.B", "BF-B"),
        ("AAPL", "AAPL"),
        ("", ""),
    ],
)
def test_yahoo_symbol_conversion(canonical: str, expected: str) -> None:
    """UT-INF-007.001.M03.T01: Dots become hyphens, everything else is unchanged."""
    assert yahoo_symbol(canonical) == expected


def test_yahoo_symbol_is_idempotent() -> None:
    """UT-INF-007.001.M03.T02: Converting an already-converted symbol is a no-op."""
    assert yahoo_symbol(yahoo_symbol("BRK.B")) == "BRK-B"


# ---------------------------------------------------------------------------
# Every Yahoo call site applies the conversion (ISS-INF-0003)
# ---------------------------------------------------------------------------


def test_watchlist_quote_worker_uses_vendor_symbol(qapp) -> None:
    """UT-INF-007.001.M03.T03: Market-watch quotes look up BRK.B as BRK-B.

    The emitted row must still carry the dotted symbol so the GUI matches it
    against the watchlist.
    """
    from unittest.mock import MagicMock, patch

    from us_swing.gui.app_service import _WatchlistQuoteWorker

    ticker_cls = MagicMock()
    ticker_cls.return_value.fast_info = MagicMock(last_price=1.0, previous_close=1.0)

    worker = _WatchlistQuoteWorker(["BRK.B"])
    captured: list[list[dict]] = []
    worker.done.connect(captured.append)

    with patch("yfinance.Ticker", ticker_cls):
        worker.run()

    ticker_cls.assert_called_once_with("BRK-B")
    assert captured and captured[0][0]["symbol"] == "BRK.B"


def test_market_cap_fetch_uses_vendor_symbol() -> None:
    """UT-INF-007.001.M03.T04: Universe market caps look up BRK.B as BRK-B.

    The returned mapping stays keyed on the dotted symbol.
    """
    from unittest.mock import MagicMock, patch

    from us_swing.universe.store import _fetch_market_caps

    ticker_cls = MagicMock()
    ticker_cls.return_value.fast_info.market_cap = 1_000.0

    with patch("yfinance.Ticker", ticker_cls):
        caps = _fetch_market_caps(["BRK.B"])

    ticker_cls.assert_called_once_with("BRK-B")
    assert caps == {"BRK.B": 1_000.0}


def test_live_bar_poll_uses_vendor_symbol(tmp_path) -> None:
    """UT-INF-007.001.M03.T05: The live batch download sends and reads BRK-B.

    The frame is keyed by the symbols as sent, so a dotted lookup against a
    hyphen-keyed frame would silently skip the stock.
    """
    from unittest.mock import MagicMock, patch

    import pandas as pd

    from us_swing.execution.live_bar_worker import LiveBarWorker

    frame = pd.DataFrame(
        {("BRK-B", "Open"): [], ("BRK-B", "High"): [],
         ("BRK-B", "Low"): [], ("BRK-B", "Close"): [], ("BRK-B", "Volume"): []}
    )
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)

    worker = LiveBarWorker(
        symbols=["BRK.B", "AAPL"],
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        ibkr_client_id=99,
        db_path=str(tmp_path / "candles.db"),
    )

    download = MagicMock(return_value=frame)
    with patch("yfinance.download", download):
        worker._poll_yfinance_once()

    assert download.call_count == 2  # one per timeframe
    for call in download.call_args_list:
        assert call.args[0] == ["BRK-B", "AAPL"]
