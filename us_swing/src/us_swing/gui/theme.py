"""
Module: MD-GUI-001.001.M01 — Theme

Single source of truth for ALL GUI theme values. Two themes are supported:
    • Catppuccin Mocha (default)   → MOCHA_QSS    keyed as "mocha"
    • VS Code Dark                 → VS_CODE_QSS  keyed as "vscode"

To change a colour, edit it here only. Three surfaces own the hex literals:

    1. MOCHA_QSS / VS_CODE_QSS  — global stylesheet (hex literals inlined,
       no f-string interpolation) for everything QSS can style.
    2. THEME_COLORS[<theme_id>]  — runtime colour roles, used by widgets
       that paint themselves (custom paintEvent, QStandardItem
       BackgroundRole, embedded HTML/JS chart rendering). Call
       `colors()` to get the dict for the active theme.
    3. C / _VS                   — named token classes consumed by panel
       code (kept stable as the panel-facing API surface).

No GUI panel may contain a hex literal. If a panel needs a colour, either
the global QSS should style it via objectName / property selector, or the
panel reads `colors()["<role>"]` / `C.<TOKEN>` / `active_palette().<TOKEN>`.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Catppuccin Mocha — colour tokens + sizing
# ─────────────────────────────────────────────────────────────────────────────

class _MOCHA:
    """Mocha colour tokens + universal widget sizing constants."""
    BG       = "#1e1e2e"
    SURFACE  = "#181825"
    OVERLAY  = "#313244"
    OVERLAY2 = "#45475a"
    INPUT    = "#181825"
    TEXT     = "#cdd6f4"
    SUBTEXT  = "#bac2de"
    MUTED    = "#7f849c"

    GREEN    = "#a6e3a1"
    RED      = "#f38ba8"
    YELLOW   = "#f9e2af"
    ORANGE   = "#fab387"
    BLUE     = "#89b4fa"
    TEAL     = "#94e2d5"
    MAUVE    = "#cba6f7"

    # Position state colours
    STATE_NEW             = "#7f849c"
    STATE_PARTIAL_ENTRY   = "#f9e2af"
    STATE_OPEN            = "#a6e3a1"
    STATE_PARTIAL_EXIT    = "#fab387"
    STATE_CLOSED          = "#6c7086"

    # P&L cell background (dark tint)
    PNL_POS_BG = "#1a3326"
    PNL_NEG_BG = "#331a1a"

    # Standard widget heights — use these everywhere; never hardcode px values
    BTN_H    = 28   # all QPushButton variants
    BTN_H_SM = 26   # compact buttons in group-card / dialog headers
    INPUT_H  = 28   # QLineEdit / QSpinBox / QDoubleSpinBox / QComboBox / QTimeEdit


STATE_COLORS: dict[str, str] = {
    "NEW":           _MOCHA.STATE_NEW,
    "PARTIAL_ENTRY": _MOCHA.STATE_PARTIAL_ENTRY,
    "OPEN":          _MOCHA.STATE_OPEN,
    "PARTIAL_EXIT":  _MOCHA.STATE_PARTIAL_EXIT,
    "CLOSED":        _MOCHA.STATE_CLOSED,
}


# ─────────────────────────────────────────────────────────────────────────────
# VS Code Dark — colour tokens
# ─────────────────────────────────────────────────────────────────────────────

class _VS:
    """VS Code Dark colour tokens (ported from ACU dark_theme.py)."""
    BG       = "#1e1e1e"
    SURFACE  = "#252526"
    OVERLAY  = "#2d2d2d"
    OVERLAY2 = "#454545"
    INPUT    = "#3c3c3c"
    TEXT     = "#d4d4d4"
    SUBTEXT  = "#9d9d9d"
    MUTED    = "#6d6d6d"

    BLUE     = "#007acc"
    GREEN    = "#4ec9b0"
    RED      = "#f44747"
    YELLOW   = "#cca700"
    ORANGE   = "#ce9178"
    TEAL     = "#4ec9b0"
    MAUVE    = "#c586c0"

    STATE_NEW           = "#6d6d6d"
    STATE_PARTIAL_ENTRY = "#cca700"
    STATE_OPEN          = "#4ec9b0"
    STATE_PARTIAL_EXIT  = "#ce9178"
    STATE_CLOSED        = "#4d4d4d"

    PNL_POS_BG = "#1a2e2e"
    PNL_NEG_BG = "#2e1a1a"

    BTN_H    = _MOCHA.BTN_H
    BTN_H_SM = _MOCHA.BTN_H_SM
    INPUT_H  = _MOCHA.INPUT_H


VS_STATE_COLORS: dict[str, str] = {
    "NEW":           _VS.STATE_NEW,
    "PARTIAL_ENTRY": _VS.STATE_PARTIAL_ENTRY,
    "OPEN":          _VS.STATE_OPEN,
    "PARTIAL_EXIT":  _VS.STATE_PARTIAL_EXIT,
    "CLOSED":        _VS.STATE_CLOSED,
}


# ─────────────────────────────────────────────────────────────────────────────
# Runtime colour roles — used by non-QSS code paths only.
# Add a key here when a panel needs a colour that QSS cannot style
# (custom paintEvent, QStandardItem BackgroundRole, HTML/JS chart render).
# ─────────────────────────────────────────────────────────────────────────────

THEME_COLORS: dict[str, dict[str, str]] = {
    "mocha": {
        # TradingView-convention candle colours (semi-transparent for volume).
        "candle_up_volume":      "#26a69a55",
        "candle_down_volume":    "#ef535055",
        # Screener score-cell amber background (mid-range score band).
        "score_cell_warning_bg": "#2e2a14",
        # Screener tab × close button hover background.
        "filter_close_hover_bg": "#c0392b88",
        # Validator pill row backgrounds (set via QStandardItem.BackgroundRole).
        "validator_pass_bg":     "#1a2d1a",
        "validator_fail_bg":     "#2d1a1a",
        # Mode badge backgrounds in screener results header.
        "mode_auto_bg":          "#12302e",
        "mode_manual_bg":        "#1a2d45",
        # Status badge text colour — sits on top of light-tint badge BGs.
        "badge_text_dark":       "#1e1e2e",
        # Dashboard scope strip + pills.
        "scope_strip_bg":          "#181825",
        "scope_strip_border":      "#313244",
        "scope_pill_muted":        "#7f849c",
        "scope_pill_border":       "#313244",
        "scope_pill_checked_bg":   "#89b4fa33",
        "scope_pill_checked_fg":   "#89b4fa",
        "scope_pill_checked_bd":   "#89b4fa",
    },
    "vscode": {
        "candle_up_volume":      "#26a69a55",
        "candle_down_volume":    "#ef535055",
        "score_cell_warning_bg": "#3a3520",
        "filter_close_hover_bg": "#c0392b88",
        "validator_pass_bg":     "#1a2e1a",
        "validator_fail_bg":     "#2e1a1a",
        "mode_auto_bg":          "#1a2e2e",
        "mode_manual_bg":        "#1a2535",
        "badge_text_dark":       "#1e1e1e",
        "scope_strip_bg":          "#252526",
        "scope_strip_border":      "#454545",
        "scope_pill_muted":        "#6d6d6d",
        "scope_pill_border":       "#2d2d2d",
        "scope_pill_checked_bg":   "#3a3d41",
        "scope_pill_checked_fg":   "#ffffff",
        "scope_pill_checked_bd":   "#9d9d9d",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Global stylesheet — Catppuccin Mocha (hex literals inlined, no interpolation)
# ─────────────────────────────────────────────────────────────────────────────

MOCHA_QSS = """
/* ═══════════════════════════════════════════════════════════
   GLOBAL  — Catppuccin Mocha · TIKR / Finviz terminal style
   ═══════════════════════════════════════════════════════════ */
QMainWindow, QDialog, QWidget {
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* ── Compact frameless title bar ─────────────────────────── */
QWidget#title_bar {
    background: #11111b;
    border-bottom: 1px solid #313244;
}
QWidget#dlg_title_bar {
    background: #1e1e2e;
}
QLabel#top_brand {
    color: #89b4fa;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0 4px 0 8px;
}
QLabel#top_version { color: #6c7086; font-size: 8pt; padding: 0 6px 0 0; }
QLabel#user_chip  { color: #cdd6f4;   font-size: 8pt; padding: 0 4px; }
QLabel#risk_err_lbl { color: #f38ba8; font-size: 9pt; }

/* ── Horizontal tab nav (inside title bar) ────────────────── */
QPushButton#tab_btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #7f849c;
    font-size: 8pt;
    padding: 0 10px;
    min-height: 38px;
    max-height: 38px;
    outline: none;
}
QPushButton#tab_btn:hover {
    color: #cdd6f4;
    background: #31324422;
    outline: none;
}
QPushButton#tab_btn:checked {
    color: #cdd6f4;
    background: #45475a55;
    border-bottom: none;
    border-radius: 4px;
    font-weight: bold;
    outline: none;
}
QPushButton#tab_btn:focus {
    outline: none;
}
QPushButton#tab_btn:checked:focus {
    outline: none;
}


/* ── Accent underline below title bar ─────────────────────── */
QFrame#accent_line { color: #45475a; max-height: 2px; }

/* ── Admin context bar (username / market watch strip) ────── */
QWidget#admin_ctx_bar {
    background: #181825;
    border-bottom: 1px solid #313244;
}

/* ── Screener toolbar + preset pane ──────────────────────── */
QFrame#screener_toolbar {
    background: #1e1e2e;
    border-bottom: 1px solid #313244;
}
QFrame#preset_pane {
    background: #181825;
    border-right: 1px solid #313244;
}

/* ── AI Transcript panel ──────────────────────────────────── */
QFrame#transcript_header_bar {
    background: #181825;
    border-top: 1px solid #313244;
}

/* ── Dashboard QTabWidget ─────────────────────────────────────── */
QTabWidget#dash_tabs::pane {
    border: 1px solid #313244;
    border-radius: 4px;
    background: #1e1e2e;
}
QTabWidget#dash_tabs > QTabBar::tab {
    background: #181825;
    color: #7f849c;
    font-size: 9pt;
    padding: 6px 16px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabWidget#dash_tabs > QTabBar::tab:selected {
    background: #1e1e2e;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
    font-weight: bold;
}
QTabWidget#dash_tabs > QTabBar::tab:hover:!selected {
    color: #cdd6f4;
    background: #313244;
}

/* ── Stat cards (TIKR KPI style) ─────────────────────────── */
QFrame#stat_card {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 10px;
}
QFrame#stat_card:hover {
    border: 1px solid #45475a;
}
QWidget#stat_card_inner {
    background: transparent;
}
QWidget#stat_card_inner QLabel {
    background: transparent;
}

/* ── Screener chip / badge row ────────────────────────────── */
QFrame#filter_chip {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 12px;
    padding: 2px 10px;
}
QFrame#filter_chip[active="true"] {
    background: #1a2d45;
    border: 1px solid #89b4fa;
}

/* ── Mode/status badges ───────────────────────────────────── */
QLabel#mode_live {
    background: #331a1a;
    color: #f38ba8;
    border: 1px solid #f38ba8;
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}
QLabel#mode_paper {
    background: #1a2d45;
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}
QLabel#can_enter_yes {
    background: #1a3326;
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}
QLabel#can_enter_no {
    background: #331a1a;
    color: #f38ba8;
    border: 1px solid #f38ba8;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}

/* ── (legacy) Tab widget — kept for any residual usage ────── */
QTabWidget::pane {
    border: 1px solid #313244;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #181825;
    color: #7f849c;
    padding: 8px 22px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 9pt;
}
QTabBar::tab:selected {
    background: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover:!selected {
    background: #313244;
    color: #cdd6f4;
}
QTableView, QTreeView {
    background: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    outline: none;
}
QTableView::item, QTreeView::item {
    padding: 3px 6px;
}
QHeaderView::section {
    background: #313244;
    color: #bac2de;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #45475a;
    border-bottom: 1px solid #45475a;
    font-weight: bold;
    font-size: 8pt;
    text-transform: uppercase;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 0 8px;
    min-height: 28px;
    max-height: 28px;
    outline: none;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {
    border: 1px solid #89b4fa;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #313244;
    selection-background-color: #45475a;
    color: #cdd6f4;
    border: 1px solid #45475a;
}
QPushButton {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 0 16px;
    font-size: 9pt;
    min-height: 28px;
    max-height: 28px;
    outline: none;
}
QPushButton:focus {
    outline: none;
}
QPushButton:hover {
    background: #45475a;
    border: 1px solid #89b4fa;
}
QPushButton:pressed {
    background: #45475a;
}
QPushButton:disabled {
    color: #7f849c;
    background: #181825;
    border-color: #313244;
}
QPushButton#buy_btn {
    background: #1a3326;
    border: 1px solid #a6e3a1;
    color: #a6e3a1;
    font-weight: bold;
}
QPushButton#buy_btn:hover { background: #223d2e; }
QPushButton#close_btn {
    background: #331a1a;
    border: 1px solid #f38ba8;
    color: #f38ba8;
}
QPushButton#close_btn:hover { background: #3d2222; }
QPushButton#run_btn {
    background: #1a2d45;
    border: 1px solid #89b4fa;
    color: #89b4fa;
    font-weight: bold;
    padding: 0 24px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#run_btn:hover { background: #1e3658; }
QPushButton#run_btn:disabled { color: #7f849c; background: #31324444; border-color: #313244; }
QPushButton#add_btn {
    background: #2a1a3a;
    border: 1px solid #cba6f7;
    color: #cba6f7;
    padding: 0 8px;
    font-size: 9pt;
}
QPushButton#add_btn:hover { background: #33214d; }
QPushButton#add_btn:disabled { color: #7f849c; background: #31324444; border-color: #313244; }
QPushButton#danger_btn {
    background: #f38ba822;
    border: 1px solid #f38ba8;
    color: #f38ba8;
}
QPushButton#danger_btn:hover { background: #3d2222; }

/* ── Reusable named colour variants (standard 28 px height) ── */
QPushButton#btn_green {
    background: #1a3d2a;
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
    border-radius: 4px;
    padding: 0 16px;
}
QPushButton#btn_green:hover { background: #1e4a32; }
QPushButton#btn_blue {
    background: #1a2d45;
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 4px;
    font-size: 9pt;
}
QPushButton#btn_blue:hover { background: #1e3558; }

/* ── Compact variants (26 px — group-card header controls) ─ */
QPushButton#btn_add_screener {
    background: #1a3d2a;
    color: #a6e3a1;
    border: 1px solid #a6e3a166;
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 10px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_add_screener:hover { background: #1e4a32; border-color: #a6e3a1; }
QPushButton#btn_configure {
    background: transparent;
    color: #bac2de;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_configure:hover:enabled { color: #89b4fa; border-color: #89b4fa; }
QPushButton#btn_configure:disabled { color: #45475a; border-color: #313244; }
QPushButton#btn_remove {
    background: transparent;
    color: #7f849c;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_remove:hover { color: #f38ba8; border-color: #f38ba8; }

/* ── Square nav arrow buttons (toolbar date navigation) ────── */
QPushButton#btn_nav {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 12pt;
    padding: 0;
}
QPushButton#btn_nav:hover { background: #45475a; border-color: #89b4fa; }
QPushButton#btn_nav:disabled { color: #7f849c; background: #31324444; border-color: #313244; }

QProgressBar {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 3px;
    max-height: 10px;
    text-align: center;
    font-size: 7pt;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background: #89b4fa;
    border-radius: 3px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
    color: #bac2de;
    font-weight: bold;
    font-size: 9pt;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    background: #1e1e2e;
    padding: 0 4px;
}
QCheckBox {
    color: #cdd6f4;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background: #181825;
}
QCheckBox::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}
QStatusBar {
    background: #181825;
    color: #7f849c;
    border-top: 1px solid #313244;
    font-size: 9pt;
    min-height: 28px;
}
QStatusBar::item { border: none; }
QSplitter::handle {
    background: #313244;
    width: 2px;
}
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QScrollBar:horizontal {
    background: #181825;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QTextEdit {
    background: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    outline: none;
}
QListWidget {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    outline: none;
}
QListWidget::item:focus {
    outline: none;
    border: none;
}
QLabel { color: #cdd6f4; }
QToolTip {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px;
}
"""

# Back-compat alias — older code imports `QSS` directly.
QSS = MOCHA_QSS


# ─────────────────────────────────────────────────────────────────────────────
# Global stylesheet — VS Code Dark (hex literals inlined, no interpolation)
# ─────────────────────────────────────────────────────────────────────────────

VS_CODE_QSS = """
/* ═══════════════════════════════════════════════════════════
   GLOBAL  — VS Code Dark (inspired by Visual Studio / ACU)
   ═══════════════════════════════════════════════════════════ */
QMainWindow, QDialog, QWidget {
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* ── Compact frameless title bar ─────────────────────────── */
QWidget#title_bar {
    background: #161616;
    border-bottom: 1px solid #d4d4d4;
}
QWidget#dlg_title_bar {
    background: #1e1e1e;
}
QLabel#top_brand {
    color: #ffffff;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0 4px 0 8px;
}
QLabel#top_version { color: #8a8a8a; font-size: 8pt; padding: 0 6px 0 0; }
QLabel#user_chip  { color: #d4d4d4; font-size: 8pt; padding: 0 4px; }
QLabel#risk_err_lbl { color: #f44747; font-size: 9pt; }

/* ── Horizontal tab nav (inside title bar) ────────────────── */
QPushButton#tab_btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #6d6d6d;
    font-size: 8pt;
    padding: 0 10px;
    min-height: 38px;
    max-height: 38px;
    outline: none;
}
QPushButton#tab_btn:hover {
    color: #d4d4d4;
    background: #45454533;
    outline: none;
}
QPushButton#tab_btn:checked {
    color: #d4d4d4;
    background: #45454555;
    border-bottom: none;
    border-radius: 4px;
    font-weight: bold;
    outline: none;
}
QPushButton#tab_btn:focus { outline: none; }
QPushButton#tab_btn:checked:focus { outline: none; }

/* ── Accent underline below title bar ─────────────────────── */
QFrame#accent_line { color: #9d9d9d; max-height: 2px; }

/* ── Admin context bar (username / market watch strip) ────── */
QWidget#admin_ctx_bar {
    background: #252526;
    border-bottom: 1px solid #454545;
}

/* ── Screener toolbar + preset pane ──────────────────────── */
QFrame#screener_toolbar {
    background: #1e1e1e;
    border-bottom: 1px solid #454545;
}
QFrame#preset_pane {
    background: #252526;
    border-right: 1px solid #454545;
}

/* ── AI Transcript panel ──────────────────────────────────── */
QFrame#transcript_header_bar {
    background: #252526;
    border-top: 1px solid #454545;
}

/* ── Dashboard QTabWidget ─────────────────────────────────── */
QTabWidget#dash_tabs::pane {
    border: 1px solid #454545;
    border-radius: 4px;
    background: #1e1e1e;
}
QTabWidget#dash_tabs > QTabBar::tab {
    background: #252526;
    color: #6d6d6d;
    font-size: 9pt;
    padding: 6px 16px;
    border: 1px solid #454545;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabWidget#dash_tabs > QTabBar::tab:selected {
    background: #1e1e1e;
    color: #9d9d9d;
    border-bottom: 2px solid #9d9d9d;
    font-weight: bold;
}
QTabWidget#dash_tabs > QTabBar::tab:hover:!selected {
    color: #d4d4d4;
    background: #2a2d2e;
}

/* ── Stat cards ───────────────────────────────────────────── */
QFrame#stat_card {
    background: #252526;
    border: 1px solid #454545;
    border-radius: 4px;
    padding: 10px;
}
QFrame#stat_card:hover {
    border: 1px solid #9d9d9d;
}
QWidget#stat_card_inner { background: transparent; }
QWidget#stat_card_inner QLabel { background: transparent; }

/* ── Screener chip / badge row ────────────────────────────── */
QFrame#filter_chip {
    background: #2d2d2d;
    border: 1px solid #454545;
    border-radius: 12px;
    padding: 2px 10px;
}
QFrame#filter_chip[active="true"] {
    background: #1a2535;
    border: 1px solid #007acc;
}

/* ── Mode/status badges ───────────────────────────────────── */
QLabel#mode_live {
    background: #2e1a1a;
    color: #f44747;
    border: 1px solid #f44747;
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}
QLabel#mode_paper {
    background: #1a2535;
    color: #007acc;
    border: 1px solid #007acc;
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}
QLabel#can_enter_yes {
    background: #1a2e2e;
    color: #4ec9b0;
    border: 1px solid #4ec9b0;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}
QLabel#can_enter_no {
    background: #2e1a1a;
    color: #f44747;
    border: 1px solid #f44747;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}

/* ── Tab widget (generic) ─────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #454545;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #252526;
    color: #6d6d6d;
    padding: 8px 22px;
    border: 1px solid #454545;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 9pt;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: #9d9d9d;
    border-bottom: 2px solid #9d9d9d;
}
QTabBar::tab:hover:!selected {
    background: #2a2d2e;
    color: #d4d4d4;
}

/* ── Tables / trees ───────────────────────────────────────── */
QTableView, QTreeView {
    background: #252526;
    alternate-background-color: #1e1e1e;
    color: #d4d4d4;
    gridline-color: #454545;
    border: 1px solid #454545;
    border-radius: 2px;
    selection-background-color: #264f78;
    selection-color: #d4d4d4;
    outline: none;
}
QTableView::item, QTreeView::item { padding: 3px 6px; }
QHeaderView::section {
    background: #2d2d2d;
    color: #9d9d9d;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #454545;
    border-bottom: 1px solid #454545;
    font-weight: bold;
    font-size: 8pt;
    text-transform: uppercase;
}

/* ── Inputs ───────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {
    background: #3c3c3c;
    border: 1px solid #454545;
    border-radius: 2px;
    color: #d4d4d4;
    padding: 0 8px;
    min-height: 28px;
    max-height: 28px;
    outline: none;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {
    border: 1px solid #007acc;
    outline: none;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #252526;
    selection-background-color: #264f78;
    color: #d4d4d4;
    border: 1px solid #007acc;
    outline: none;
}

/* ── Buttons ──────────────────────────────────────────────── */
QPushButton {
    background: #2d2d2d;
    border: 1px solid #454545;
    border-radius: 2px;
    color: #d4d4d4;
    padding: 0 16px;
    font-size: 9pt;
    min-height: 28px;
    max-height: 28px;
    outline: none;
}
QPushButton:focus { outline: none; }
QPushButton:hover {
    background: #3a3d41;
    border: 1px solid #9d9d9d;
    color: #ffffff;
}
QPushButton:pressed { background: #007acc; color: #ffffff; border-color: #007acc; }
QPushButton:disabled { color: #6d6d6d; background: #252526; border-color: #2d2d2d; }

QPushButton#buy_btn {
    background: #1a2e2e;
    border: 1px solid #4ec9b0;
    color: #4ec9b0;
    font-weight: bold;
}
QPushButton#buy_btn:hover { background: #1e3535; }
QPushButton#close_btn {
    background: #2e1a1a;
    border: 1px solid #f44747;
    color: #f44747;
}
QPushButton#close_btn:hover { background: #3d2222; }
QPushButton#run_btn {
    background: #2d2d2d;
    border: 1px solid #454545;
    color: #d4d4d4;
    font-weight: bold;
    padding: 0 24px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#run_btn:hover { background: #454545; color: #ffffff; }
QPushButton#run_btn:disabled { color: #6d6d6d; background: #2d2d2d; border-color: #454545; }
QPushButton#add_btn {
    background: #291a2e;
    border: 1px solid #c586c0;
    color: #c586c0;
    padding: 0 8px;
    font-size: 9pt;
}
QPushButton#add_btn:hover { background: #32203a; }
QPushButton#add_btn:disabled { color: #6d6d6d; background: #2d2d2d; border-color: #454545; }
QPushButton#danger_btn {
    background: #2e1a1a;
    border: 1px solid #f44747;
    color: #f44747;
}
QPushButton#danger_btn:hover { background: #3d2222; }

QPushButton#btn_green {
    background: #1a2e2e;
    color: #4ec9b0;
    border: 1px solid #4ec9b0;
    border-radius: 2px;
    padding: 0 16px;
}
QPushButton#btn_green:hover { background: #1e3535; }
QPushButton#btn_blue {
    background: #1a2535;
    color: #007acc;
    border: 1px solid #007acc;
    border-radius: 2px;
    font-size: 9pt;
}
QPushButton#btn_blue:hover { background: #1e2e40; }

QPushButton#btn_add_screener {
    background: #1a2e2e;
    color: #4ec9b0;
    border: 1px solid #4ec9b066;
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 10px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_add_screener:hover { background: #1e3535; border-color: #4ec9b0; }
QPushButton#btn_configure {
    background: transparent;
    color: #9d9d9d;
    border: 1px solid #454545;
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_configure:hover:enabled { color: #d4d4d4; border-color: #9d9d9d; }
QPushButton#btn_configure:disabled { color: #454545; border-color: #2d2d2d; }
QPushButton#btn_remove {
    background: transparent;
    color: #6d6d6d;
    border: 1px solid #454545;
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton#btn_remove:hover { color: #f44747; border-color: #f44747; }

QPushButton#btn_nav {
    background: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #454545;
    border-radius: 2px;
    font-size: 12pt;
    padding: 0;
}
QPushButton#btn_nav:hover { background: #454545; border-color: #9d9d9d; }
QPushButton#btn_nav:disabled { color: #6d6d6d; background: #252526; border-color: #2d2d2d; }

/* ── Progress bar ─────────────────────────────────────────── */
QProgressBar {
    background: #252526;
    border: 1px solid #454545;
    border-radius: 2px;
    max-height: 10px;
    text-align: center;
    font-size: 7pt;
    color: #d4d4d4;
}
QProgressBar::chunk { background: #007acc; border-radius: 2px; }

/* ── Group box ────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #454545;
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 6px;
    color: #9d9d9d;
    font-weight: bold;
    font-size: 9pt;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    background: #1e1e1e;
    padding: 0 4px;
}

/* ── Checkbox ─────────────────────────────────────────────── */
QCheckBox { color: #d4d4d4; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #454545;
    border-radius: 2px;
    background: #3c3c3c;
}
QCheckBox::indicator:checked { background: #007acc; border-color: #007acc; }
QCheckBox::indicator:hover { border-color: #007acc; }

/* ── Status bar ───────────────────────────────────────────── */
QStatusBar {
    background: #007acc;
    color: #ffffff;
    border-top: none;
    font-size: 9pt;
    min-height: 28px;
}
QStatusBar::item { border: none; }

/* ── Splitter ─────────────────────────────────────────────── */
QSplitter::handle { background: #454545; width: 1px; }
QSplitter::handle:hover { background: #007acc; }

/* ── Scrollbars ───────────────────────────────────────────── */
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 5px;
    min-height: 20px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover { background: #686868; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QScrollBar:horizontal {
    background: #1e1e1e;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #424242;
    border-radius: 5px;
    min-width: 20px;
    margin: 1px;
}
QScrollBar::handle:horizontal:hover { background: #686868; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Text / list widgets ──────────────────────────────────── */
QTextEdit {
    background: #252526;
    color: #d4d4d4;
    border: 1px solid #454545;
    border-radius: 2px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    outline: none;
}
QListWidget {
    background: #252526;
    border: 1px solid #454545;
    border-radius: 2px;
    outline: none;
}
QListWidget::item:focus { outline: none; border: none; }
QListWidget::item:selected { background: #264f78; color: #d4d4d4; }
QListWidget::item:hover:!selected { background: #2a2d2e; }

QLabel { color: #d4d4d4; }
QToolTip {
    background: #252526;
    color: #d4d4d4;
    border: 1px solid #454545;
    padding: 4px 8px;
    font-size: 9pt;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Carbon — graphite + amber (default). Its QSS is MOCHA_QSS with every Mocha
# hex swapped through _MOCHA_TO_CARBON, so both themes style the same widgets.
# ─────────────────────────────────────────────────────────────────────────────

class _CARBON:
    """Carbon colour tokens. BLUE is the accent role (amber in this theme)."""
    BG       = "#0c0f13"
    SURFACE  = "#12161c"
    OVERLAY  = "#232a35"
    OVERLAY2 = "#2f3845"
    INPUT    = "#0f1318"
    TEXT     = "#dde2ea"
    SUBTEXT  = "#9ba5b4"
    MUTED    = "#687384"

    GREEN    = "#3cc583"
    RED      = "#ef5a50"
    YELLOW   = "#e8c14d"
    ORANGE   = "#ee8a4a"
    BLUE     = "#f0a63a"
    TEAL     = "#7fb4d9"
    MAUVE    = "#f4b85c"

    STATE_NEW           = "#687384"
    STATE_PARTIAL_ENTRY = "#e8c14d"
    STATE_OPEN          = "#3cc583"
    STATE_PARTIAL_EXIT  = "#ee8a4a"
    STATE_CLOSED        = "#59626f"

    PNL_POS_BG = "#12291e"
    PNL_NEG_BG = "#2e1615"

    BTN_H    = _MOCHA.BTN_H
    BTN_H_SM = _MOCHA.BTN_H_SM
    INPUT_H  = _MOCHA.INPUT_H


_MOCHA_TO_CARBON: dict[str, str] = {
    "#11111b": "#090b0e", "#181825": "#12161c", "#1e1e2e": "#0c0f13",
    "#313244": "#232a35", "#45475a": "#2f3845", "#6c7086": "#59626f",
    "#7f849c": "#687384", "#bac2de": "#9ba5b4", "#cdd6f4": "#dde2ea",
    "#89b4fa": "#f0a63a", "#a6e3a1": "#3cc583", "#f38ba8": "#ef5a50",
    "#cba6f7": "#f4b85c", "#f9e2af": "#e8c14d", "#fab387": "#ee8a4a",
    "#94e2d5": "#7fb4d9",
    "#1a2d45": "#2a2213", "#1e3558": "#3a2e17", "#1e3658": "#3a2e17",
    "#2a1a3a": "#2a2213", "#33214d": "#3a2e17",
    "#1a3326": "#12291e", "#1a3d2a": "#15301f", "#1e4a32": "#183a26", "#223d2e": "#1a3324",
    "#331a1a": "#2e1615", "#3d2222": "#3a1b19",
}


def _to_carbon(text: str) -> str:
    for mocha_hex, carbon_hex in _MOCHA_TO_CARBON.items():
        text = text.replace(mocha_hex, carbon_hex)
    return text


def _rgba_from_hex8(qss: str) -> str:
    """Rewrite ``#RRGGBBAA`` as ``rgba()``; Qt reads 8-digit hex as ``#AARRGGBB``."""
    def to_rgba(match: re.Match[str]) -> str:
        h = match.group(1)
        r, g, b, a = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
        return f"rgba({r}, {g}, {b}, {a / 255:.2f})"
    return re.sub(r"#([0-9a-fA-F]{8})(?![0-9a-fA-F])", to_rgba, qss)


_CARBON_EXTRA = """
QMainWindow, QDialog, QWidget {
    font-family: "IBM Plex Sans", "Segoe UI", Arial, sans-serif;
}
QPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QGroupBox {
    border-radius: 2px;
}
QTableView, QTableWidget, QTreeView {
    font-family: "IBM Plex Mono", Consolas, monospace;
}
"""


def _danger_qss(red: str, muted: str, line: str) -> str:
    r, g, b = (int(red[i:i + 2], 16) for i in (1, 3, 5))
    return f"""
QPushButton[role="danger"] {{
    background: transparent; color: {red}; border: 1px solid {red}; outline: none;
}}
QPushButton[role="danger"]:hover {{ background: rgba({r}, {g}, {b}, 0.15); }}
QPushButton[role="danger"]:focus {{ outline: none; }}
QPushButton[role="danger"]:disabled {{ color: {muted}; border-color: {line}; }}
"""


def _sidebar_qss(bg: str, line: str, text: str, sub: str, hover: str,
                 active_bg: str, accent: str) -> str:
    return f"""
QFrame#sidebar {{ background: {bg}; border: 1px solid {line}; border-radius: 6px; }}
QPushButton#side_btn {{
    background: transparent; color: {sub}; border: none; border-left: 2px solid transparent;
    border-radius: 2px; text-align: left; padding: 0 10px; outline: none; font-size: 10pt;
}}
QPushButton#side_btn:hover {{ background: {hover}; color: {text}; }}
QPushButton#side_btn:checked {{
    background: {active_bg}; color: {accent}; border-left: 2px solid {accent}; font-weight: bold;
}}
QPushButton#side_btn:focus {{ outline: none; }}
QFrame#side_sep {{ background: {line}; border: none; }}
QLabel#side_footer {{ color: {sub}; font-size: 8.5pt; }}
QLabel#top_brand {{ font-size: 10pt; letter-spacing: 0px; }}
QWidget#side_account, QWidget#side_account QLabel {{ background: transparent; }}
QWidget#side_conn, QWidget#side_conn_rows, QWidget#side_conn QLabel {{ background: transparent; }}
QLabel#side_conn_title {{ color: {sub}; font-size: 7.5pt; font-weight: bold; letter-spacing: 1px; }}
QPushButton#side_power {{
    background: transparent; border: 1px solid {line}; border-radius: 4px; padding: 0;
    outline: none;
}}
QPushButton#side_power:hover {{ background: {hover}; }}
QPushButton#side_power[armed="true"] {{ background: {active_bg}; border-color: {accent}; }}
QPushButton#side_power:disabled {{ background: transparent; border-color: {line}; }}
QPushButton#side_power:focus {{ outline: none; }}
QFrame#update_popup {{ background: {bg}; border: 1px solid {line}; border-radius: 6px; }}
QFrame#update_popup QLabel {{ background: transparent; }}
QPushButton#view_btn {{
    background: transparent; border: 1px solid {line}; border-radius: 0; padding: 0;
    outline: none;
}}
QPushButton#view_btn:hover {{ background: {hover}; }}
QPushButton#view_btn:checked {{ background: {line}; }}
QPushButton#view_btn:focus {{ outline: none; }}
QListWidget#result_list {{
    background: transparent; border: none; border-right: 1px solid {line}; outline: none;
    padding: 6px;
}}
QListWidget#result_list::item {{ border-radius: 6px; border: 1px solid transparent; }}
QListWidget#result_list::item:hover {{ background: {hover}; }}
QListWidget#result_list::item:selected {{ background: {hover}; border-color: {line}; }}
QWidget#result_row, QWidget#result_row QLabel {{ background: transparent; }}
QLabel#row_symbol {{ color: {text}; font-size: 10pt; font-weight: bold; }}
QLabel#card_symbol {{ color: {text}; font-size: 12pt; font-weight: bold; }}
QWidget#result_detail, QWidget#cards_host, QWidget#rule_strip {{ background: transparent; }}
QFrame#result_card, QFrame#detail_tile, QFrame#chart_slot, QFrame#detail_plan {{
    background: transparent; border: 1px solid {line}; border-radius: 6px;
}}
QFrame#result_card QLabel, QFrame#detail_tile QLabel, QFrame#detail_plan QLabel {{
    border: none;
}}
QLabel#detail_symbol {{ color: {text}; font-size: 17pt; font-weight: bold; }}
QLabel#view_key {{ color: {sub}; font-size: 8pt; }}
QFrame#screener_header {{ background: transparent; border-bottom: 1px solid {line}; }}
QLabel#page_tag {{
    color: {sub}; background: {line}; border-radius: 3px; padding: 1px 7px; font-size: 8pt;
}}
QLabel#rule_pill {{
    color: {text}; background: {hover}; border: 1px solid {line}; border-radius: 10px;
    padding: 2px 10px; font-size: 8.5pt;
}}
QPushButton#tx_pill {{
    background: transparent; color: {text}; border: 1px solid {line}; border-radius: 11px;
    padding: 0 10px; min-height: 22px; max-height: 22px; font-size: 8pt; outline: none;
}}
QPushButton#tx_pill:hover {{ background: {hover}; }}
QPushButton#tx_pill:checked {{ background: {line}; }}
QPushButton#tx_pill:focus {{ outline: none; }}
QPushButton#primary_btn {{
    background: {accent}; color: {bg}; border: 1px solid {accent}; font-weight: bold;
    padding: 0 14px; outline: none;
}}
QPushButton#primary_btn:hover {{ background: {text}; border-color: {text}; }}
QPushButton#primary_btn:disabled {{ background: {line}; color: {sub}; border-color: {line}; }}
QPushButton#primary_btn:focus {{ outline: none; }}
QFrame#run_stepper {{ border: 1px solid {line}; border-radius: 4px; }}
QPushButton#stepper_btn, QPushButton#stepper_date {{
    background: transparent; border: none; color: {text}; padding: 0 6px; outline: none;
}}
QPushButton#stepper_btn:hover, QPushButton#stepper_date:hover {{ background: {hover}; }}
QPushButton#stepper_btn:disabled {{ background: transparent; }}
QPushButton::menu-indicator {{ subcontrol-origin: padding; subcontrol-position: right center;
    right: 8px; }}
QPushButton#stepper_date::menu-indicator {{ image: none; width: 0; }}
QPushButton#stepper_btn:focus, QPushButton#stepper_date:focus {{ outline: none; }}
QLabel#latest_tag {{ color: {sub}; background: {line}; border-radius: 3px; padding: 1px 6px;
    font-size: 7.5pt; margin-right: 4px; }}
QFrame#side_drawer {{ background: {bg}; border-left: 1px solid {line}; }}
QLabel#drawer_title {{ color: {text}; font-size: 11pt; font-weight: bold; }}
QWidget#seg_group {{ background: {bg}; border: 1px solid {line}; border-radius: 6px; }}
QPushButton#filter_chip {{
    background: transparent; color: {sub}; border: none; border-radius: 4px;
    padding: 0 6px; min-height: 22px; max-height: 22px; font-size: 8pt; outline: none;
}}
QPushButton#filter_chip:hover {{ color: {text}; }}
QPushButton#filter_chip:checked {{ background: {line}; color: {text}; font-weight: bold; }}
QPushButton#filter_chip:focus {{ outline: none; }}
QListWidget#preset_list {{ background: transparent; border: none; outline: none; }}
QListWidget#preset_list::item {{ border-radius: 4px; margin: 0 6px; }}
QListWidget#preset_list::item:hover {{ background: {hover}; }}
QListWidget#preset_list::item:selected {{ background: {line}; }}
QWidget#preset_item, QWidget#preset_item QLabel {{ background: transparent; }}
QLabel#preset_name {{ color: {text}; font-size: 9.5pt; }}
QLabel#view_head {{ color: {sub}; font-size: 7.5pt; font-weight: bold; letter-spacing: 1px; }}
QFrame#icon_strip {{ background: {bg}; border: 1px solid {line}; border-radius: 6px; }}
QPushButton#strip_btn {{
    background: transparent; border: none; border-radius: 2px; outline: none;
}}
QPushButton#strip_btn:hover {{ background: {hover}; }}
QPushButton#strip_btn:checked {{ background: {active_bg}; border-left: 2px solid {accent}; }}
QPushButton#strip_btn:focus {{ outline: none; }}
QLabel#strip_badge {{
    background: {accent}; color: {bg}; border-radius: 7px; font-size: 7pt; font-weight: bold;
}}
QFrame#right_panel, QFrame#log_panel {{ background: {hover}; border: none; }}
QWidget#shell_gutter {{ background: {hover}; }}
QFrame#shell_card {{ border: 1px solid {line}; border-radius: 6px; }}
QFrame#preset_pane {{ background: transparent; border: none; }}
QLabel#details_key {{ color: {sub}; }}
QMdiArea#chart_mdi {{ background: {bg}; border: 1px solid {line}; }}
QMdiArea#chart_mdi QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; }}
QLabel#page_title {{ font-size: 13pt; font-weight: bold; }}
QLabel#page_meta {{ color: {sub}; padding-left: 8px; }}
QTabBar#exec_tabs::tab {{
    background: transparent; color: {sub}; border: none; border-bottom: 2px solid transparent;
    padding: 9px 2px; margin-right: 18px; font-size: 9.5pt;
}}
QTabBar#exec_tabs::tab:hover {{ color: {text}; }}
QTabBar#exec_tabs::tab:selected {{ color: {text}; border-bottom-color: {accent}; }}
QTreeWidget#exec_watch {{ background: transparent; border: none; outline: none; }}
QTreeWidget#exec_watch::item {{ min-height: 26px; border-bottom: 1px solid {line}; }}
QTreeWidget#exec_watch::item:hover {{ background: {hover}; }}
QTreeWidget#exec_watch::item:selected {{ background: {active_bg}; color: {text}; }}
QLabel#exec_chip {{
    color: {sub}; background: transparent; border: 1px solid {line}; border-radius: 4px;
    padding: 2px 8px; font-size: 8.5pt;
}}
QPushButton#mode_btn:checked {{ background: {active_bg}; color: {accent}; border-color: {accent}; }}
QFrame#settings_nav, QFrame#settings_card {{ border: 1px solid {line}; }}
QLabel#settings_head {{
    background: {hover}; border-bottom: 1px solid {line}; padding: 0 10px;
    min-height: 32px; max-height: 32px; font-family: "IBM Plex Mono", Consolas, monospace;
    font-size: 8pt; font-weight: bold;
}}
QLabel#data_pill {{
    border: 1px solid {sub}; color: {sub}; border-radius: 2px; padding: 0 6px;
    font-size: 7.5pt; font-weight: bold;
}}
QLabel#data_pct {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 20pt; font-weight: bold; }}
QLabel#data_pill[state="downloading"], QLabel#data_pct[state="downloading"] {{ color: {accent}; border-color: {accent}; }}
QLabel#data_pill[state="complete"], QLabel#data_pct[state="complete"] {{ color: #3cc583; border-color: #3cc583; }}
QLabel#data_pill[state="partial"], QLabel#data_pct[state="partial"] {{ color: #e8c14d; border-color: #e8c14d; }}
QLabel#data_pill[state="empty"] {{ color: #ef5a50; border-color: #ef5a50; }}
QProgressBar#data_bar {{ background: {hover}; border: none; border-radius: 1px; }}
QProgressBar#data_bar::chunk {{ background: {accent}; }}
QProgressBar#data_bar[state="complete"]::chunk {{ background: #3cc583; }}
QProgressBar#data_bar[state="partial"]::chunk {{ background: #e8c14d; }}
QLabel#data_badge {{
    background: {accent}; color: {bg}; border-radius: 7px; font-size: 7pt; font-weight: bold;
}}
QLabel#data_badge[state="complete"] {{ background: #3cc583; }}
QLabel#data_badge[state="partial"] {{ background: #e8c14d; }}
QLabel#panel_group {{
    color: {sub}; font-family: "IBM Plex Mono", Consolas, monospace; font-size: 7.5pt;
    font-weight: bold;
}}
"""


CARBON_QSS = _rgba_from_hex8(_to_carbon(MOCHA_QSS)) + _CARBON_EXTRA + _danger_qss(
    _CARBON.RED, _CARBON.MUTED, _CARBON.OVERLAY2
) + _sidebar_qss("#090b0e", _CARBON.OVERLAY, _CARBON.TEXT, _CARBON.SUBTEXT,
                 "#1a2029", "#2a2213", _CARBON.MAUVE)
MOCHA_QSS += _danger_qss(_MOCHA.RED, _MOCHA.MUTED, _MOCHA.OVERLAY2) + _sidebar_qss(
    "#11111b", _MOCHA.OVERLAY, _MOCHA.TEXT, _MOCHA.SUBTEXT, _MOCHA.OVERLAY, "#1a2d45", _MOCHA.BLUE
)
VS_CODE_QSS += _danger_qss(_VS.RED, _VS.MUTED, _VS.OVERLAY2) + _sidebar_qss(
    "#161616", _VS.OVERLAY2, _VS.TEXT, _VS.SUBTEXT, _VS.OVERLAY, "#04395e", _VS.TEXT
)
QSS = MOCHA_QSS

THEME_COLORS["carbon"] = {
    **{key: _to_carbon(value) for key, value in THEME_COLORS["mocha"].items()},
    "scope_pill_checked_bg": "#2a2213",
}


# ─────────────────────────────────────────────────────────────────────────────
# Theme registry + persistence + active-palette helpers
# ─────────────────────────────────────────────────────────────────────────────

THEMES: dict[str, str] = {
    "carbon": CARBON_QSS,
    "mocha":  MOCHA_QSS,
    "vscode": VS_CODE_QSS,
}
DEFAULT_THEME = "carbon"
_PALETTES: dict[str, type] = {"carbon": _CARBON, "mocha": _MOCHA, "vscode": _VS}

_THEME_PREF_FILE = Path.home() / ".usswing" / "theme_id"


def load_theme_id() -> str:
    try:
        tid = _THEME_PREF_FILE.read_text(encoding="utf-8").strip()
        return tid if tid in THEMES else DEFAULT_THEME
    except OSError:
        return DEFAULT_THEME


def save_theme_id(theme_id: str) -> None:
    _THEME_PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    _THEME_PREF_FILE.write_text(theme_id, encoding="utf-8")


def apply_theme(theme_id: str) -> None:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setStyleSheet(THEMES.get(theme_id, CARBON_QSS))


def active_palette() -> type:
    """Return the active theme's colour token class (_CARBON, _MOCHA or _VS)."""
    return _PALETTES[load_theme_id()]


class _ThemeProxy:
    """Transparent proxy — C.BLUE always returns the active theme's token at call time.

    Panels import C and use C.BLUE / C.OVERLAY / C.BTN_H as before.
    No panel code needs to call active_palette() manually for inline
    setStyleSheet() calls — C already does it automatically.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(active_palette(), name)


C = _ThemeProxy()


def colors() -> dict[str, str]:
    """Runtime colour roles for the active theme.

    Used by code paths QSS cannot reach: custom paintEvent, QStandardItem
    BackgroundRole, embedded HTML/JS chart rendering, and inline
    setStyleSheet calls that need a theme-aware hex value.

    Prefer QSS selectors (`#objectName` or `[property="value"]`) for any
    case where the styled widget is QSS-reachable.
    """
    return THEME_COLORS[load_theme_id()]


def asset_dir(sub: str) -> Path:
    """Return ``assets/<sub>`` for both source runs and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / sub  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3] / "assets" / sub


def load_fonts(font_dir: Path | None = None) -> None:
    """Register the bundled IBM Plex fonts; a bad file is skipped with a warning."""
    from PyQt6.QtGui import QFontDatabase

    for path in sorted((font_dir or asset_dir("fonts")).glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            _log.warning("[Theme] Could not load font %s", path.name)
