Generic code writing skill for us_swing. Applies PyQt6 patterns when writing GUI modules; applies standard Python patterns for all other modules. Invoke before writing any new or significantly rewritten source file.

$ARGUMENTS

---

## Before Writing Any File

1. Query `MODULE_MAP.json` for the target class/module — never read full source files for orientation
2. Confirm the MD ID from `TRACE.md` — required for the file header
3. For GUI files: read `theme.py` constants and the closest existing panel for naming/layout patterns
4. For non-GUI files: read the relevant SRD rows and MD entry only

---

## File Header (all files)

```python
"""
Module: MD-<TOOL>-NNN.NNN.MNN — <Module Name>
Parent SRD: SRD-<TOOL>-NNN.NNN
"""
```

---

## PyQt6 Rules (GUI files only)

### Thread Safety

Any operation touching the network, filesystem, database, or running > 50 ms must use a worker:

```python
class _Worker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.finished.emit(fetch_data())
        except Exception as exc:
            self.error.emit(str(exc))

class MyPanel(QWidget):
    def _start_load(self) -> None:
        self._thread = QThread()
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._on_error)
        self._thread.start()
```

Never call `time.sleep()`, DB queries, or file I/O directly in a slot or `__init__`.

### Theme Constants

```python
from us_swing.gui.theme import C, QSS

label.setStyleSheet(f"color: {C.FG2};")
btn.setFixedWidth(80)       # width only — height controlled by global QSS
# NEVER: btn.setFixedHeight(28) or btn.setFixedSize(80, 28)
```

### Focus Outline

Every `setStyleSheet()` on a focusable widget (`QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QLineEdit`, `QPushButton`, `QRadioButton`) must include `outline: none` in base and `:focus` selectors.

### Frameless Windows

Every new top-level window or dialog:

```python
self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
```

Copy `_TitleBar` from `main_window.py` (drag, min/max/close). Copy `_DialogTitleBar` from `scheduler_dialog.py` for dialogs. Window titles: short noun phrase only.

### Tabular Data

For any table with > 20 rows or dynamic data use `QAbstractTableModel` + `QSortFilterProxyModel`. Never `QTableWidget` with data stored in cells for dynamic datasets.

### Signal/Slot Wiring

- Document every connection: `# emitter → signal → receiver → slot`
- Cross-panel communication goes through `core/` or the parent window — never import sibling panels

### Layout and Spacing

- Base unit: 4 px. Margins: 8 px (tight), 12 px (standard), 16 px (section gap)
- Every widget container must have a layout assigned

### Anti-Patterns

| Never write | Use instead |
|---|---|
| `btn.setFixedHeight(28)` | Let global QSS control height |
| `time.sleep()` in a slot | `QTimer.singleShot()` or `QThread` |
| Widget update from `QThread.run()` | Emit a signal, update in slot |
| `QTableWidget` for dynamic data | `QAbstractTableModel` |
| Business logic in `__init__` or `paintEvent` | Extract to service or worker |
| Hardcoded color `"#1e1e2e"` | `C.BG`, `C.BG2`, etc. |
| Sibling panel import | Signal through parent or `core/` |
| Missing `outline: none` on focusable widget | Add to base and `:focus` selectors |

---

## Python Rules (all files)

- Full type annotations on all public functions and methods
- Google-style docstrings on all public APIs
- `dataclasses` or Pydantic for data containers — not plain dicts
- `asyncio` for I/O-bound operations — never block the event loop
- Repository pattern for all data access
- Must pass `ruff check` + `mypy --strict` with zero errors

---

## Output Checklist

Before declaring a file done:

- [ ] Module header with correct MD ID present
- [ ] No hardcoded colors or pixel heights (GUI)
- [ ] All blocking operations in `QThread` workers (GUI)
- [ ] Every focusable widget stylesheet has `outline: none` (GUI)
- [ ] Frameless window pattern used for any top-level window/dialog (GUI)
- [ ] Full type annotations on all public methods
- [ ] Passes `ruff` + `mypy --strict`
