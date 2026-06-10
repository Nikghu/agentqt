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

from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Catppuccin Mocha — colour tokens + sizing
# ─────────────────────────────────────────────────────────────────────────────

class _MOCHA:
    """Mocha colour tokens + universal widget sizing constants."""
    BG       = "#1e1e2e"
    SURFACE  = "#181825"
    OVERLAY  = "#313244"
    OVERLAY2 = "#45475a"
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
        # Footer feed-toggle pill (custom paintEvent).
        "feed_hover_border":     "#6e7aff",
        "feed_hover_text":       "#b0b8ff",
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
        "feed_hover_border":     "#9d9d9d",
        "feed_hover_text":       "#d4d4d4",
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
# Theme registry + persistence + active-palette helpers
# ─────────────────────────────────────────────────────────────────────────────

THEMES: dict[str, str] = {
    "mocha":  MOCHA_QSS,
    "vscode": VS_CODE_QSS,
}

_THEME_PREF_FILE = Path.home() / ".usswing" / "theme_id"


def load_theme_id() -> str:
    try:
        tid = _THEME_PREF_FILE.read_text(encoding="utf-8").strip()
        return tid if tid in THEMES else "mocha"
    except OSError:
        return "mocha"


def save_theme_id(theme_id: str) -> None:
    _THEME_PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    _THEME_PREF_FILE.write_text(theme_id, encoding="utf-8")


def apply_theme(theme_id: str) -> None:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(THEMES.get(theme_id, MOCHA_QSS))


def active_palette() -> type:
    """Return the active theme's colour token class (_MOCHA or _VS)."""
    return _VS if load_theme_id() == "vscode" else _MOCHA  # type: ignore[return-value]


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
