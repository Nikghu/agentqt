"""Helpers for the P5c news tests: small RSS texts and a fake getter (no network)."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape

# (title, link, published or None)
Item = tuple[str, str, datetime | None]


def rss(items: Sequence[Item]) -> str:
    """RSS text with one ``item`` per entry; a ``None`` time leaves out the pubDate."""
    parts = []
    for title, link, when in items:
        stamp = f"<pubDate>{format_datetime(when)}</pubDate>" if when else ""
        parts.append(f"<item><title>{escape(title)}</title><link>{escape(link)}</link>"
                     f"{stamp}</item>")
    return ('<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>'
            + "".join(parts) + "</channel></rss>")


def getter(stock: Mapping[str, str] | None = None, market: Mapping[str, str] | None = None,
           fail_stock: Sequence[str] = (), fail_all: bool = False,
           fail_market: Sequence[str] = ()) -> Callable[[str], str]:
    """A getter keyed by stock symbol (``s=SYM&``) or by market feed URL fragment."""
    stock = stock or {}
    market = market or {}

    def get(url: str) -> str:
        if fail_all:
            raise OSError("network down")
        if "headline?s=" in url:
            symbol = url.split("headline?s=")[1].split("&")[0]
            if symbol in fail_stock:
                raise OSError("feed failed")
            return stock.get(symbol) or market.get(symbol) or rss([])
        for part in fail_market:
            if part in url:
                raise OSError("feed failed")
        for part, text in market.items():
            if part in url:
                return text
        return rss([])

    return get
