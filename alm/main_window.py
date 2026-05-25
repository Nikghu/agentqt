"""
ALM Main Window — PyQt6 UI for the traceability tree viewer.

Skill coverage (skill.md § 4):
  4.5  Theming & Styling  — dark/light QSS themes, DPI-aware palette
  4.6  Dockable Workspace — QSplitter with persistent sizes
  4.7  Async/GUI Bridge   — QThread doc-loader, progress reporting
  4.8  Keyboard-First UX  — Ctrl+F/O/R, Esc, F5 shortcuts
  4.9  Modern Styleguide  — unified palette, icon controls, toast notifications

Standalone tool — works with any project that follows the docs/ convention.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from alm.parser import ALMNode, ALL_STATUSES, AuditResult, audit_docs, load_all_nodes, update_node_status

# ---------------------------------------------------------------------------
# Theme definitions  (skill.md 4.5, 4.9)
# ---------------------------------------------------------------------------

_DARK_QSS = """
QMainWindow, QWidget {
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
}
QTreeWidget {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 5px;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    show-decoration-selected: 1;
    padding: 2px;
}
QTreeWidget::item {
    padding: 3px 2px;
    border-radius: 3px;
}
QTreeWidget::item:selected {
    background: #45475a;
    color: #cdd6f4;
}
QTreeWidget::item:hover:!selected {
    background: #313244;
}
QTextBrowser {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 5px;
    color: #cdd6f4;
    selection-background-color: #585b70;
    padding: 6px;
}
QLineEdit {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 5px 10px;
    min-height: 22px;
}
QLineEdit:focus { border: 1px solid #89b4fa; }
QLineEdit:read-only { border-color: #313244; color: #7f849c; }
QLabel { background: transparent; }
QComboBox {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 5px 8px;
    min-height: 22px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #313244;
    selection-background-color: #45475a;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 2px;
}
QPushButton {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 5px 14px;
    min-height: 22px;
}
QPushButton:hover  { background: #45475a; border-color: #89b4fa; }
QPushButton:pressed { background: #585b70; }
QPushButton:checked { background: #1e3a5f; border-color: #89b4fa; color: #89b4fa; }
QPushButton#accent {
    background: #1e4a34;
    border: 1px solid #40a070;
    color: #a6e3a1;
}
QPushButton#accent:hover  { background: #26855c; }
QPushButton#accent:disabled { background: #252535; border-color: #35354a; color: #55556a; }
QPushButton#icon_btn {
    background: transparent;
    border: 1px solid transparent;
    padding: 4px 8px;
}
QPushButton#icon_btn:hover { background: #313244; border-color: #45475a; }
QProgressBar {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 3px;
    text-align: center;
    color: #cdd6f4;
    font-size: 8pt;
}
QProgressBar::chunk { background: #a6e3a1; border-radius: 3px; }
QProgressBar#slim::chunk { background: #89b4fa; }
QStatusBar {
    background: #181825;
    color: #7f849c;
    border-top: 1px solid #313244;
    font-size: 8pt;
}
QLabel#toast_ok  { color: #a6e3a1; font-weight: bold; }
QLabel#toast_err { color: #f38ba8; font-weight: bold; }
QLabel#toast_inf { color: #89b4fa; }
QLabel#group_hdr {
    color: #7f849c;
    font-size: 8pt;
    font-weight: bold;
    letter-spacing: 0.5px;
}
QFrame#separator_v {
    background: #313244;
    max-width: 1px;
    min-width: 1px;
    margin: 4px 2px;
}
QFrame#card {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
}
QFrame#audit_banner {
    background: #3d2b00;
    border: 1px solid #f9e2af;
    border-radius: 5px;
}
QFrame#audit_banner QLabel { color: #f9e2af; font-size: 9pt; }
QFrame#audit_banner QPushButton {
    background: transparent; border: none; color: #f9e2af; font-weight: bold;
    padding: 2px 6px;
}
QFrame#audit_banner QPushButton:hover { color: #fab387; }
QFrame#heatmap_frame {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
}
QSplitter::handle { background: #313244; width: 2px; margin: 0 2px; }
"""

# Status colour map (works in both themes)
_STATUS_COLOURS: dict[str, str] = {
    "approved":    "#4caf50",
    "implemented": "#42a5f5",
    "verified":    "#26c6da",
    "draft":       "#ffa726",
    "unknown":     "#9e9e9e",
}

# Doc-type sort order
_LEVEL_ORDER = ["FO", "SRD", "DD", "MD", "UT"]


def _status_colour(node: ALMNode) -> QColor:
    key = node.status.lower().split()[0]
    return QColor(_STATUS_COLOURS.get(key, _STATUS_COLOURS["unknown"]))


def _tool_label(tool: str) -> str:
    return f"\U0001f4c1  {tool.replace('_', ' ').title()}"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )





# ---------------------------------------------------------------------------
# Async loader  (skill.md 4.7)
# ---------------------------------------------------------------------------

class _LoadWorker(QObject):
    """Loads ALM nodes in a background QThread — keeps the UI responsive."""

    finished = pyqtSignal(list)          # list[ALMNode]
    audited  = pyqtSignal(object)        # AuditResult
    error    = pyqtSignal(str)

    def __init__(self, docs_root: Path) -> None:
        super().__init__()
        self._docs_root = docs_root

    def run(self) -> None:
        try:
            nodes = load_all_nodes(self._docs_root)
            self.finished.emit(nodes)
            # Audit runs after load so it reuses the same file reads
            result = audit_docs(self._docs_root)
            self.audited.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class ALMMainWindow(QMainWindow):
    def __init__(
        self,
        docs_root: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._docs_root: Path | None = docs_root
        self._nodes: list[ALMNode] = []
        self._id_map:   dict[str, ALMNode] = {}
        self._current_node: ALMNode | None = None
        self._thread: QThread | None = None
        self._worker: _LoadWorker | None = None
        self._pending_restore: tuple[set[str], str | None] | None = None

        self.setWindowTitle("ALM Viewer")
        self.setMinimumSize(1100, 720)

        self._build_ui()
        self._apply_theme(dark=True)
        self._register_shortcuts()  # skill.md 4.8

        if self._docs_root and self._docs_root.is_dir():
            self._update_title()
            self._load()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(10, 10, 10, 6)
        vbox.setSpacing(0)              # sections manage their own spacing

        # ================================================================
        # ROW 1 — Header bar: path + Browse + Tool/Status/Type filters
        # ================================================================
        header = QFrame()
        header.setObjectName("card")
        header.setFixedHeight(46)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 10, 0)
        h_lay.setSpacing(6)

        # ── Shared widget factories (available for the rest of _build_ui) ──
        def _btn(text: str, tip: str, width: int = 0) -> QPushButton:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedHeight(30)
            if width:
                b.setFixedWidth(width)
            return b

        def _vsep() -> QFrame:
            s = QFrame()
            s.setObjectName("separator_v")
            s.setFrameShape(QFrame.Shape.VLine)
            return s

        def _combo(width: int) -> QComboBox:
            c = QComboBox()
            c.setFixedWidth(width)
            c.setFixedHeight(28)
            return c

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setObjectName("group_hdr")
            l.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            )
            return l

        self._path_label = QLineEdit()
        self._path_label.setReadOnly(True)
        self._path_label.setPlaceholderText("No project loaded — Ctrl+O to browse")
        h_lay.addWidget(self._path_label, stretch=1)

        h_lay.addSpacing(4)
        browse_btn = _btn("📂  Browse", "Open project folder (Ctrl+O)", 106)
        browse_btn.clicked.connect(self._on_browse)
        h_lay.addWidget(browse_btn)

        h_lay.addWidget(_vsep())

        # Tool / Status / Type filter combos in header
        h_lay.addWidget(_lbl("Tool"))
        self._tool_filter = _combo(128)
        self._tool_filter.addItem("All")
        self._tool_filter.currentTextChanged.connect(self._on_filter_changed)
        h_lay.addWidget(self._tool_filter)

        h_lay.addSpacing(4)
        h_lay.addWidget(_lbl("Status"))
        self._status_filter = _combo(116)
        self._status_filter.addItem("All")
        self._status_filter.addItems(ALL_STATUSES)
        self._status_filter.currentTextChanged.connect(self._on_filter_changed)
        h_lay.addWidget(self._status_filter)

        h_lay.addSpacing(4)
        h_lay.addWidget(_lbl("Type"))
        self._type_filter = _combo(72)
        self._type_filter.addItem("All")
        self._type_filter.addItems(_LEVEL_ORDER)
        self._type_filter.currentTextChanged.connect(self._on_filter_changed)
        h_lay.addWidget(self._type_filter)

        vbox.addWidget(header)
        vbox.addSpacing(6)

        # ================================================================
        # ROW 4 — Main splitter: tree | detail
        # ================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        # Left: tree
        tree_wrapper = QFrame()
        tree_wrapper.setObjectName("card")
        tw_lay = QVBoxLayout(tree_wrapper)
        tw_lay.setContentsMargins(6, 6, 6, 6)
        tw_lay.setSpacing(4)

        # Search box inside tree frame
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_icon = QLabel("🔍")
        search_icon.setFixedWidth(18)
        search_row.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search IDs, titles, content…  (Ctrl+F)")
        self._search.setFixedHeight(28)
        self._search.textChanged.connect(self._on_search)
        search_row.addWidget(self._search, stretch=1)
        refresh_btn = QPushButton("⟳")
        refresh_btn.setToolTip("Reload all docs (F5 / Ctrl+R)")
        refresh_btn.setFixedSize(32, 28)
        refresh_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        refresh_btn.clicked.connect(self._load)
        search_row.addWidget(refresh_btn)
        tw_lay.addLayout(search_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setAlternatingRowColors(True)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        self._tree.setFont(QFont("Consolas", 9))
        self._tree.setFrameShape(QFrame.Shape.NoFrame)   # card provides the border
        tw_lay.addWidget(self._tree)
        splitter.addWidget(tree_wrapper)

        # Right: FO progress + detail browser
        right_wrapper = QFrame()
        right_wrapper.setObjectName("card")
        rw_lay = QVBoxLayout(right_wrapper)
        rw_lay.setContentsMargins(10, 8, 10, 8)
        rw_lay.setSpacing(6)

        # Set Status / Save row  —  FO summary label on left, controls on right
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self._fo_bar_lbl = QLabel()
        self._fo_bar_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._fo_bar_lbl.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        ctrl_row.addWidget(self._fo_bar_lbl, stretch=1)

        s_sep = QFrame()
        s_sep.setObjectName("separator_v")
        s_sep.setFrameShape(QFrame.Shape.VLine)
        ctrl_row.addWidget(s_sep)

        ctrl_row.addWidget(_lbl("Set status"))
        self._status_combo = _combo(116)
        self._status_combo.addItems(ALL_STATUSES)
        self._status_combo.setEnabled(False)
        ctrl_row.addWidget(self._status_combo)

        ctrl_row.addSpacing(4)
        self._save_btn = QPushButton("💾  Save")
        self._save_btn.setObjectName("accent")
        self._save_btn.setFixedSize(80, 28)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_status)
        ctrl_row.addWidget(self._save_btn)
        rw_lay.addLayout(ctrl_row)

        # FO verified progress mini-bar — REMOVED; summary shown inline on selection

        # Thin divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("separator_v")   # reuse same 1px style; horizontal
        rw_lay.addWidget(divider)

        self._panel = QTextBrowser()
        self._panel.setOpenLinks(False)
        self._panel.setFont(QFont("Segoe UI", 10))
        self._panel.anchorClicked.connect(self._on_link)
        self._panel.setFrameShape(QFrame.Shape.NoFrame)
        rw_lay.addWidget(self._panel)

        splitter.addWidget(right_wrapper)
        splitter.setSizes([340, 760])
        vbox.addWidget(splitter, stretch=1)
        vbox.addSpacing(4)

        # ================================================================
        # BOTTOM — audit banner + slim loading bar
        # ================================================================
        self._audit_banner = QFrame()
        self._audit_banner.setObjectName("audit_banner")
        self._audit_banner.setFrameShape(QFrame.Shape.StyledPanel)
        self._audit_banner.setFixedHeight(34)
        self._audit_banner.setVisible(False)
        bl = QHBoxLayout(self._audit_banner)
        bl.setContentsMargins(10, 0, 6, 0)
        bl.setSpacing(8)
        self._audit_icon = QLabel("⚠️")
        self._audit_icon.setFixedWidth(20)
        bl.addWidget(self._audit_icon)
        self._audit_label = QLabel()
        self._audit_label.setWordWrap(False)
        bl.addWidget(self._audit_label, stretch=1)
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setObjectName("icon_btn")
        dismiss_btn.setFixedSize(26, 26)
        dismiss_btn.setToolTip("Dismiss")
        dismiss_btn.clicked.connect(lambda: self._audit_banner.setVisible(False))
        bl.addWidget(dismiss_btn)
        vbox.addWidget(self._audit_banner)

        self._loading_bar = QProgressBar()
        self._loading_bar.setObjectName("slim")
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(3)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setVisible(False)
        vbox.addWidget(self._loading_bar)

        # ---- Status bar -----------------------------------------------
        self._toast = QLabel("Ready")
        self._toast.setObjectName("toast_inf")
        self.statusBar().addWidget(self._toast)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.setText("Ready"))

    # ------------------------------------------------------------------
    # Keyboard shortcuts  (skill.md 4.8)
    # ------------------------------------------------------------------

    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence("F5"),     self).activated.connect(self._load)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._load)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._on_browse)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._clear_search)

    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def _clear_search(self) -> None:
        self._search.clear()
        self._tree.setFocus()

    # ------------------------------------------------------------------
    # Theme  (skill.md 4.5, 4.9)
    # ------------------------------------------------------------------

    def _apply_theme(self, dark: bool = True) -> None:  # always dark
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_DARK_QSS)

    # ------------------------------------------------------------------
    # Toast notifications  (skill.md 4.9)
    # ------------------------------------------------------------------

    def _toast_notify(self, msg: str, *, kind: str = "inf", ms: int = 3000) -> None:
        self._toast.setObjectName(f"toast_{kind}")
        self._toast.style().unpolish(self._toast)
        self._toast.style().polish(self._toast)
        self._toast.setText(msg)
        self._toast_timer.start(ms)

    # ------------------------------------------------------------------
    # Browse / title
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select project folder (or its docs/ folder)",
            str(self._docs_root) if self._docs_root else "",
        )
        if not folder:
            return
        path = Path(folder)
        if path.name == "docs" and path.is_dir():
            self._docs_root = path
        elif (path / "docs").is_dir():
            self._docs_root = path / "docs"
        else:
            for parent in path.parents:
                if (parent / "docs").is_dir():
                    self._docs_root = parent / "docs"
                    break
            else:
                QMessageBox.warning(
                    self, "No docs/ found",
                    f"Could not find a docs/ folder in or above:\n{path}",
                )
                return
        self._update_title()
        self._load()

    def _update_title(self) -> None:
        if self._docs_root:
            project = self._docs_root.parent.name
            self.setWindowTitle(f"ALM Viewer — {project}")
            self._path_label.setText(str(self._docs_root))

    # ------------------------------------------------------------------
    # Async data load  (skill.md 4.7)
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._docs_root or not self._docs_root.is_dir():
            self._toast_notify("No docs folder loaded", kind="err")
            return

        # Preserve tree state across manual refresh (save-triggered reloads set
        # _pending_restore themselves before calling _load, so don't overwrite).
        if self._nodes and self._pending_restore is None:
            current_id = self._current_node.id if self._current_node else None
            self._pending_restore = (self._save_tree_state(), current_id)

        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(500)

        self._loading_bar.setVisible(True)
        self._toast_notify("Loading docs\u2026", kind="inf", ms=30_000)

        self._thread = QThread(self)
        self._worker = _LoadWorker(self._docs_root)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_load_finished)
        self._worker.audited.connect(self._on_audit_result)
        self._worker.error.connect(self._on_load_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_load_finished(self, nodes: list[ALMNode]) -> None:
        self._loading_bar.setVisible(False)
        self._nodes = nodes
        self._id_map = {n.id: n for n in nodes}
        self._rebuild_filters()
        self._rebuild_tree()

        # Restore tree expansion + selection if a save triggered the reload
        pending = self._pending_restore
        if pending is not None:
            expanded, select_id = pending
            self._pending_restore = None
            self._restore_tree_state(expanded, select_id)

        tools = len({n.tool for n in nodes})
        self._toast_notify(
            f"\u2714  {len(nodes)} nodes \u00b7 {tools} tool(s) loaded",
            kind="ok",
        )

    def _on_audit_result(self, result: AuditResult) -> None:
        """Show or hide the traceability warning banner based on audit outcome."""
        if not result.missing:
            self._audit_banner.setVisible(False)
            return

        # Build a compact summary of missed IDs grouped by file
        by_file: dict[str, list[str]] = {}
        for node_id, path in result.missing:
            key = path.name
            by_file.setdefault(key, []).append(node_id)

        detail_parts = []
        for fname, ids in sorted(by_file.items()):
            sample = ", ".join(ids[:3])
            if len(ids) > 3:
                sample += f" … +{len(ids) - 3} more"
            detail_parts.append(f"{fname}: {sample}")

        count = len(result.missing)
        msg = (
            f"{count} traceable ID(s) found in docs but NOT captured by the parser — "
            f"a document format change may have broken traceability.  "
            + "  |  ".join(detail_parts)
        )
        self._audit_label.setText(msg)
        self._audit_label.setToolTip(
            "The ALM parser could not read these IDs.\n"
            "Likely cause: document format changed without updating the parser.\n"
            "Fix: update alm/parser.py to handle the new format, then refresh."
        )
        self._audit_banner.setVisible(True)
        # Also emit a persistent toast so it's visible without scrolling
        self._toast_notify(
            f"⚠️  Traceability gap: {count} ID(s) not captured — see banner",
            kind="err",
            ms=10000,
        )

    def _on_load_error(self, msg: str) -> None:
        self._loading_bar.setVisible(False)
        self._toast_notify(f"\u274c  Load error: {msg}", kind="err", ms=8000)

    # ------------------------------------------------------------------
    # Filter helpers  (FO-ALM-005)
    # ------------------------------------------------------------------

    def _rebuild_filters(self) -> None:
        self._tool_filter.blockSignals(True)
        prev_tool = self._tool_filter.currentText()
        self._tool_filter.clear()
        self._tool_filter.addItem("All")
        for t in sorted({n.tool for n in self._nodes}):
            self._tool_filter.addItem(t.replace("_", " ").title())
        idx = self._tool_filter.findText(prev_tool)
        if idx >= 0:
            self._tool_filter.setCurrentIndex(idx)
        self._tool_filter.blockSignals(False)

    def _on_filter_changed(self, _text: str) -> None:
        self._rebuild_tree()

    def _active_tool_filter(self) -> str:
        t = self._tool_filter.currentText()
        return "" if t == "All" else t.lower().replace(" ", "_")

    def _active_status_filter(self) -> str:
        s = self._status_filter.currentText()
        return "" if s == "All" else s

    def _active_type_filter(self) -> str:
        t = self._type_filter.currentText()
        return "" if t == "All" else t

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------

    def _rebuild_tree(self) -> None:
        self._tree.clear()
        self._panel.clear()
        self._status_combo.setEnabled(False)
        self._save_btn.setEnabled(False)

        tool_f   = self._active_tool_filter()
        status_f = self._active_status_filter()
        type_f   = self._active_type_filter()
        search_t = self._search.text().strip().lower()

        visible_nodes = [
            n for n in self._nodes
            if (not tool_f   or n.tool == tool_f)
            and (not type_f   or n.doc_type == type_f)
            and (not status_f or n.status.lower() == status_f.lower())
            and (not search_t or search_t in n.id.lower()
                             or search_t in n.title.lower()
                             or search_t in n.body.lower())
        ]

        item_map:    dict[str, QTreeWidgetItem] = {}
        tool_map:    dict[str, QTreeWidgetItem] = {}
        orphan_item: QTreeWidgetItem | None = None

        ordered = sorted(
            visible_nodes,
            key=lambda n: (
                _LEVEL_ORDER.index(n.doc_type) if n.doc_type in _LEVEL_ORDER else 99
            ),
        )

        for node in ordered:
            item = QTreeWidgetItem([node.label])
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            item.setForeground(0, _status_colour(node))

            if not node.parent_id:
                if node.tool not in tool_map:
                    ti = QTreeWidgetItem([_tool_label(node.tool)])
                    ti.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
                    ti.setData(0, Qt.ItemDataRole.UserRole, f"__tool__{node.tool}")
                    self._tree.addTopLevelItem(ti)
                    tool_map[node.tool] = ti
                tool_map[node.tool].addChild(item)
            elif node.parent_id in item_map:
                item_map[node.parent_id].addChild(item)
            else:
                if orphan_item is None:
                    orphan_item = QTreeWidgetItem(["\u26a0  Orphans (missing parent)"])
                    orphan_item.setForeground(0, QColor("#f38ba8"))
                    self._tree.addTopLevelItem(orphan_item)
                orphan_item.addChild(item)
                item.setToolTip(0, f"Missing parent: {node.parent_id}")

            item_map[node.id] = item

        # Expand only the top-level tool folder items; children stay collapsed.
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setExpanded(True)

        orphan_count = orphan_item.childCount() if orphan_item else 0
        summary = f"{len(visible_nodes)} / {len(self._nodes)} nodes"
        if tool_f or status_f or search_t:
            summary += "  (filtered)"
        if orphan_count:
            summary += f"  \u26a0 {orphan_count} orphan(s)"
        self._toast.setText(summary)

    # ------------------------------------------------------------------
    # FO requirements summary  (replaces progress bar)
    # ------------------------------------------------------------------

    def _update_fo_bar(self, item: QTreeWidgetItem) -> None:
        """Build Section breadcrumb + status counts from selected tree item's subtree."""
        # --- breadcrumb: walk from root to this item ---
        path_parts: list[str] = []
        cur: QTreeWidgetItem | None = item
        while cur is not None:
            data = cur.data(0, Qt.ItemDataRole.UserRole) or ""
            if data.startswith("__tool__"):
                path_parts.insert(0, data[8:].replace("_", " ").title())
            elif data:
                n = self._id_map.get(data)
                path_parts.insert(0, n.id if n else data)
            cur = cur.parent()
        breadcrumb = " — ".join(path_parts)

        # --- collect all descendant nodes (inclusive) ---
        def _collect(it: QTreeWidgetItem) -> list[ALMNode]:
            result: list[ALMNode] = []
            nid = it.data(0, Qt.ItemDataRole.UserRole) or ""
            if nid and not nid.startswith("__tool__"):
                nd = self._id_map.get(nid)
                if nd:
                    result.append(nd)
            for i in range(it.childCount()):
                result.extend(_collect(it.child(i)))
            return result

        nodes = _collect(item)
        total = len(nodes)

        counts: dict[str, int] = {}
        for nd in nodes:
            key = nd.status_key.lower().split()[0].capitalize()
            counts[key] = counts.get(key, 0) + 1

        pills: list[str] = []
        for raw_key, colour in _STATUS_COLOURS.items():
            if raw_key == "unknown":
                continue
            label = raw_key.capitalize()
            c = counts.get(label, 0)
            if c:
                pills.append(
                    f"<span style='color:{colour};"
                    f"font-size:8pt;font-weight:bold'>{label}&nbsp;{c}</span>"
                )
        pills_html = "&nbsp;&nbsp;".join(pills) if pills else ""
        total_html = (
            f"&nbsp;<span style='color:#7f849c;font-size:8pt'>({total})</span>"
            if total else ""
        )

        self._fo_bar_lbl.setText(
            f"<span style='color:#cdd6f4;font-size:8pt'>"
            f"<b style='color:#89b4fa'>Section:</b>&nbsp;{breadcrumb}"
            f"{total_html}</span>"
            f"&nbsp;&nbsp;&nbsp;{pills_html}"
        )

    # ------------------------------------------------------------------
    # FO progress bar  (FO-ALM-004) — REMOVED
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_changed(
        self,
        current: QTreeWidgetItem | None,
        _prev: object,
    ) -> None:
        if current is None:
            self._panel.clear()
            self._fo_bar_lbl.clear()
            self._status_combo.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._current_node = None
            return

        node_id: str = current.data(0, Qt.ItemDataRole.UserRole) or ""

        # Tool-folder item clicked — show breadcrumb in bar, clear panel
        if node_id.startswith("__tool__"):
            self._update_fo_bar(current)
            self._panel.clear()
            self._status_combo.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._current_node = None
            return

        node = self._id_map.get(node_id)
        if node:
            self._update_fo_bar(current)
            self._render_node(node)
            idx = self._status_combo.findText(
                node.status, Qt.MatchFlag.MatchFixedString
            )
            if idx >= 0:
                self._status_combo.setCurrentIndex(idx)
            self._status_combo.setEnabled(True)
            self._save_btn.setEnabled(True)
            self._current_node = node
        else:
            self._panel.clear()
            self._fo_bar_lbl.clear()
            self._status_combo.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._current_node = None

    def _on_search(self, _text: str) -> None:
        self._rebuild_tree()

    def _on_save_status(self) -> None:
        node = self._current_node
        if node is None:
            return
        new_status = self._status_combo.currentText()
        if new_status == node.status:
            self._toast_notify("Status unchanged", kind="inf")
            return
        try:
            update_node_status(node, new_status)
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            self._toast_notify(f"\u274c Save failed: {exc}", kind="err")
            return
        # Save tree state before reload so it can be restored
        self._pending_restore = (self._save_tree_state(), node.id)
        self._load()
        self._toast_notify(f"\u2714  {node.id} \u2192 {new_status}", kind="ok")

    def _on_link(self, url: object) -> None:
        node_id = str(url.toString()) if hasattr(url, "toString") else str(url)
        node = self._id_map.get(node_id)
        if node:
            self._render_node(node)
        else:
            self._toast_notify(f"Node not found: {node_id}", kind="err")

    # ------------------------------------------------------------------
    # Tree state save / restore  (preserve expansion + selection on reload)
    # ------------------------------------------------------------------

    def _save_tree_state(self) -> set[str]:
        """Return the set of node IDs whose tree items are currently expanded."""
        expanded: set[str] = set()

        def _walk(item: QTreeWidgetItem) -> None:
            nid = item.data(0, Qt.ItemDataRole.UserRole) or ""
            if nid and item.isExpanded():
                expanded.add(nid)
            for i in range(item.childCount()):
                _walk(item.child(i))

        for i in range(self._tree.topLevelItemCount()):
            _walk(self._tree.topLevelItem(i))
        return expanded

    def _restore_tree_state(
        self, expanded: set[str], select_id: str | None = None
    ) -> None:
        """Re-expand previously expanded items and optionally re-select a node."""
        select_item: QTreeWidgetItem | None = None

        def _walk(item: QTreeWidgetItem) -> None:
            nonlocal select_item
            nid = item.data(0, Qt.ItemDataRole.UserRole) or ""
            if nid in expanded:
                item.setExpanded(True)
            if nid and nid == select_id:
                select_item = item
            for i in range(item.childCount()):
                _walk(item.child(i))

        for i in range(self._tree.topLevelItemCount()):
            _walk(self._tree.topLevelItem(i))

        if select_item is not None:
            self._tree.setCurrentItem(select_item)
            self._tree.scrollToItem(select_item)

    # ------------------------------------------------------------------
    # Content rendering
    # ------------------------------------------------------------------

    def _render_node(self, node: ALMNode) -> None:
        colour = _STATUS_COLOURS.get(node.status_key, _STATUS_COLOURS["unknown"])
        lines: list[str] = [
            f"<h2 style='color:{colour};margin-bottom:2px'>{node.id}</h2>",
            f"<h3 style='margin-top:2px'>{_escape_html(node.title)}</h3>",
            f"<p><b>Tool:</b> {node.tool} &nbsp;|&nbsp; "
            f"<b>Type:</b> {node.doc_type} &nbsp;|&nbsp; "
            f"<b>Status:</b> <span style='color:{colour}'>{node.status}</span></p>",
        ]
        if node.parent_id:
            lines.append(
                f"<p><b>Parent:</b> "
                f"<a href='{node.parent_id}' style='color:{colour}'>"
                f"{node.parent_id}</a></p>"
            )
        lines.append(
            f"<p><b>Source:</b> <code style='font-size:8pt'>"
            f"{node.source_file.name}</code></p>"
        )
        lines.append("<hr/>")
        lines.append(
            "<pre style='white-space:pre-wrap;"
            "font-family:Consolas,\"Courier New\",monospace;"
            "font-size:9pt;line-height:1.4'>"
        )
        lines.append(_escape_html(node.body))
        lines.append("</pre>")
        self._panel.setHtml("".join(lines))
