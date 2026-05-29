"""
Module: MD-SCR-014.004.M22 — gui/ai_transcript_panel.py
Parent SRD: SRD-SCR-014.004, SRD-SCR-014.005, SRD-SCR-014.007
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont, QTextOption
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.theme import C, load_theme_id

if TYPE_CHECKING:
    from us_swing.screener.storage import AITranscriptTurn  # noqa: F401

# VS Code Dark palette for transcript cards (mirrors _VS in theme.py)
_VSD = {
    "blue":    "#007acc",
    "green":   "#4ec9b0",
    "yellow":  "#cca700",
    "muted":   "#6d6d6d",
    "bg":      "#1e1e1e",
    "surface": "#252526",
    "ovl2":    "#454545",
    "user_bg": "#2a2d2e",
}


def _build_role_styles(vs: bool) -> dict[str, tuple[str, str, str, str]]:
    """Return role-style map for the active theme.

    Each entry: (display_text, avatar_color, card_bg, border_css).
    """
    if vs:
        b, g, y, mu = _VSD["blue"], _VSD["green"], _VSD["yellow"], _VSD["muted"]
        bg, sf, ov2 = _VSD["bg"], _VSD["surface"], _VSD["ovl2"]
        return {
            "user":        ("USER",      b,  _VSD["user_bg"], f"border: 1px solid {ov2}; border-radius: 4px;"),
            "assistant":   ("ASSISTANT", g,  sf,              f"border: 1px solid {ov2}; border-radius: 4px;"),
            "system":      ("SYSTEM",    mu, bg,              f"border: 1px dashed {ov2}; border-radius: 4px;"),
            "tool_result": ("TOOL",      y,  bg,
                            f"border-left: 4px solid {y};"
                            " border-top: none; border-right: none; border-bottom: none;"
                            " border-radius: 0px;"),
        }
    return {
        "user":        ("USER",      C.BLUE,   "#1a2d45",  f"border: 1px solid {C.BLUE};    border-radius: 8px;"),
        "assistant":   ("ASSISTANT", C.GREEN,  C.SURFACE,  f"border: 1px solid {C.OVERLAY}; border-radius: 8px;"),
        "system":      ("SYSTEM",    C.MUTED,  C.BG,       f"border: 1px dashed {C.OVERLAY}; border-radius: 8px;"),
        "tool_result": ("TOOL",      C.YELLOW, C.BG,
                        f"border-left: 4px solid {C.YELLOW};"
                        " border-top: none; border-right: none; border-bottom: none;"
                        " border-radius: 0px;"),
    }


def _screening_results_html(content: str) -> str | None:
    """Return an HTML table if content is a JSON list of screening results, else None."""
    s = content.strip()
    for i, ch in enumerate(s):
        if ch in ("{", "["):
            s = s[i:]
            break
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, list) or not data:
        return None
    if not all(isinstance(item, dict) and "symbol" in item for item in data):
        return None

    rows: list[str] = []
    for item in data:
        symbol: str = item.get("symbol", "?")
        score: float = float(item.get("score", 0.0))
        reasoning: str = item.get("reasoning", "")
        pct = int(score * 100)

        if score >= 0.70:
            color = "#a6e3a1"  # green
        elif score >= 0.50:
            color = "#f9e2af"  # yellow
        elif score >= 0.35:
            color = "#fab387"  # orange
        else:
            color = "#f38ba8"  # red

        rows.append(
            f'<tr style="border-bottom:1px solid #313244;">'
            f'<td style="padding:6px 8px;font-weight:bold;color:{color};white-space:nowrap;">{symbol}</td>'
            f'<td style="padding:6px 4px;color:{color};white-space:nowrap;">{pct}%</td>'
            f'<td style="padding:6px 8px;color:#cdd6f4;">{reasoning}</td>'
            f'</tr>'
        )

    return (
        '<table style="width:100%;border-collapse:collapse;font-family:Consolas,monospace;font-size:9pt;">'
        + "".join(rows)
        + "</table>"
    )


# ---------------------------------------------------------------------------
# _TurnBlock
# ---------------------------------------------------------------------------

class _TurnBlock(QFrame):
    """Renders a single conversation turn as a styled chat card."""

    def __init__(self, turn: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("turn_block")

        role: str = getattr(turn, "role", "user")
        content: str = getattr(turn, "content", "")
        tool_name: str | None = getattr(turn, "tool_name", None)
        tokens_input: int = int(getattr(turn, "tokens_input", 0))
        tokens_output: int = int(getattr(turn, "tokens_output", 0))
        sent_at: str | None = getattr(turn, "sent_at", None)
        received_at: str | None = getattr(turn, "received_at", None)
        response_time_ms: int = getattr(turn, "response_time_ms", 0)

        _is_vs = load_theme_id() == "vscode"
        _styles = _build_role_styles(_is_vs)
        _focus_blue = _VSD["blue"] if _is_vs else C.BLUE
        _unknown_bg  = _VSD["bg"]   if _is_vs else C.BG
        _unknown_ov  = _VSD["ovl2"] if _is_vs else C.OVERLAY
        _unknown_mu  = _VSD["muted"] if _is_vs else C.MUTED
        _unknown_r   = "4px" if _is_vs else "8px"

        display_text, avatar_color, card_bg, border_css = _styles.get(
            role,
            ("UNKNOWN", _unknown_mu, _unknown_bg,
             f"border: 1px solid {_unknown_ov}; border-radius: {_unknown_r};"),
        )

        is_system = role == "system"
        is_assistant = role == "assistant"
        is_tool_result = role == "tool_result"

        self.setStyleSheet(
            f"QFrame#turn_block {{"
            f"  {border_css}"
            f"  background: {card_bg};"
            f"  margin-bottom: 4px;"
            f"}}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        # ── role row ────────────────────────────────────────────
        role_row = QHBoxLayout()
        role_row.setContentsMargins(0, 0, 0, 0)
        role_row.setSpacing(6)

        # Avatar dot
        avatar = QLabel()
        avatar.setFixedSize(10, 10)
        avatar.setStyleSheet(
            f"background: {avatar_color};"
            f"border-radius: 5px;"
            f"border: none;"
        )
        role_row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignVCenter)

        # Role label — shown only for system and tool_result
        if is_system or is_tool_result:
            role_label = QLabel(display_text)
            role_font = QFont()
            role_font.setBold(True)
            role_font.setPointSize(9)
            if is_system:
                role_font.setItalic(True)
            role_label.setFont(role_font)
            role_label.setStyleSheet(
                f"color: {avatar_color}; background: transparent; border: none;"
            )
            role_row.addWidget(role_label)

        # Tool name label (tool_result only)
        if tool_name is not None:
            tool_name_label = QLabel(tool_name)
            tool_name_label.setStyleSheet(
                f"color: {C.MUTED}; font-size: 8pt; background: transparent; border: none;"
            )
            role_row.addWidget(tool_name_label)

        role_row.addStretch()

        # Timestamp label — right side of role row (user/assistant only)
        if role in ("user", "assistant"):
            ts_str = received_at if role == "assistant" else sent_at
            if ts_str and len(ts_str) >= 19:
                ts_label = QLabel(ts_str[11:19])  # HH:MM:SS slice from ISO string
                ts_label.setStyleSheet(
                    f"color: {C.MUTED}; font-size: 8pt; background: transparent; border: none;"
                )
                role_row.addWidget(ts_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._content_widget: QTextEdit | QLabel | None = None
        self._toggle_btn: QPushButton | None = None

        # System toggle button sits in the role row
        if is_system:
            toggle_btn = QPushButton("Show system prompt ▼")
            toggle_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: transparent;"
                f"  color: {C.MUTED};"
                f"  border: none;"
                f"  font-size: 8pt;"
                f"  text-align: right;"
                f"  outline: none;"
                f"}}"
                f"QPushButton:focus {{"
                f"  outline: none;"
                f"  border: 1px solid {C.BLUE};"
                f"  border-radius: 3px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  color: {C.SUBTEXT};"
                f"}}"
            )
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # toggle_btn clicked → _toggle_content
            toggle_btn.clicked.connect(self._toggle_content)
            role_row.addWidget(toggle_btn)
            self._toggle_btn = toggle_btn

        outer.addLayout(role_row)

        # ── content widget — varies by role ─────────────────────
        if role == "user":
            # Selectable plain label
            content_label = QLabel(content)
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            content_label.setStyleSheet(
                f"color: {C.TEXT};"
                f"background: transparent;"
                f"border: none;"
                f"font-size: 10pt;"
            )
            outer.addWidget(content_label)
            self._content_widget = content_label

        elif role == "assistant":
            html = _screening_results_html(content)
            _is_inline = not html and "\n" not in content and len(content) <= 120

            if _is_inline:
                inline_lbl = QLabel(content or "—")
                inline_lbl.setWordWrap(True)
                inline_lbl.setStyleSheet(
                    f"color: {C.SUBTEXT};"
                    f"background: transparent;"
                    f"border: none;"
                    f"font-family: 'Consolas', 'Courier New', monospace;"
                    f"font-size: 9pt;"
                )
                outer.addWidget(inline_lbl)
                self._content_widget = inline_lbl
            else:
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
                text_edit.setMaximumHeight(400)
                text_edit.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
                )
                text_edit.setStyleSheet(
                    f"QTextEdit {{"
                    f"  border-radius: 4px;"
                    f"  font-family: 'Consolas', 'Courier New', monospace;"
                    f"  font-size: 9pt;"
                    f"  outline: none;"
                    f"}}"
                    f"QTextEdit:focus {{"
                    f"  outline: none;"
                    f"  border: 1px solid {_focus_blue};"
                    f"}}"
                )
                if html:
                    text_edit.setHtml(html)
                else:
                    text_edit.setPlainText(content)
                outer.addWidget(text_edit)
                self._content_widget = text_edit

        elif role == "system":
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
            text_edit.setMaximumHeight(320)
            text_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
            text_edit.setStyleSheet(
                f"QTextEdit {{"
                f"  border-radius: 4px;"
                f"  font-family: 'Consolas', 'Courier New', monospace;"
                f"  font-size: 9pt;"
                f"  outline: none;"
                f"}}"
                f"QTextEdit:focus {{"
                f"  outline: none;"
                f"  border: 1px solid {_focus_blue};"
                f"}}"
            )
            text_edit.setPlainText(content)
            text_edit.setVisible(False)  # collapsed by default
            outer.addWidget(text_edit)
            self._content_widget = text_edit

        elif role == "tool_result":
            result_label = QLabel(content or "—")
            result_label.setWordWrap(True)
            result_label.setStyleSheet(
                f"color: {C.MUTED};"
                f"background: transparent;"
                f"border: none;"
                f"font-size: 8pt;"
            )
            outer.addWidget(result_label)
            self._content_widget = result_label

        else:
            # Fallback: plain label
            fallback = QLabel(content)
            fallback.setWordWrap(True)
            fallback.setStyleSheet(
                f"color: {C.TEXT}; background: transparent; border: none;"
            )
            outer.addWidget(fallback)
            self._content_widget = fallback

        # ── footer — assistant cards: tokens + response time ────────────
        if is_assistant and (tokens_input or tokens_output or response_time_ms):
            parts: list[str] = []
            if tokens_input or tokens_output:
                parts.append(f"↑ {tokens_input}  ↓ {tokens_output}")
            if response_time_ms:
                secs = response_time_ms / 1000
                parts.append(f"{secs:.1f}s")
            footer_label = QLabel("   ·   ".join(parts))
            footer_font = QFont()
            footer_font.setPointSize(8)
            footer_label.setFont(footer_font)
            footer_label.setStyleSheet(
                f"color: {C.MUTED}; background: transparent; border: none;"
            )
            outer.addWidget(footer_label)

    # ------------------------------------------------------------------
    def _toggle_content(self) -> None:
        if self._content_widget is None or self._toggle_btn is None:
            return
        visible = self._content_widget.isVisible()
        self._content_widget.setVisible(not visible)
        if visible:
            self._toggle_btn.setText("Show system prompt ▼")
        else:
            self._toggle_btn.setText("Hide system prompt ▲")


# ---------------------------------------------------------------------------
# AITranscriptPanel
# ---------------------------------------------------------------------------

class AITranscriptPanel(QWidget):
    """Scrollable panel that displays the full AI conversation transcript."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_turns: list[Any] = []
        self._last_cost_in: float = 0.0
        self._last_cost_out: float = 0.0
        self._style_reload_pending: bool = False
        self._build_ui()

    # ------------------------------------------------------------------
    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.StyleChange
            and self._last_turns
            and not self._style_reload_pending
        ):
            self._style_reload_pending = True
            QTimer.singleShot(0, self._reload_for_theme)

    def _reload_for_theme(self) -> None:
        self._style_reload_pending = False
        self.load_transcript(self._last_turns, self._last_cost_in, self._last_cost_out)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ──────────────────────────────────────────
        header_bar = QFrame()
        header_bar.setObjectName("transcript_header_bar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(8, 4, 12, 4)
        header_layout.setSpacing(8)

        title_lbl = QLabel("AI TRANSCRIPT")
        title_font = QFont()
        title_font.setPointSize(7)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(
            f"color: {C.MUTED}; background: transparent; border: none;"
        )
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self._summary_lbl = QLabel("")
        summary_font = QFont("monospace", 9)
        self._summary_lbl.setFont(summary_font)
        self._summary_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._summary_lbl.setStyleSheet(
            f"color: {C.SUBTEXT}; background: transparent; border: none;"
        )
        header_layout.addWidget(self._summary_lbl)

        root.addWidget(header_bar)

        # ── scroll area ─────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self._turns_container = QWidget()
        self._turns_container.setStyleSheet("background: transparent;")
        self._turns_layout = QVBoxLayout(self._turns_container)
        self._turns_layout.setContentsMargins(8, 8, 8, 8)
        self._turns_layout.setSpacing(4)
        self._turns_layout.addStretch()

        self._scroll.setWidget(self._turns_container)
        root.addWidget(self._scroll)

    # ------------------------------------------------------------------
    def load_transcript(
        self,
        turns: list[Any],
        cost_per_1k_in: float,
        cost_per_1k_out: float,
    ) -> None:
        """Clear panel, build _TurnBlock per turn, update summary label.

        Args:
            turns: List of AITranscriptTurn-compatible objects.
            cost_per_1k_in: Cost in USD per 1 000 input tokens.
            cost_per_1k_out: Cost in USD per 1 000 output tokens.
        """
        self._last_turns = list(turns)
        self._last_cost_in = cost_per_1k_in
        self._last_cost_out = cost_per_1k_out
        self._clear_turns()

        total_in = sum(getattr(t, "tokens_input", 0) for t in turns)
        total_out = sum(getattr(t, "tokens_output", 0) for t in turns)
        cost = (total_in * cost_per_1k_in + total_out * cost_per_1k_out) / 1000

        if total_in == 0 and total_out == 0:
            summary_text = "No token data"
        else:
            summary_text = (
                f"Input: {total_in:,} tokens  |  "
                f"Output: {total_out:,} tokens  |  "
                f"Est. cost: ${cost:.4f}"
            )

        # Insert each turn as a wrapper QHBoxLayout with a fixed 80px spacer
        # to create the chat-log left/right alignment effect.
        # user cards: spacer LEFT + block RIGHT
        # all others: block LEFT + spacer RIGHT
        for turn in turns:
            role: str = getattr(turn, "role", "user")
            block = _TurnBlock(turn, self._turns_container)

            wrapper = QHBoxLayout()
            wrapper.setContentsMargins(0, 0, 0, 0)
            wrapper.setSpacing(0)

            if role == "user":
                # Indent from the left — pushes bubble to the right
                wrapper.addItem(
                    QSpacerItem(
                        80, 0,
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Minimum,
                    )
                )
                wrapper.addWidget(block)
            else:
                # Indent from the right — keeps bubble on the left
                wrapper.addWidget(block)
                wrapper.addItem(
                    QSpacerItem(
                        80, 0,
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Minimum,
                    )
                )

            # insertLayout(count-1) places before the trailing stretch
            self._turns_layout.insertLayout(
                self._turns_layout.count() - 1, wrapper
            )

        self._update_summary(summary_text)

        # Auto-scroll to bottom after Qt has processed layout geometry
        # _scroll verticalScrollBar setValue maximum → scroll to bottom
        QTimer.singleShot(
            0,
            lambda: self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            ),
        )

    def clear(self) -> None:
        """Remove all _TurnBlock widgets and reset summary label."""
        self._last_turns = []
        self._last_cost_in = 0.0
        self._last_cost_out = 0.0
        self._clear_turns()
        self._update_summary("")

    def has_turns(self) -> bool:
        """Return True if at least one transcript turn is currently loaded."""
        return bool(self._last_turns)

    # ------------------------------------------------------------------
    def _clear_turns(self) -> None:
        """Remove all wrapper layouts and their children from the turns layout.

        Keeps the trailing stretch item (always the last item) in place.
        Wrapper layouts contain _TurnBlock widgets and QSpacerItems; both are
        cleaned up before the inner layout is discarded.
        """
        while self._turns_layout.count() > 1:  # keep trailing stretch
            item = self._turns_layout.takeAt(0)
            inner = item.layout()
            if inner is not None:
                # Drain all items from the wrapper layout
                while inner.count():
                    sub = inner.takeAt(0)
                    w = sub.widget()
                    if w is not None:
                        w.deleteLater()
                    # QSpacerItems are reference-counted and freed automatically
                inner.deleteLater()
            else:
                # Bare widget inserted directly (defensive)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

    def _update_summary(self, text: str) -> None:
        """Set the summary label text."""
        self._summary_lbl.setText(text)
