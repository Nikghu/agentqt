"""
Module: MD-GUI-007 — log_viewer_panel.py
FO-GUI-007 Log Viewer: streaming colored log display with live filters.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C


# ── Color map for level names ─────────────────────────────────────────────────

_LEVEL_COLORS: dict[str, str] = {
    "DEBUG":    C.BLUE,
    "INFO":     "#ffffff",
    "WARNING":  C.ORANGE,
    "ERROR":    C.RED,
    "CRITICAL": C.MAROON if hasattr(C, "MAROON") else "#eba0ac",
}

_LEVEL_BG: dict[str, str] = {
    "ERROR":    "#1a0808",
    "CRITICAL": "#200808",
}


def _html_entry(level: str, message: str) -> str:
    """Build one colored HTML log line."""
    ts    = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    color = _LEVEL_COLORS.get(level, C.TEXT)
    bg    = _LEVEL_BG.get(level, "transparent")
    bg_style = f"background-color:{bg};" if bg != "transparent" else ""
    level_padded = level.ljust(8)
    return (
        f'<div style="font-family:Consolas,monospace;font-size:9pt;'
        f'padding:1px 4px;{bg_style}">'
        f'<span style="color:{C.MUTED}">{ts}</span>  '
        f'<span style="color:{color};font-weight:bold">[{level_padded}]</span>  '
        f'<span style="color:{color}">{message}</span>'
        f'</div>'
    )


# ── Log Viewer Panel ──────────────────────────────────────────────────────────

class LogViewerPanel(QWidget):
    """
    FO-GUI-007 Log Viewer Panel.
    Filter row + streaming QTextEdit. Connects to AppService.log_message.
    """

    MAX_LINES = 10_000
    error_occurred = pyqtSignal()  # emitted when ERROR/CRITICAL arrives

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo      = demo
        self._paused    = False
        self._line_count = 0
        self._buffer: list[tuple[str, str]] = []   # (level, message)

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        # ── Filter row ─────────────────────────────────────────────────────────
        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("ALL")
        self._level_combo.setFixedWidth(100)
        self._level_combo.currentTextChanged.connect(self._reapply_filter)

        lbl_lvl = QLabel("Level:")
        lbl_mod = QLabel("Search:")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by keyword…")
        self._search.setFixedWidth(220)
        self._search.textChanged.connect(self._reapply_filter)

        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)

        self._pause_btn = QPushButton("Pause")
        set_icon(self._pause_btn, "pause", "go")
        self._pause_btn.setFixedWidth(90)
        self._pause_btn.clicked.connect(self._toggle_pause)

        self._clear_btn = QPushButton("Clear")
        set_icon(self._clear_btn, "eraser")
        self._clear_btn.setFixedWidth(80)
        self._clear_btn.clicked.connect(self._clear)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(lbl_lvl)
        filter_row.addWidget(self._level_combo)
        filter_row.addWidget(lbl_mod)
        filter_row.addWidget(self._search)
        filter_row.addWidget(self._auto_scroll)
        filter_row.addStretch()
        filter_row.addWidget(self._pause_btn)
        filter_row.addWidget(self._clear_btn)
        main.addLayout(filter_row)

        # ── Log text area ──────────────────────────────────────────────────────
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._log_view.setFont(font)
        self._log_view.setStyleSheet(
            f"QTextEdit {{ background: {C.SURFACE}; color: {C.TEXT}; "
            f"border: 1px solid {C.OVERLAY}; border-radius: 4px; outline: none; }}"
        )
        main.addWidget(self._log_view, 1)

        # ── Footer ─────────────────────────────────────────────────────────────
        self._count_lbl = QLabel("0 entries")
        self._count_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")
        main.addWidget(self._count_lbl)

        # ── Connect demo signal ────────────────────────────────────────────────
        demo.log_message.connect(self._on_log_message)

        # ── Welcome message ────────────────────────────────────────────────────
        self._append_entry("INFO",  "Log viewer started — streaming demo messages")
        self._append_entry("INFO",  "Price update timer active (2 s interval)")
        self._append_entry("INFO",  "Demo mode: no live IBKR connection")

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_log_message(self, level: str, message: str) -> None:
        self._buffer.append((level, message))
        if len(self._buffer) > self.MAX_LINES:
            self._buffer = self._buffer[-self.MAX_LINES:]
        if level in ("ERROR", "CRITICAL"):
            self.error_occurred.emit()
        if not self._paused and self._matches_filter(level, message):
            self._append_entry(level, message)

    def _append_entry(self, level: str, message: str) -> None:
        self._log_view.append(_html_entry(level, message))
        self._line_count += 1
        self._count_lbl.setText(f"{self._line_count} entries")
        if self._auto_scroll.isChecked():
            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _matches_filter(self, level: str, message: str) -> bool:
        selected_level = self._level_combo.currentText()
        if selected_level != "ALL":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            try:
                if levels.index(level) < levels.index(selected_level):
                    return False
            except ValueError:
                pass
        kw = self._search.text().strip().lower()
        if kw and kw not in message.lower():
            return False
        return True

    def _reapply_filter(self) -> None:
        """Re-render entire view based on current filter settings."""
        self._log_view.clear()
        self._line_count = 0
        for level, msg in self._buffer:
            if self._matches_filter(level, msg):
                self._log_view.append(_html_entry(level, msg))
                self._line_count += 1
        self._count_lbl.setText(f"{self._line_count} entries (filtered)")
        if self._auto_scroll.isChecked():
            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("Resume")
            set_icon(self._pause_btn, "play", "go")
            self._pause_btn.setStyleSheet(f"color: {C.YELLOW};")
        else:
            self._pause_btn.setText("Pause")
            set_icon(self._pause_btn, "pause", "go")
            self._pause_btn.setStyleSheet("")
            # Flush buffered entries received while paused
            self._reapply_filter()

    def _clear(self) -> None:
        self._buffer.clear()
        self._log_view.clear()
        self._line_count = 0
        self._count_lbl.setText("0 entries")
