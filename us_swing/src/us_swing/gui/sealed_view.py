"""
Module: MD-GUI-034.024.M20 — gui/sealed_view.py
Parent SRD: SRD-GUI-034.024
Also: SRD-GUI-034.025 (request filter)

A sealed web view for AI report pages: one shared off-the-record profile whose request
filter lets through only the page itself, with JavaScript, local file and remote URL
access turned off. Pages are cleaned again by ``core.report_html`` before they are shown.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QWidget

from us_swing.core.report_html import clean_page, sealed_document

log = logging.getLogger(__name__)

_ALLOWED_SCHEMES = frozenset({"data", "about"})
_OFF = (
    QWebEngineSettings.WebAttribute.JavascriptEnabled,
    QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
    QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
    QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
    QWebEngineSettings.WebAttribute.LocalStorageEnabled,
    QWebEngineSettings.WebAttribute.PluginsEnabled,
    QWebEngineSettings.WebAttribute.PdfViewerEnabled,
    QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
    QWebEngineSettings.WebAttribute.WebGLEnabled,
    QWebEngineSettings.WebAttribute.DnsPrefetchEnabled,
)
_profile: QWebEngineProfile | None = None


def allowed_scheme(scheme: str) -> bool:
    """True only for the page itself (``setHtml`` loads it as ``data:``) and ``about:``."""
    return scheme.lower() in _ALLOWED_SCHEMES


class _PageOnly(QWebEngineUrlRequestInterceptor):
    """Blocks every request that is not the page itself."""

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802 — Qt name
        url = info.requestUrl()
        if not allowed_scheme(url.scheme()):
            info.block(True)
            log.debug("[Pages] Blocked a request from a report page to %s",
                      url.toString()[:120])


def sealed_profile() -> QWebEngineProfile:
    """Return the shared sealed profile (off the record, no cache, no cookies)."""
    global _profile
    if _profile is None:
        profile = QWebEngineProfile(QApplication.instance())
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        interceptor = _PageOnly(profile)
        profile.setUrlRequestInterceptor(interceptor)
        profile.destroyed.connect(_forget_profile)
        _profile = profile
    return _profile


def _forget_profile() -> None:
    global _profile
    _profile = None


class _SealedPage(QWebEnginePage):
    """A page that never navigates away from itself."""

    def acceptNavigationRequest(  # noqa: N802 — Qt name
        self, url: QUrl, kind: QWebEnginePage.NavigationType, is_main_frame: bool,
    ) -> bool:
        return allowed_scheme(url.scheme())


class SealedView(QWebEngineView):
    """A web view that shows one cleaned report page and can load nothing else."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        page = _SealedPage(sealed_profile(), self)
        settings = page.settings()
        for attribute in _OFF:
            settings.setAttribute(attribute, False)  # type: ignore[union-attr]
        self.setPage(page)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def show_page(self, body: str, title: str) -> None:
        """Clean ``body`` again and show it inside the sealed page shell."""
        self.setHtml(sealed_document(clean_page(body).html, title))
