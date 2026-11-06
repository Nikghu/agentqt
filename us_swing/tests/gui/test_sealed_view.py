"""Tests for MD-GUI-034.024.M20 — gui/sealed_view.py (sealed web view for report pages)."""
from __future__ import annotations

import logging

import pytest
from PyQt6.QtCore import QUrl
from pytestqt.qtbot import QtBot

web = pytest.importorskip("PyQt6.QtWebEngineWidgets")
if not isinstance(web.QWebEngineView, type) or web.QWebEngineView.__module__ != "PyQt6.QtWebEngineWidgets":
    pytest.skip("QtWebEngine is stubbed in this test run", allow_module_level=True)

from PyQt6.QtWebEngineCore import QWebEngineSettings  # noqa: E402

from us_swing.gui import sealed_view  # noqa: E402
from us_swing.gui.sealed_view import SealedView, _PageOnly, allowed_scheme  # noqa: E402

_A = QWebEngineSettings.WebAttribute


def test_sealed_settings(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-034.024.M20.T01: off-the-record profile; JavaScript, file and remote access off."""
    view = SealedView()
    qtbot.addWidget(view)
    page = view.page()
    assert page is not None
    profile = page.profile()
    assert profile is not None and profile.isOffTheRecord()
    assert profile is sealed_view.sealed_profile()
    settings = page.settings()
    assert settings is not None
    for attribute in (_A.JavascriptEnabled, _A.LocalContentCanAccessFileUrls,
                      _A.LocalContentCanAccessRemoteUrls, _A.LocalStorageEnabled,
                      _A.PluginsEnabled):
        assert not settings.testAttribute(attribute), attribute
    shown: list[str] = []
    monkeypatch.setattr(view, "setHtml", lambda html, *a: shown.append(html))
    view.show_page("<p onclick=\"x()\">Hi</p><script>bad()</script>", "Report")
    assert "onclick" not in shown[0] and "bad()" not in shown[0] and "<p>Hi</p>" in shown[0]
    assert "Content-Security-Policy" in shown[0]


def test_request_rule() -> None:
    """UT-GUI-034.025.M20.T01: only the page itself (data:) and about: are allowed."""
    assert allowed_scheme("data") and allowed_scheme("about") and allowed_scheme("DATA")
    for scheme in ("http", "https", "file", "qrc", "ws", "wss", "ftp", ""):
        assert not allowed_scheme(scheme), scheme


class _Info:
    def __init__(self, url: str) -> None:
        self._url = QUrl(url)
        self.blocked = False

    def requestUrl(self) -> QUrl:  # noqa: N802 — Qt name
        return self._url

    def block(self, value: bool) -> None:
        self.blocked = value


def test_blocked_request_logged(caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-034.025.M20.T02: an https request is blocked and logged once at DEBUG."""
    rule = _PageOnly()
    info, page = _Info("https://example.com/x.png"), _Info("data:text/html,<p>x</p>")
    with caplog.at_level(logging.DEBUG, logger="us_swing.gui.sealed_view"):
        rule.interceptRequest(info)  # type: ignore[arg-type]
        rule.interceptRequest(page)  # type: ignore[arg-type]
    assert info.blocked and not page.blocked
    lines = [r for r in caplog.records if r.getMessage().startswith("[Pages]")]
    assert len(lines) == 1 and lines[0].levelno == logging.DEBUG
