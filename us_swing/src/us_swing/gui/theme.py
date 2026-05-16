"""
Module: MD-GUI-001.001.M01 — Theme
Dark Catppuccin Mocha colour palette and global QSS stylesheet.
VS Code Dark theme available as an alternative (VS_CODE_QSS).
"""
from __future__ import annotations

from pathlib import Path


class C:
    """Colour token constants."""
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
    "NEW":           C.STATE_NEW,
    "PARTIAL_ENTRY": C.STATE_PARTIAL_ENTRY,
    "OPEN":          C.STATE_OPEN,
    "PARTIAL_EXIT":  C.STATE_PARTIAL_EXIT,
    "CLOSED":        C.STATE_CLOSED,
}

QSS = f"""
/* ═══════════════════════════════════════════════════════════
   GLOBAL  — Catppuccin Mocha · TIKR / Finviz terminal style
   ═══════════════════════════════════════════════════════════ */
QMainWindow, QDialog, QWidget {{
    background: {C.BG};
    color: {C.TEXT};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}}

/* ── Compact frameless title bar ─────────────────────────── */
QWidget#title_bar {{
    background: #11111b;
    border-bottom: 1px solid {C.OVERLAY};
}}
QLabel#top_brand {{
    color: {C.BLUE};
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0 4px 0 8px;
}}
QLabel#user_chip  {{ color: {C.TEXT};   font-size: 8pt; padding: 0 4px; }}

/* ── Horizontal tab nav (inside title bar) ────────────────── */
QPushButton#tab_btn {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: {C.MUTED};
    font-size: 8pt;
    padding: 0 10px;
    min-height: 38px;
    max-height: 38px;
    outline: none;
}}
QPushButton#tab_btn:hover {{
    color: {C.TEXT};
    background: {C.OVERLAY}22;
    outline: none;
}}
QPushButton#tab_btn:checked {{
    color: {C.TEXT};
    background: {C.OVERLAY2}55;
    border-bottom: none;
    border-radius: 4px;
    font-weight: bold;
    outline: none;
}}
QPushButton#tab_btn:focus {{
    outline: none;
}}
QPushButton#tab_btn:checked:focus {{
    outline: none;
}}


/* ── Accent underline below title bar ─────────────────────── */
QFrame#accent_line {{ color: {C.OVERLAY2}; max-height: 2px; }}

/* ── Admin context bar (username / market watch strip) ────── */
QWidget#admin_ctx_bar {{
    background: {C.SURFACE};
    border-bottom: 1px solid {C.OVERLAY};
}}

/* ── Screener toolbar + preset pane ──────────────────────── */
QFrame#screener_toolbar {{
    background: {C.BG};
    border-bottom: 1px solid {C.OVERLAY};
}}
QFrame#preset_pane {{
    background: {C.SURFACE};
    border-right: 1px solid {C.OVERLAY};
}}

/* ── AI Transcript panel ──────────────────────────────────── */
QFrame#transcript_header_bar {{
    background: {C.SURFACE};
    border-top: 1px solid {C.OVERLAY};
}}

/* ── Dashboard QTabWidget ─────────────────────────────────────── */
QTabWidget#dash_tabs::pane {{
    border: 1px solid {C.OVERLAY};
    border-radius: 4px;
    background: {C.BG};
}}
QTabWidget#dash_tabs > QTabBar::tab {{
    background: {C.SURFACE};
    color: {C.MUTED};
    font-size: 9pt;
    padding: 6px 16px;
    border: 1px solid {C.OVERLAY};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabWidget#dash_tabs > QTabBar::tab:selected {{
    background: {C.BG};
    color: {C.BLUE};
    border-bottom: 2px solid {C.BLUE};
    font-weight: bold;
}}
QTabWidget#dash_tabs > QTabBar::tab:hover:!selected {{
    color: {C.TEXT};
    background: {C.OVERLAY};
}}

/* ── Stat cards (TIKR KPI style) ─────────────────────────── */
QFrame#stat_card {{
    background: {C.SURFACE};
    border: 1px solid {C.OVERLAY};
    border-radius: 8px;
    padding: 10px;
}}
QFrame#stat_card:hover {{
    border: 1px solid {C.OVERLAY2};
}}
QWidget#stat_card_inner {{
    background: transparent;
}}
QWidget#stat_card_inner QLabel {{
    background: transparent;
}}

/* ── Screener chip / badge row ────────────────────────────── */
QFrame#filter_chip {{
    background: {C.OVERLAY};
    border: 1px solid {C.OVERLAY2};
    border-radius: 12px;
    padding: 2px 10px;
}}
QFrame#filter_chip[active="true"] {{
    background: #1a2d45;
    border: 1px solid {C.BLUE};
}}

/* ── Mode/status badges ───────────────────────────────────── */
QLabel#mode_live {{
    background: #331a1a;
    color: {C.RED};
    border: 1px solid {C.RED};
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}}
QLabel#mode_paper {{
    background: #1a2d45;
    color: {C.BLUE};
    border: 1px solid {C.BLUE};
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}}
QLabel#can_enter_yes {{
    background: #1a3326;
    color: {C.GREEN};
    border: 1px solid {C.GREEN};
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}}
QLabel#can_enter_no {{
    background: #331a1a;
    color: {C.RED};
    border: 1px solid {C.RED};
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}}

/* ── (legacy) Tab widget — kept for any residual usage ────── */
QTabWidget::pane {{
    border: 1px solid {C.OVERLAY};
    background: {C.BG};
}}
QTabBar::tab {{
    background: {C.SURFACE};
    color: {C.MUTED};
    padding: 8px 22px;
    border: 1px solid {C.OVERLAY};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 9pt;
}}
QTabBar::tab:selected {{
    background: {C.BG};
    color: {C.TEXT};
    border-bottom: 2px solid {C.BLUE};
}}
QTabBar::tab:hover:!selected {{
    background: {C.OVERLAY};
    color: {C.TEXT};
}}
QTableView, QTreeView {{
    background: {C.SURFACE};
    alternate-background-color: {C.BG};
    color: {C.TEXT};
    gridline-color: {C.OVERLAY};
    border: 1px solid {C.OVERLAY};
    border-radius: 4px;
    selection-background-color: {C.OVERLAY2};
    selection-color: {C.TEXT};
    outline: none;
}}
QTableView::item, QTreeView::item {{
    padding: 3px 6px;
}}
QHeaderView::section {{
    background: {C.OVERLAY};
    color: {C.SUBTEXT};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {C.OVERLAY2};
    border-bottom: 1px solid {C.OVERLAY2};
    font-weight: bold;
    font-size: 8pt;
    text-transform: uppercase;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
    background: {C.OVERLAY};
    border: 1px solid {C.OVERLAY2};
    border-radius: 4px;
    color: {C.TEXT};
    padding: 0 8px;
    min-height: {C.INPUT_H}px;
    max-height: {C.INPUT_H}px;
    outline: none;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{
    border: 1px solid {C.BLUE};
    outline: none;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {C.OVERLAY};
    selection-background-color: {C.OVERLAY2};
    color: {C.TEXT};
    border: 1px solid {C.OVERLAY2};
}}
QPushButton {{
    background: {C.OVERLAY};
    border: 1px solid {C.OVERLAY2};
    border-radius: 4px;
    color: {C.TEXT};
    padding: 0 16px;
    font-size: 9pt;
    min-height: {C.BTN_H}px;
    max-height: {C.BTN_H}px;
    outline: none;
}}
QPushButton:focus {{
    outline: none;
}}
QPushButton:hover {{
    background: {C.OVERLAY2};
    border: 1px solid {C.BLUE};
}}
QPushButton:pressed {{
    background: {C.OVERLAY2};
}}
QPushButton:disabled {{
    color: {C.MUTED};
    background: {C.SURFACE};
    border-color: {C.OVERLAY};
}}
QPushButton#buy_btn {{
    background: #1a3326;
    border: 1px solid {C.GREEN};
    color: {C.GREEN};
    font-weight: bold;
}}
QPushButton#buy_btn:hover {{ background: #223d2e; }}
QPushButton#close_btn {{
    background: #331a1a;
    border: 1px solid {C.RED};
    color: {C.RED};
}}
QPushButton#close_btn:hover {{ background: #3d2222; }}
QPushButton#run_btn {{
    background: #1a2d45;
    border: 1px solid {C.BLUE};
    color: {C.BLUE};
    font-weight: bold;
    padding: 0 24px;
    min-height: {C.BTN_H}px;
    max-height: {C.BTN_H}px;
}}
QPushButton#run_btn:hover {{ background: #1e3658; }}
QPushButton#run_btn:disabled {{ color: {C.MUTED}; background: {C.OVERLAY}44; border-color: {C.OVERLAY}; }}
QPushButton#add_btn {{
    background: #2a1a3a;
    border: 1px solid {C.MAUVE};
    color: {C.MAUVE};
    padding: 0 8px;
    font-size: 9pt;
}}
QPushButton#add_btn:hover {{ background: #33214d; }}
QPushButton#add_btn:disabled {{ color: {C.MUTED}; background: {C.OVERLAY}44; border-color: {C.OVERLAY}; }}
QPushButton#danger_btn {{
    background: {C.RED}22;
    border: 1px solid {C.RED};
    color: {C.RED};
}}
QPushButton#danger_btn:hover {{ background: #3d2222; }}

/* ── Reusable named colour variants (standard 28 px height) ── */
QPushButton#btn_green {{
    background: #1a3d2a;
    color: {C.GREEN};
    border: 1px solid {C.GREEN};
    border-radius: 4px;
    padding: 0 16px;
}}
QPushButton#btn_green:hover {{ background: #1e4a32; }}
QPushButton#btn_blue {{
    background: #1a2d45;
    color: {C.BLUE};
    border: 1px solid {C.BLUE};
    border-radius: 4px;
    font-size: 9pt;
}}
QPushButton#btn_blue:hover {{ background: #1e3558; }}

/* ── Compact variants ({C.BTN_H_SM} px — group-card header controls) ─ */
QPushButton#btn_add_screener {{
    background: #1a3d2a;
    color: {C.GREEN};
    border: 1px solid {C.GREEN}66;
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 10px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_add_screener:hover {{ background: #1e4a32; border-color: {C.GREEN}; }}
QPushButton#btn_configure {{
    background: transparent;
    color: {C.SUBTEXT};
    border: 1px solid {C.OVERLAY2};
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_configure:hover:enabled {{ color: {C.BLUE}; border-color: {C.BLUE}; }}
QPushButton#btn_configure:disabled {{ color: {C.OVERLAY2}; border-color: {C.OVERLAY}; }}
QPushButton#btn_remove {{
    background: transparent;
    color: {C.MUTED};
    border: 1px solid {C.OVERLAY2};
    border-radius: 4px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_remove:hover {{ color: {C.RED}; border-color: {C.RED}; }}

/* ── Square nav arrow buttons (toolbar date navigation) ────── */
QPushButton#btn_nav {{
    background: {C.OVERLAY};
    color: {C.TEXT};
    border: 1px solid {C.OVERLAY2};
    border-radius: 4px;
    font-size: 12pt;
    padding: 0;
}}
QPushButton#btn_nav:hover {{ background: {C.OVERLAY2}; border-color: {C.BLUE}; }}
QPushButton#btn_nav:disabled {{ color: {C.MUTED}; background: {C.OVERLAY}44; border-color: {C.OVERLAY}; }}

QProgressBar {{
    background: {C.SURFACE};
    border: 1px solid {C.OVERLAY};
    border-radius: 3px;
    max-height: 10px;
    text-align: center;
    font-size: 7pt;
    color: {C.TEXT};
}}
QProgressBar::chunk {{
    background: {C.BLUE};
    border-radius: 3px;
}}
QGroupBox {{
    border: 1px solid {C.OVERLAY};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
    color: {C.SUBTEXT};
    font-weight: bold;
    font-size: 9pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    background: {C.BG};
    padding: 0 4px;
}}
QCheckBox {{
    color: {C.TEXT};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C.OVERLAY2};
    border-radius: 3px;
    background: {C.SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {C.BLUE};
    border-color: {C.BLUE};
}}
QStatusBar {{
    background: {C.SURFACE};
    color: {C.MUTED};
    border-top: 1px solid {C.OVERLAY};
    font-size: 9pt;
    min-height: 28px;
}}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{
    background: {C.OVERLAY};
    width: 2px;
}}
QScrollBar:vertical {{
    background: {C.SURFACE};
    width: 10px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C.OVERLAY2};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C.SURFACE};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {C.OVERLAY2};
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QTextEdit {{
    background: {C.SURFACE};
    color: {C.TEXT};
    border: 1px solid {C.OVERLAY};
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    outline: none;
}}
QListWidget {{
    background: {C.SURFACE};
    border: 1px solid {C.OVERLAY};
    border-radius: 4px;
    outline: none;
}}
QListWidget::item:focus {{
    outline: none;
    border: none;
}}
QLabel {{ color: {C.TEXT}; }}
QToolTip {{
    background: {C.OVERLAY};
    color: {C.TEXT};
    border: 1px solid {C.OVERLAY2};
    padding: 4px;
}}
"""

# ─────────────────────────────────────────────────────────────────────────────
# VS Code Dark theme
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

    BTN_H    = C.BTN_H
    BTN_H_SM = C.BTN_H_SM
    INPUT_H  = C.INPUT_H


VS_CODE_QSS = f"""
/* ═══════════════════════════════════════════════════════════
   GLOBAL  — VS Code Dark (inspired by Visual Studio / ACU)
   ═══════════════════════════════════════════════════════════ */
QMainWindow, QDialog, QWidget {{
    background: {_VS.BG};
    color: {_VS.TEXT};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}}

/* ── Compact frameless title bar ─────────────────────────── */
QWidget#title_bar {{
    background: #161616;
    border-bottom: 1px solid {_VS.TEXT};
}}
QLabel#top_brand {{
    color: #ffffff;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 0 4px 0 8px;
}}
QLabel#user_chip  {{ color: {_VS.TEXT}; font-size: 8pt; padding: 0 4px; }}

/* ── Horizontal tab nav (inside title bar) ────────────────── */
QPushButton#tab_btn {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: {_VS.MUTED};
    font-size: 8pt;
    padding: 0 10px;
    min-height: 38px;
    max-height: 38px;
    outline: none;
}}
QPushButton#tab_btn:hover {{
    color: {_VS.TEXT};
    background: {_VS.OVERLAY2}33;
    outline: none;
}}
QPushButton#tab_btn:checked {{
    color: {_VS.TEXT};
    background: {_VS.OVERLAY2}55;
    border-bottom: none;
    border-radius: 4px;
    font-weight: bold;
    outline: none;
}}
QPushButton#tab_btn:focus {{ outline: none; }}
QPushButton#tab_btn:checked:focus {{ outline: none; }}

/* ── Accent underline below title bar ─────────────────────── */
QFrame#accent_line {{ color: {_VS.SUBTEXT}; max-height: 2px; }}

/* ── Admin context bar (username / market watch strip) ────── */
QWidget#admin_ctx_bar {{
    background: {_VS.SURFACE};
    border-bottom: 1px solid {_VS.OVERLAY2};
}}

/* ── Screener toolbar + preset pane ──────────────────────── */
QFrame#screener_toolbar {{
    background: {_VS.BG};
    border-bottom: 1px solid {_VS.OVERLAY2};
}}
QFrame#preset_pane {{
    background: {_VS.SURFACE};
    border-right: 1px solid {_VS.OVERLAY2};
}}

/* ── AI Transcript panel ──────────────────────────────────── */
QFrame#transcript_header_bar {{
    background: {_VS.SURFACE};
    border-top: 1px solid {_VS.OVERLAY2};
}}

/* ── Dashboard QTabWidget ─────────────────────────────────── */
QTabWidget#dash_tabs::pane {{
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 4px;
    background: {_VS.BG};
}}
QTabWidget#dash_tabs > QTabBar::tab {{
    background: {_VS.SURFACE};
    color: {_VS.MUTED};
    font-size: 9pt;
    padding: 6px 16px;
    border: 1px solid {_VS.OVERLAY2};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabWidget#dash_tabs > QTabBar::tab:selected {{
    background: {_VS.BG};
    color: {_VS.SUBTEXT};
    border-bottom: 2px solid {_VS.SUBTEXT};
    font-weight: bold;
}}
QTabWidget#dash_tabs > QTabBar::tab:hover:!selected {{
    color: {_VS.TEXT};
    background: #2a2d2e;
}}

/* ── Stat cards ───────────────────────────────────────────── */
QFrame#stat_card {{
    background: {_VS.SURFACE};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 4px;
    padding: 10px;
}}
QFrame#stat_card:hover {{
    border: 1px solid {_VS.SUBTEXT};
}}
QWidget#stat_card_inner {{ background: transparent; }}
QWidget#stat_card_inner QLabel {{ background: transparent; }}

/* ── Screener chip / badge row ────────────────────────────── */
QFrame#filter_chip {{
    background: {_VS.OVERLAY};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 12px;
    padding: 2px 10px;
}}
QFrame#filter_chip[active="true"] {{
    background: #1a2535;
    border: 1px solid {_VS.BLUE};
}}

/* ── Mode/status badges ───────────────────────────────────── */
QLabel#mode_live {{
    background: #2e1a1a;
    color: {_VS.RED};
    border: 1px solid {_VS.RED};
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}}
QLabel#mode_paper {{
    background: #1a2535;
    color: {_VS.BLUE};
    border: 1px solid {_VS.BLUE};
    border-radius: 8px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 8pt;
}}
QLabel#can_enter_yes {{
    background: #1a2e2e;
    color: {_VS.GREEN};
    border: 1px solid {_VS.GREEN};
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}}
QLabel#can_enter_no {{
    background: #2e1a1a;
    color: {_VS.RED};
    border: 1px solid {_VS.RED};
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 9pt;
}}

/* ── Tab widget (generic) ─────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {_VS.OVERLAY2};
    background: {_VS.BG};
}}
QTabBar::tab {{
    background: {_VS.SURFACE};
    color: {_VS.MUTED};
    padding: 8px 22px;
    border: 1px solid {_VS.OVERLAY2};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 9pt;
}}
QTabBar::tab:selected {{
    background: {_VS.BG};
    color: {_VS.SUBTEXT};
    border-bottom: 2px solid {_VS.SUBTEXT};
}}
QTabBar::tab:hover:!selected {{
    background: #2a2d2e;
    color: {_VS.TEXT};
}}

/* ── Tables / trees ───────────────────────────────────────── */
QTableView, QTreeView {{
    background: {_VS.SURFACE};
    alternate-background-color: {_VS.BG};
    color: {_VS.TEXT};
    gridline-color: {_VS.OVERLAY2};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    selection-background-color: #264f78;
    selection-color: {_VS.TEXT};
    outline: none;
}}
QTableView::item, QTreeView::item {{ padding: 3px 6px; }}
QHeaderView::section {{
    background: {_VS.OVERLAY};
    color: {_VS.SUBTEXT};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {_VS.OVERLAY2};
    border-bottom: 1px solid {_VS.OVERLAY2};
    font-weight: bold;
    font-size: 8pt;
    text-transform: uppercase;
}}

/* ── Inputs ───────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
    background: {_VS.INPUT};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    color: {_VS.TEXT};
    padding: 0 8px;
    min-height: {C.INPUT_H}px;
    max-height: {C.INPUT_H}px;
    outline: none;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{
    border: 1px solid {_VS.BLUE};
    outline: none;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {_VS.SURFACE};
    selection-background-color: #264f78;
    color: {_VS.TEXT};
    border: 1px solid {_VS.BLUE};
    outline: none;
}}

/* ── Buttons ──────────────────────────────────────────────── */
QPushButton {{
    background: {_VS.OVERLAY};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    color: {_VS.TEXT};
    padding: 0 16px;
    font-size: 9pt;
    min-height: {C.BTN_H}px;
    max-height: {C.BTN_H}px;
    outline: none;
}}
QPushButton:focus {{ outline: none; }}
QPushButton:hover {{
    background: #3a3d41;
    border: 1px solid {_VS.SUBTEXT};
    color: #ffffff;
}}
QPushButton:pressed {{ background: {_VS.BLUE}; color: #ffffff; border-color: {_VS.BLUE}; }}
QPushButton:disabled {{ color: {_VS.MUTED}; background: {_VS.SURFACE}; border-color: {_VS.OVERLAY}; }}

QPushButton#buy_btn {{
    background: #1a2e2e;
    border: 1px solid {_VS.GREEN};
    color: {_VS.GREEN};
    font-weight: bold;
}}
QPushButton#buy_btn:hover {{ background: #1e3535; }}
QPushButton#close_btn {{
    background: #2e1a1a;
    border: 1px solid {_VS.RED};
    color: {_VS.RED};
}}
QPushButton#close_btn:hover {{ background: #3d2222; }}
QPushButton#run_btn {{
    background: {_VS.OVERLAY};
    border: 1px solid {_VS.OVERLAY2};
    color: {_VS.TEXT};
    font-weight: bold;
    padding: 0 24px;
    min-height: {C.BTN_H}px;
    max-height: {C.BTN_H}px;
}}
QPushButton#run_btn:hover {{ background: {_VS.OVERLAY2}; color: #ffffff; }}
QPushButton#run_btn:disabled {{ color: {_VS.MUTED}; background: {_VS.OVERLAY}; border-color: {_VS.OVERLAY2}; }}
QPushButton#add_btn {{
    background: #291a2e;
    border: 1px solid {_VS.MAUVE};
    color: {_VS.MAUVE};
    padding: 0 8px;
    font-size: 9pt;
}}
QPushButton#add_btn:hover {{ background: #32203a; }}
QPushButton#add_btn:disabled {{ color: {_VS.MUTED}; background: {_VS.OVERLAY}; border-color: {_VS.OVERLAY2}; }}
QPushButton#danger_btn {{
    background: #2e1a1a;
    border: 1px solid {_VS.RED};
    color: {_VS.RED};
}}
QPushButton#danger_btn:hover {{ background: #3d2222; }}

QPushButton#btn_green {{
    background: #1a2e2e;
    color: {_VS.GREEN};
    border: 1px solid {_VS.GREEN};
    border-radius: 2px;
    padding: 0 16px;
}}
QPushButton#btn_green:hover {{ background: #1e3535; }}
QPushButton#btn_blue {{
    background: #1a2535;
    color: {_VS.BLUE};
    border: 1px solid {_VS.BLUE};
    border-radius: 2px;
    font-size: 9pt;
}}
QPushButton#btn_blue:hover {{ background: #1e2e40; }}

QPushButton#btn_add_screener {{
    background: #1a2e2e;
    color: {_VS.GREEN};
    border: 1px solid {_VS.GREEN}66;
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 10px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_add_screener:hover {{ background: #1e3535; border-color: {_VS.GREEN}; }}
QPushButton#btn_configure {{
    background: transparent;
    color: {_VS.SUBTEXT};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_configure:hover:enabled {{ color: {_VS.TEXT}; border-color: {_VS.SUBTEXT}; }}
QPushButton#btn_configure:disabled {{ color: {_VS.OVERLAY2}; border-color: {_VS.OVERLAY}; }}
QPushButton#btn_remove {{
    background: transparent;
    color: {_VS.MUTED};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    font-size: 8pt;
    padding: 0 8px;
    min-height: {C.BTN_H_SM}px;
    max-height: {C.BTN_H_SM}px;
}}
QPushButton#btn_remove:hover {{ color: {_VS.RED}; border-color: {_VS.RED}; }}

QPushButton#btn_nav {{
    background: {_VS.OVERLAY};
    color: {_VS.TEXT};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    font-size: 12pt;
    padding: 0;
}}
QPushButton#btn_nav:hover {{ background: {_VS.OVERLAY2}; border-color: {_VS.SUBTEXT}; }}
QPushButton#btn_nav:disabled {{ color: {_VS.MUTED}; background: {_VS.SURFACE}; border-color: {_VS.OVERLAY}; }}

/* ── Progress bar ─────────────────────────────────────────── */
QProgressBar {{
    background: {_VS.SURFACE};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    max-height: 10px;
    text-align: center;
    font-size: 7pt;
    color: {_VS.TEXT};
}}
QProgressBar::chunk {{ background: {_VS.BLUE}; border-radius: 2px; }}

/* ── Group box ────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 6px;
    color: {_VS.SUBTEXT};
    font-weight: bold;
    font-size: 9pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    background: {_VS.BG};
    padding: 0 4px;
}}

/* ── Checkbox ─────────────────────────────────────────────── */
QCheckBox {{ color: {_VS.TEXT}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    background: {_VS.INPUT};
}}
QCheckBox::indicator:checked {{ background: {_VS.BLUE}; border-color: {_VS.BLUE}; }}
QCheckBox::indicator:hover {{ border-color: {_VS.BLUE}; }}

/* ── Status bar ───────────────────────────────────────────── */
QStatusBar {{
    background: {_VS.BLUE};
    color: #ffffff;
    border-top: none;
    font-size: 9pt;
    min-height: 28px;
}}
QStatusBar::item {{ border: none; }}

/* ── Splitter ─────────────────────────────────────────────── */
QSplitter::handle {{ background: {_VS.OVERLAY2}; width: 1px; }}
QSplitter::handle:hover {{ background: {_VS.BLUE}; }}

/* ── Scrollbars ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {_VS.BG};
    width: 10px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #424242;
    border-radius: 5px;
    min-height: 20px;
    margin: 1px;
}}
QScrollBar::handle:vertical:hover {{ background: #686868; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {_VS.BG};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: #424242;
    border-radius: 5px;
    min-width: 20px;
    margin: 1px;
}}
QScrollBar::handle:horizontal:hover {{ background: #686868; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Text / list widgets ──────────────────────────────────── */
QTextEdit {{
    background: {_VS.SURFACE};
    color: {_VS.TEXT};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    outline: none;
}}
QListWidget {{
    background: {_VS.SURFACE};
    border: 1px solid {_VS.OVERLAY2};
    border-radius: 2px;
    outline: none;
}}
QListWidget::item:focus {{ outline: none; border: none; }}
QListWidget::item:selected {{ background: #264f78; color: {_VS.TEXT}; }}
QListWidget::item:hover:!selected {{ background: #2a2d2e; }}

QLabel {{ color: {_VS.TEXT}; }}
QToolTip {{
    background: {_VS.SURFACE};
    color: {_VS.TEXT};
    border: 1px solid {_VS.OVERLAY2};
    padding: 4px 8px;
    font-size: 9pt;
}}
"""

# ── Theme ID for VS Code Dark position state colours ─────────────────────────
VS_STATE_COLORS: dict[str, str] = {
    "NEW":           _VS.STATE_NEW,
    "PARTIAL_ENTRY": _VS.STATE_PARTIAL_ENTRY,
    "OPEN":          _VS.STATE_OPEN,
    "PARTIAL_EXIT":  _VS.STATE_PARTIAL_EXIT,
    "CLOSED":        _VS.STATE_CLOSED,
}

THEMES: dict[str, str] = {
    "mocha":  QSS,
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
        app.setStyleSheet(THEMES.get(theme_id, QSS))


def active_palette() -> type:
    """Return C (Mocha) or _VS (VS Code Dark) colour tokens for the active theme."""
    return _VS if load_theme_id() == "vscode" else C  # type: ignore[return-value]
