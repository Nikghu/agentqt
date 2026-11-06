"""
Module: MD-MKT-007.003.M01 — core/report_html.py
Parent SRD: SRD-MKT-007.003

The allow-list cleaner for AI report pages and the sealed page shell. The cleaned page
is rebuilt from scratch: only listed tags and attributes are written, and anything that
could load a script, a link, an outside or local file is left out. ``market`` uses it
before a page is stored and the GUI uses it again before a page is shown.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

MAX_PAGE_BYTES = 200_000

_TEXT_TAGS = frozenset(
    "div span p br hr h1 h2 h3 h4 h5 h6 strong b em i u small sub sup ul ol li dl dt dd "
    "table thead tbody tfoot tr th td caption colgroup col section article header footer "
    "figure figcaption blockquote pre code img style".split())
_SVG_TAGS = frozenset(
    "svg g rect line polyline polygon circle ellipse path text tspan title".split())
_ALLOWED_TAGS = _TEXT_TAGS | _SVG_TAGS
_DROP_WITH_CONTENT = frozenset(
    "script iframe object embed frame frameset noscript template applet link meta base form "
    "input button select textarea audio video source canvas math foreignobject".split())
_VOID_TAGS = frozenset("br hr img col".split())
_DROP_VOID = frozenset("input link meta base source embed frame".split())
_GLOBAL_ATTRS = frozenset("class style title colspan rowspan align width height".split())
_IMG_ATTRS = frozenset({"src", "alt"})
_SVG_ATTRS = frozenset(
    "viewbox x y x1 y1 x2 y2 cx cy r rx ry d points fill stroke stroke-width opacity "
    "fill-opacity stroke-dasharray transform text-anchor font-size font-family font-weight "
    "dominant-baseline preserveaspectratio".split())
_SVG_CASE = {"viewbox": "viewBox", "preserveaspectratio": "preserveAspectRatio"}
_DATA_IMAGE = re.compile(r"^data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+$")
_CSS_BAD = re.compile(
    r"@import[^;]*;?|@font-face|"
    r"(?:-[a-z]+-)?(?:url|image-set|image|src|cross-fade|element|expression|local)\s*\([^)]*\)?|"
    r"behavior\s*:[^;}]*|-moz-binding\s*:[^;}]*|javascript\s*:[^;}]*",
    re.IGNORECASE)
_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


@dataclass(frozen=True)
class CleanPage:
    """A cleaned page body and how many tags, attributes and CSS parts were taken out."""

    html: str
    removed: int


def clean_css(css: str) -> tuple[str, int]:
    """Remove imports, loading functions (``url()``, ``image-set()`` ...), expressions,
    CSS escapes and every ``<``; repeat until nothing changes, so no removal can build
    a new ``url(``.
    """
    count = css.count("<") + css.count("\\")
    cleaned = css.replace("<", "").replace("\\", "")
    while True:
        cleaned, found = _CSS_BAD.subn("", cleaned)
        if not found:
            return cleaned, count
        count += found


def _first_src(attrs: list[tuple[str, str | None]]) -> str:
    return next((v or "" for k, v in attrs if k.lower() == "src"), "")


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.removed = 0
        self._open: list[str] = []
        self._skip: list[str] = []

    def _attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        allowed = _GLOBAL_ATTRS | (_IMG_ATTRS if tag == "img" else frozenset())
        allowed |= _SVG_ATTRS if tag in _SVG_TAGS else frozenset()
        parts: list[str] = []
        seen: set[str] = set()
        for name, value in attrs:
            name = name.lower()
            text = value or ""
            if name not in allowed or name in seen or "javascript:" in text.lower().replace(" ", ""):
                self.removed += 1
                continue
            seen.add(name)
            if name != "src":
                text, count = clean_css(text)
                self.removed += count
            parts.append(f' {_SVG_CASE.get(name, name)}="{html.escape(text, quote=True)}"')
        return "".join(parts)

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], closed: bool) -> None:
        if self._skip:
            if tag == self._skip[-1] and not closed:
                self._skip.append(tag)
            return
        if tag in _DROP_WITH_CONTENT:
            self.removed += 1
            if not closed and tag not in _DROP_VOID:
                self._skip.append(tag)
            return
        if tag not in _ALLOWED_TAGS:
            self.removed += 1
            return
        if tag == "style" and closed or tag == "img" and not _DATA_IMAGE.match(_first_src(attrs)):
            self.removed += 1
            return
        self.out.append(f"<{tag}{self._attrs(tag, attrs)}{' /' if closed else ''}>")
        if not closed and tag not in _VOID_TAGS:
            self._open.append(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, closed=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, closed=True)

    def handle_endtag(self, tag: str) -> None:
        if self._skip:
            if tag == self._skip[-1]:
                self._skip.pop()
            return
        if tag in self._open:
            while self._open:
                last = self._open.pop()
                self.out.append(f"</{last}>")
                if last == tag:
                    break

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._open and self._open[-1] == "style":
            css, count = clean_css(data)
            self.removed += count
            self.out.append(css)
        else:
            self.out.append(html.escape(data, quote=False))

    def handle_comment(self, data: str) -> None:
        self.removed += 1

    def handle_decl(self, decl: str) -> None:
        self.removed += 1

    def handle_pi(self, data: str) -> None:
        self.removed += 1

    def unknown_decl(self, data: str) -> None:
        self.removed += 1

    def result(self) -> CleanPage:
        self.out.extend(f"</{tag}>" for tag in reversed(self._open))
        self._open.clear()
        return CleanPage("".join(self.out), self.removed)


def clean_page(body: str) -> CleanPage:
    """Return ``body`` rebuilt from the allowed tags and attributes only.

    Scripts, frames, forms and media are dropped with their content; event handlers,
    links and outside or local images are dropped; CSS loses imports and ``url()``.
    Images are kept only as inline PNG, JPEG, GIF or WebP data.
    """
    cleaner = _Cleaner()
    cleaner.feed(body)
    cleaner.close()
    return cleaner.result()


def sealed_document(body: str, title: str) -> str:
    """Wrap a cleaned ``body`` in a full page whose content policy allows no loads."""
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"{_CSP}\">"
        f"<title>{html.escape(title)}</title></head><body>{body}</body></html>"
    )
