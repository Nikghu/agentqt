"""Tests for MD-MKT-007.003.M01 — core/report_html.py (page cleaner and sealed shell)."""
from __future__ import annotations

from html.parser import HTMLParser

from us_swing.core.report_html import clean_page, sealed_document

PNG = "data:image/png;base64,iVBORw0KGgo="


def test_allowed_content_kept() -> None:
    """UT-MKT-007.003.M01.T01: tables, headings, a style block and an inline svg chart are kept."""
    body = ("<style>h2 { color: #eee; }</style><h2 class=\"t\">Evening</h2>"
            "<table><tr><th>Side</th><td colspan=\"2\">long</td></tr></table>"
            "<svg viewBox=\"0 0 10 10\"><rect x=\"1\" y=\"2\" width=\"3\" height=\"4\" "
            "fill=\"#0af\"></rect><text x=\"1\" y=\"9\">NVDA</text></svg>")
    page = clean_page(body)
    assert page.removed == 0
    assert page.html == body


def test_scripts_and_handlers_removed() -> None:
    """UT-MKT-007.003.M01.T02: scripts, on* handlers, iframes and javascript links are removed."""
    body = ("<p onclick=\"steal()\">Hi</p><script>alert('x')</script>"
            "<svg onload=\"run()\"><circle r=\"2\"></circle></svg>"
            "<iframe src=\"https://x\"><p>inside</p></iframe>"
            "<a href=\"javascript:alert(1)\">link</a>")
    page = clean_page(body)
    for bad in ("script", "alert", "onclick", "onload", "iframe", "inside", "href", "<a"):
        assert bad not in page.html
    assert "<p>Hi</p>" in page.html and "link" in page.html
    assert page.removed == 5


def test_outside_and_local_images_removed() -> None:
    """UT-MKT-007.003.M01.T03: only inline PNG/JPEG/GIF/WebP data images are kept."""
    body = (f"<img src=\"https://x/a.png\"><img src=\"file:///C:/a.png\">"
            f"<img src=\"data:image/svg+xml;base64,PHN2Zz4=\"><img src=\"{PNG}\" alt=\"ok\">")
    page = clean_page(body)
    assert page.html == f"<img src=\"{PNG}\" alt=\"ok\">"
    assert page.removed == 3


def test_css_loads_removed() -> None:
    """UT-MKT-007.003.M01.T04: @import, url() and expression() are taken out of CSS."""
    body = ("<style>@import url(https://x/a.css); body { color: #ddd; "
            "background: url(https://x/b.png); width: expression(alert(1)); }</style>"
            "<div style=\"color: red; background: url('file:///a.png')\">x</div>")
    page = clean_page(body)
    for bad in ("@import", "url(", "expression", "https://", "file:"):
        assert bad not in page.html
    assert "color: #ddd;" in page.html and "color: red;" in page.html
    assert page.removed >= 4


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)


def test_tricky_markup() -> None:
    """UT-MKT-007.003.M01.T05: escaped text stays text; upper case, comments and doctype go."""
    body = ("<!DOCTYPE html><!-- note --><p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"
            "<SCRIPT>bad()</SCRIPT><div><p>open"
            "<style>p { color: red; } </style><b>x</b>")
    page = clean_page(body)
    assert "&lt;script&gt;" in page.html
    assert "bad()" not in page.html and "<!--" not in page.html and "DOCTYPE" not in page.html
    assert page.html.endswith("</div>") or page.html.endswith("</p></div>")
    parser = _Tags()
    parser.feed(page.html)
    assert "script" not in parser.tags
    assert parser.tags.count("style") == 1


def test_sealed_shell() -> None:
    """UT-MKT-007.003.M01.T06: the shell has the content policy and an escaped title."""
    doc = sealed_document("<p>x</p>", "A < B")
    assert doc.startswith("<!DOCTYPE html>")
    assert "Content-Security-Policy" in doc and "default-src 'none'" in doc
    assert "img-src data:" in doc
    assert "<title>A &lt; B</title>" in doc and "<body><p>x</p></body>" in doc


def test_css_cannot_rebuild_loads() -> None:
    """UT-MKT-007.003.M01.T07: removals and CSS escapes cannot build a new url() or image-set()."""
    for css in ("a{background:ur<l(http://x/a.png)}", "a{background:ur@import a;l(http://x/a.png)}",
                r"a{background:u\72l(http://x/a.png)}",
                "a{background:image-set('http://x/a.png' 1x)}",
                r"@\69mport 'http://x/a.css'; a{}", "@font-face{src:local(Arial)}"):
        html = clean_page(f"<style>{css}</style><div style=\"{css}\">x</div>").html
        for bad in ("url(", "image-set", "@import", "local(", "\\"):
            assert bad not in html.lower(), (css, html)


def test_duplicate_and_svg_attributes() -> None:
    """UT-MKT-007.003.M01.T08: a second src is dropped; svg fill with url() is cleaned."""
    page = clean_page(f"<img src=\"http://x/a\" src=\"{PNG}\">"
                      f"<img src=\"{PNG}\" src=\"http://x/a\">"
                      "<svg><rect fill=\"url(http://x/a.svg#p)\" stroke=\"#fff\"/></svg>"
                      "<style/><p>after</p>")
    assert "http://" not in page.html
    assert page.html.count("<img") == 1 and f"<img src=\"{PNG}\">" in page.html
    assert "stroke=\"#fff\"" in page.html and "<style" not in page.html
    assert "<p>after</p>" in page.html
