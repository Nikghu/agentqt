"""
Module: MD-GUI-000.004 — scheduler_dialog.py
Parent SRD: SRD-GUI-006.005

Windows Task Scheduler integration dialog.
Creates two independent scheduled tasks:
  • USSwing_App  — launches USSwing.exe
  • USSwing_IBKR — launches Trader Workstation (TWS)

Uses only stdlib (winreg, subprocess, pathlib) — no 3rd-party dependencies.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QThread, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.scheduler_store import (
    CloseConfig,
    SchedulerConfig,
    USSwingConfig,
    delete_close_config,
    delete_scheduler_config,
    delete_usswing_config,
    load_close_config,
    load_scheduler_config,
    load_usswing_config,
    save_close_config,
    save_scheduler_config,
    save_usswing_config,
)
from us_swing.gui.theme import C

# ── Auto-detection helpers ────────────────────────────────────────────────────

_TWS_ROOTS: list[Path] = [
    Path("C:/Jts"),
    Path("C:/Program Files/Trader Workstation"),
    Path("C:/Program Files (x86)/Trader Workstation"),
]
_USSWING_DEFAULT = Path(r"C:\Program Files (x86)\USSwing\USSwing.exe")


def _registry_tws() -> str | None:
    """Try to read the TWS install path from the Windows registry."""
    try:
        import winreg
    except ImportError:
        return None

    registry_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\IBKR"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\IBKR"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\IB Group"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\IB Group"),
    ]
    for hive, key_path in registry_keys:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "InstallPath")
                if isinstance(val, str):
                    candidate = Path(val) / "tws.exe"
                    if candidate.exists():
                        return str(candidate)
        except OSError:
            continue
    return None


def find_tws_exe() -> str | None:
    """Return the best-guess path to tws.exe, or None.

    Search order:
      1. Windows registry (IBKR install key)
      2. C:/Jts/tws.exe  (default TWS install location)
      3. Highest version subdirectory under each known root
      4. Standard Program Files locations
    """
    found = _registry_tws()
    if found:
        return found

    for root in _TWS_ROOTS:
        if not root.exists():
            continue
        direct = root / "tws.exe"
        if direct.exists():
            return str(direct)
        # Version subdirs like C:\Jts\1036\ — pick the highest
        try:
            subdirs = sorted(
                (d for d in root.iterdir() if d.is_dir()),
                reverse=True,
            )
        except PermissionError:
            continue
        for sub in subdirs:
            candidate = sub / "tws.exe"
            if candidate.exists():
                return str(candidate)
    return None


# ── schtasks wrappers ─────────────────────────────────────────────────────────

def _run_schtasks(*args: str) -> tuple[bool, str]:
    """Run schtasks.exe with the given arguments. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["schtasks", *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
        ok = result.returncode == 0
        msg = (result.stdout.strip() or result.stderr.strip()) if not ok else result.stdout.strip()
        return ok, msg
    except FileNotFoundError:
        return False, "schtasks.exe not found — this feature requires Windows."
    except subprocess.TimeoutExpired:
        return False, "schtasks timed out."
    except OSError as exc:
        return False, str(exc)


def _create_schtask(
    task_name: str,
    exe_path: str,
    launch_time: str,
    days: str,
    extra_args: str = "",
) -> tuple[bool, str]:
    tr = f'"{exe_path}"{extra_args}'
    base = ["/create", "/tn", task_name, "/tr", tr, "/st", launch_time, "/f"]
    if days == "weekdays":
        return _run_schtasks(*base, "/sc", "weekly", "/d", "MON,TUE,WED,THU,FRI")
    return _run_schtasks(*base, "/sc", "daily")


def create_usswing_task(cfg: USSwingConfig) -> tuple[bool, str]:
    return _create_schtask(cfg.task_name, cfg.exe_path, cfg.launch_time, cfg.days)


def create_ibkr_task(cfg: SchedulerConfig, password: str = "") -> tuple[bool, str]:
    extra = ""
    if cfg.auto_login and cfg.ibkr_username and password:
        extra = f" -username {cfg.ibkr_username} -password {password}"
    return _create_schtask(cfg.task_name, cfg.exe_path, cfg.launch_time, cfg.days, extra)


def delete_task(task_name: str) -> tuple[bool, str]:
    return _run_schtasks("/delete", "/tn", task_name, "/f")


def _create_close_task(
    task_name: str,
    image_name: str,
    close_time: str,
    days: str,
) -> tuple[bool, str]:
    tr = f"taskkill /IM {image_name} /F"
    base = ["/create", "/tn", task_name, "/tr", tr, "/st", close_time, "/f"]
    if days == "weekdays":
        return _run_schtasks(*base, "/sc", "weekly", "/d", "MON,TUE,WED,THU,FRI")
    return _run_schtasks(*base, "/sc", "daily")


def create_usswing_close_task(cfg: USSwingConfig, close_time: str) -> tuple[bool, str]:
    image = Path(cfg.exe_path).name or "USSwing.exe"
    return _create_close_task(f"{cfg.task_name}_Close", image, close_time, cfg.days)


def create_ibkr_close_task(cfg: SchedulerConfig, close_time: str) -> tuple[bool, str]:
    image = Path(cfg.exe_path).name or "tws.exe"
    return _create_close_task(f"{cfg.task_name}_Close", image, close_time, cfg.days)


# ── Path status label helper ──────────────────────────────────────────────────

def _make_status_label() -> QLabel:
    lbl = QLabel("")
    lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
    return lbl


def _update_status_label(lbl: QLabel, path: str | None) -> None:
    if path and Path(path).exists():
        lbl.setText("✔  Executable found")
        lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 8pt;")
    elif path:
        lbl.setText("⚠  Path set but file not found — verify the location")
        lbl.setStyleSheet("color: #f9a825; font-size: 8pt;")
    else:
        lbl.setText("✗  Not found — click Browse to locate the executable")
        lbl.setStyleSheet(f"color: {C.RED}; font-size: 8pt;")


# ── Keyring helpers ───────────────────────────────────────────────────────────

_KEYRING_SERVICE = "USSwing"


def _save_ibkr_password(username: str, password: str) -> bool:
    if not username or not password:
        return False
    try:
        import keyring  # type: ignore[import-untyped]
        keyring.set_password(_KEYRING_SERVICE, username, password)
        return True
    except Exception:
        return False


def _load_ibkr_password(username: str) -> str:
    if not username:
        return ""
    try:
        import keyring  # type: ignore[import-untyped]
        return keyring.get_password(_KEYRING_SERVICE, username) or ""
    except Exception:
        return ""


# Public alias used by main_window for startup auto-fill.
load_ibkr_password = _load_ibkr_password


def _delete_ibkr_password(username: str) -> None:
    if not username:
        return
    try:
        import keyring  # type: ignore[import-untyped]
        keyring.delete_password(_KEYRING_SERVICE, username)
    except Exception:
        pass


# ── TWS auto-fill helpers (Windows only, TEMP) ───────────────────────────────

def _find_tws_hwnd() -> int:
    """Return HWND of the first visible top-level window whose title looks like TWS login."""
    try:
        import ctypes
        import ctypes.wintypes
        u32 = ctypes.windll.user32  # type: ignore[attr-defined]
        result: list[int] = [0]
        keywords = ("login", "trader workstation", "ib gateway")

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def _cb(hwnd: int, _: int) -> bool:
            if result[0]:
                return False
            n = u32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if any(k in buf.value.lower() for k in keywords):
                    result[0] = hwnd
            return True

        u32.EnumWindows(_cb, 0)
        return result[0]
    except Exception:
        return 0


def _winapi_fill(username: str, password: str, tws_hwnd: int) -> str:
    """Type username, Tab, password into the TWS window identified by tws_hwnd.

    Returns "" on success or an error message string on failure.
    Aborts immediately if the TWS window loses focus mid-type.
    """
    try:
        import ctypes
        import time

        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP   = 0x0002
        INPUT_KEYBOARD    = 1
        VK_TAB    = 0x09
        VK_RETURN = 0x0D

        class _KI(ctypes.Structure):
            _fields_ = [
                ("wVk",         ctypes.c_ushort),
                ("wScan",       ctypes.c_ushort),
                ("dwFlags",     ctypes.c_ulong),
                ("time",        ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class _IU(ctypes.Union):
            _fields_ = [("ki", _KI), ("_pad", ctypes.c_byte * 28)]

        class _INP(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("_iu", _IU)]

        u32 = ctypes.windll.user32  # type: ignore[attr-defined]
        sz = ctypes.sizeof(_INP)

        def _tws_focused() -> bool:
            fg = u32.GetForegroundWindow()
            return bool(fg == tws_hwnd)

        def _send_unicode(ch: str) -> None:
            code = ord(ch)
            pair = (_INP * 2)()
            pair[0].type = INPUT_KEYBOARD
            pair[0]._iu.ki.wScan = code
            pair[0]._iu.ki.dwFlags = KEYEVENTF_UNICODE
            pair[1].type = INPUT_KEYBOARD
            pair[1]._iu.ki.wScan = code
            pair[1]._iu.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            u32.SendInput(2, pair, sz)

        def _send_vk(vk: int) -> None:
            pair = (_INP * 2)()
            pair[0].type = INPUT_KEYBOARD
            pair[0]._iu.ki.wVk = vk
            pair[1].type = INPUT_KEYBOARD
            pair[1]._iu.ki.wVk = vk
            pair[1]._iu.ki.dwFlags = KEYEVENTF_KEYUP
            u32.SendInput(2, pair, sz)

        if not _tws_focused():
            return "[Credentials] TWS lost focus before typing started."

        for ch in username:
            if not _tws_focused():
                return "[Credentials] TWS lost focus while typing username — fill cancelled."
            _send_unicode(ch)
            time.sleep(0.02)

        _send_vk(VK_TAB)
        time.sleep(0.5)

        if not _tws_focused():
            return "[Credentials] TWS lost focus before password — fill cancelled."

        for ch in password:
            if not _tws_focused():
                return "[Credentials] TWS lost focus while typing password — fill cancelled."
            _send_unicode(ch)
            time.sleep(0.02)

        time.sleep(1.5)
        if not _tws_focused():
            return "[Credentials] TWS lost focus before submitting — fill cancelled."
        _send_vk(VK_RETURN)
        return ""
    except Exception as exc:
        return f"[Credentials] Unexpected error during fill: {exc}"


class _FillWorker(QThread):
    """TEMP — focuses the TWS login window then types credentials via SendInput."""

    done: pyqtSignal = pyqtSignal(str)  # "" on success; error text on failure

    def __init__(self, username: str, password: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._username = username
        self._password = password

    def run(self) -> None:
        import time
        import ctypes

        hwnd = _find_tws_hwnd()
        if not hwnd:
            self.done.emit(
                "TWS login window not found.\n"
                "Open TWS and wait for the login form to appear, then click Fill again."
            )
            return

        u32 = ctypes.windll.user32  # type: ignore[attr-defined]
        u32.ShowWindow(hwnd, 9)  # SW_RESTORE
        _SWP_NO_MOVE_SIZE = 0x0003  # SWP_NOMOVE | SWP_NOSIZE
        u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, _SWP_NO_MOVE_SIZE)  # HWND_TOPMOST
        try:
            # AttachThreadInput lets us bypass Windows foreground-lock protection,
            # which silently ignores SetForegroundWindow when another app owns focus.
            cur_fg = u32.GetForegroundWindow()
            cur_tid = u32.GetWindowThreadProcessId(cur_fg, None)
            our_tid = ctypes.windll.kernel32.GetCurrentThreadId()  # type: ignore[attr-defined]
            attached = False
            if cur_tid and cur_tid != our_tid:
                attached = bool(u32.AttachThreadInput(our_tid, cur_tid, True))
            try:
                u32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            if attached:
                u32.AttachThreadInput(our_tid, cur_tid, False)

            # Confirm TWS actually has focus before typing (up to 2 s)
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if u32.GetForegroundWindow() == hwnd:
                    break
                time.sleep(0.05)
            else:
                self.done.emit(
                    "[Credentials] TWS login did not come to front.\n"
                    "Click the TWS window to focus it, then try Fill again."
                )
                return

            time.sleep(0.3)
            error = _winapi_fill(self._username, self._password, hwnd)
            self.done.emit(error)
        finally:
            u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, _SWP_NO_MOVE_SIZE)  # HWND_NOTOPMOST


# Public alias — used by main_window for startup auto-fill.
FillWorker = _FillWorker


# ── Frameless title bar ───────────────────────────────────────────────────────

class _DialogTitleBar(QWidget):
    """Custom title bar for frameless dialogs: title label + min/max/close."""

    _WC = (
        "QPushButton {{ background: transparent; color: {fg}; border: none;"
        " font-size: 14px; min-width: 32px; max-width: 32px;"
        " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
        "QPushButton:hover {{ background: {hover}; color: white; }}"
    )

    def __init__(self, title: str, window: QDialog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._win = window
        self._drag_pos = QPoint()
        self._maximised = False
        self._restore_geom = window.geometry()

        self.setObjectName("title_bar")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 4, 0)
        row.setSpacing(0)

        lbl = QLabel(title)
        lbl.setObjectName("top_brand")
        row.addWidget(lbl)
        row.addStretch()

        self._btn_min = QPushButton("−")
        self._btn_min.setStyleSheet(self._WC.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._btn_min.setToolTip("Minimize")
        self._btn_min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_max = QPushButton("□")
        self._btn_max.setStyleSheet(self._WC.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._btn_max.setToolTip("Maximize")
        self._btn_max.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_max.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_cls = QPushButton("✕")
        self._btn_cls.setStyleSheet(self._WC.format(fg=C.SUBTEXT, hover="#c0392b"))
        self._btn_cls.setToolTip("Close")
        self._btn_cls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cls.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_min.clicked.connect(window.showMinimized)
        self._btn_max.clicked.connect(self._toggle_max)
        self._btn_cls.clicked.connect(window.close)

        for btn in (self._btn_min, self._btn_max, self._btn_cls):
            row.addWidget(btn)

    def mousePressEvent(self, ev):  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):  # type: ignore[override]
        if ev.buttons() & Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self._win.move(ev.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(ev)

    def mouseDoubleClickEvent(self, ev):  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
        super().mouseDoubleClickEvent(ev)

    def _toggle_max(self) -> None:
        if self._maximised:
            self._win.setGeometry(self._restore_geom)
            self._btn_max.setText("□")
            self._btn_max.setToolTip("Maximize")
            self._maximised = False
        else:
            self._restore_geom = self._win.geometry()
            screen = self._win.screen() or QApplication.primaryScreen()
            self._win.setGeometry(screen.availableGeometry())
            self._btn_max.setText("❐")
            self._btn_max.setToolTip("Restore")
            self._maximised = True


# ── Dialog ────────────────────────────────────────────────────────────────────

class SchedulerDialog(QDialog):
    """Configure Windows Task Scheduler entries for USSwing and IBKR."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Windows Task Scheduler")
        self.setMinimumWidth(580)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        self._existing_usswing = load_usswing_config()
        self._existing_ibkr    = load_scheduler_config()
        self._existing_close   = load_close_config()
        self._ibkr_path_auto   = False
        self._fill_worker: _FillWorker | None = None

        self._build_ui()
        self._populate_usswing(self._existing_usswing)
        if self._existing_ibkr:
            self._populate_ibkr(self._existing_ibkr)
        else:
            self._detect_tws()
        self._populate_close(self._existing_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(_DialogTitleBar("🗓  Windows Task Scheduler", self))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(12)
        body_layout.setContentsMargins(12, 12, 12, 12)

        body_layout.addWidget(self._build_usswing_group())
        body_layout.addWidget(self._build_ibkr_group())
        body_layout.addWidget(self._build_close_group())
        body_layout.addWidget(self._build_note())
        body_layout.addLayout(self._build_buttons())

        root.addWidget(body)

    def _build_usswing_group(self) -> QGroupBox:
        grp = QGroupBox("USSwing Application")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._us_task_name = QLineEdit("USSwing_App")

        self._us_exe = QLineEdit()
        self._us_exe.setPlaceholderText(r"C:\Program Files (x86)\USSwing\USSwing.exe")
        self._us_exe.textChanged.connect(
            lambda t: _update_status_label(self._us_detect_lbl, t.strip() or None)
        )
        us_browse = QPushButton("Browse…")
        us_browse.setFixedWidth(80)
        us_browse.clicked.connect(self._on_us_browse)
        us_exe_row = QHBoxLayout()
        us_exe_row.setSpacing(6)
        us_exe_row.addWidget(self._us_exe)
        us_exe_row.addWidget(us_browse)

        self._us_detect_lbl = _make_status_label()

        self._us_time = QTimeEdit()
        self._us_time.setDisplayFormat("hh:mm AP")
        self._us_time.setTime(QTime(9, 0))

        self._us_days = QComboBox()
        self._us_days.addItems(["Weekdays (Mon–Fri)", "Daily (every day)"])

        us_sched_row = QHBoxLayout()
        us_sched_row.setSpacing(6)
        us_sched_row.addWidget(QLabel("Time:"), 0)
        us_sched_row.addWidget(self._us_time, 1)
        us_sched_row.addWidget(QLabel("Days:"), 0)
        us_sched_row.addWidget(self._us_days, 1)

        form.addRow("Task name:",   self._us_task_name)
        form.addRow("Executable:",  us_exe_row)
        form.addRow("",             self._us_detect_lbl)
        form.addRow("Schedule:",    us_sched_row)
        return grp

    def _build_ibkr_group(self) -> QGroupBox:
        grp = QGroupBox("Trader Workstation (TWS)")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._ibkr_task_name = QLineEdit("USSwing_IBKR")

        self._ibkr_exe = QLineEdit()
        self._ibkr_exe.setPlaceholderText("Auto-detecting…")
        self._ibkr_exe.textChanged.connect(
            lambda t: _update_status_label(self._ibkr_detect_lbl, t.strip() or None)
        )
        ibkr_browse = QPushButton("Browse…")
        ibkr_browse.setFixedWidth(80)
        ibkr_browse.clicked.connect(self._on_ibkr_browse)
        ibkr_exe_row = QHBoxLayout()
        ibkr_exe_row.setSpacing(6)
        ibkr_exe_row.addWidget(self._ibkr_exe)
        ibkr_exe_row.addWidget(ibkr_browse)

        self._ibkr_detect_lbl = _make_status_label()

        self._ibkr_time = QTimeEdit()
        self._ibkr_time.setDisplayFormat("hh:mm AP")
        self._ibkr_time.setTime(QTime(9, 0))

        self._ibkr_days = QComboBox()
        self._ibkr_days.addItems(["Weekdays (Mon–Fri)", "Daily (every day)"])

        ibkr_sched_row = QHBoxLayout()
        ibkr_sched_row.setSpacing(6)
        ibkr_sched_row.addWidget(QLabel("Time:"), 0)
        ibkr_sched_row.addWidget(self._ibkr_time, 1)
        ibkr_sched_row.addWidget(QLabel("Days:"), 0)
        ibkr_sched_row.addWidget(self._ibkr_days, 1)

        form.addRow("Task name:",   self._ibkr_task_name)
        form.addRow("Executable:",  ibkr_exe_row)
        form.addRow("",             self._ibkr_detect_lbl)
        form.addRow("Schedule:",    ibkr_sched_row)

        # ── Auto Login ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        cred_hdr = QLabel("Auto Login")
        cred_hdr.setStyleSheet("font-weight: 600;")

        self._ibkr_user = QLineEdit()
        self._ibkr_user.setPlaceholderText("IBKR username")

        self._ibkr_pwd = QLineEdit()
        self._ibkr_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._ibkr_pwd.setPlaceholderText("IBKR password")

        self._eye_btn = QPushButton("👁")
        self._eye_btn.setCheckable(True)
        self._eye_btn.setFixedWidth(65)
        self._eye_btn.setToolTip("Show / hide password")
        self._eye_btn.toggled.connect(self._on_eye_toggled)

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(6)
        pwd_row.addWidget(self._ibkr_pwd)
        pwd_row.addWidget(self._eye_btn)

        self._ibkr_auto_login = QCheckBox("Auto Fill Credential")

        # TEMP: remove after auto-login testing is complete
        self._fill_btn = QPushButton("⌨  Fill TWS Login")
        self._fill_btn.setFixedWidth(145)
        self._fill_btn.setToolTip(
            "Open TWS manually, wait for its login form, then click here.\n"
            "USSwing will focus TWS and type the credentials for you."
        )
        self._fill_btn.clicked.connect(self._on_fill_tws)

        self._save_cred_btn = QPushButton("💾  Save Credentials")
        self._save_cred_btn.setFixedWidth(145)
        self._save_cred_btn.clicked.connect(self._on_save_credentials)

        # Single row: [checkbox ──stretch── Fill TWS Login | Save Credentials]
        # Save Credentials sits flush-right, aligning with the eye button above.
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(self._ibkr_auto_login)
        action_row.addStretch()
        action_row.addWidget(self._fill_btn)
        action_row.addWidget(self._save_cred_btn)

        keyring_note = QLabel(
            "Password is saved in Windows Credential Manager — never written to disk."
        )
        keyring_note.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
        keyring_note.setWordWrap(True)

        form.addRow(sep)
        form.addRow(cred_hdr)
        form.addRow("Username:", self._ibkr_user)
        form.addRow("Password:", pwd_row)
        form.addRow("",          action_row)
        form.addRow(keyring_note)

        return grp

    def _build_close_group(self) -> QGroupBox:
        grp = QGroupBox("Auto Close")
        v = QVBoxLayout(grp)
        v.setSpacing(6)

        self._close_enabled = QCheckBox("Close both apps automatically at")
        self._close_enabled.toggled.connect(self._on_close_toggled)

        self._close_time = QTimeEdit()
        self._close_time.setDisplayFormat("hh:mm AP")
        self._close_time.setTime(QTime(16, 30))
        self._close_time.setFixedWidth(110)
        self._close_time.setEnabled(False)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._close_enabled)
        row.addWidget(self._close_time)
        row.addStretch()
        v.addLayout(row)

        note = QLabel(
            "Force-closes USSwing and Trader Workstation at this time so they don't stay open."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
        v.addWidget(note)
        return grp

    def _build_note(self) -> QLabel:
        note = QLabel(
            "ℹ  Tasks launch as your Windows user account.  "
            "When auto-login is enabled, USSwing passes credentials to TWS on startup — "
            "you still need to approve the IBKR mobile 2FA from your phone."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt; padding: 4px 0;")
        return note

    def _build_buttons(self) -> QHBoxLayout:
        has_any = bool(self._existing_usswing or self._existing_ibkr or self._existing_close.enabled)
        action_label = "📅  Update Tasks" if has_any else "📅  Add Tasks"

        self._remove_btn = QPushButton("🗑  Remove All Tasks")
        self._remove_btn.setObjectName("danger_btn")
        self._remove_btn.clicked.connect(self._on_remove)
        self._remove_btn.setVisible(has_any)

        self._ok_btn = QPushButton(action_label)
        self._ok_btn.setObjectName("run_btn")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_add_or_update)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self._remove_btn)
        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(self._ok_btn)
        return row

    # ── Population ────────────────────────────────────────────────────────────

    def _populate_usswing(self, cfg: USSwingConfig | None) -> None:
        if cfg:
            self._us_task_name.setText(cfg.task_name)
            self._us_exe.setText(cfg.exe_path)
            try:
                h, m = cfg.launch_time.split(":")
                self._us_time.setTime(QTime(int(h), int(m)))
            except ValueError:
                pass
            self._us_days.setCurrentIndex(0 if cfg.days == "weekdays" else 1)
        else:
            # Set default path and let the status label react
            default = str(_USSWING_DEFAULT)
            self._us_exe.setText(default)

    def _populate_ibkr(self, cfg: SchedulerConfig) -> None:
        self._ibkr_task_name.setText(cfg.task_name)
        self._set_ibkr_path(cfg.exe_path, auto=False)
        try:
            h, m = cfg.launch_time.split(":")
            self._ibkr_time.setTime(QTime(int(h), int(m)))
        except ValueError:
            pass
        self._ibkr_days.setCurrentIndex(0 if cfg.days == "weekdays" else 1)
        self._ibkr_user.setText(cfg.ibkr_username)
        self._ibkr_auto_login.setChecked(cfg.auto_login)
        if cfg.ibkr_username:
            stored_pwd = _load_ibkr_password(cfg.ibkr_username)
            if stored_pwd:
                self._ibkr_pwd.setText(stored_pwd)

    def _populate_close(self, cfg: CloseConfig) -> None:
        self._close_enabled.setChecked(cfg.enabled)
        self._close_time.setEnabled(cfg.enabled)
        try:
            h, m = cfg.close_time.split(":")
            self._close_time.setTime(QTime(int(h), int(m)))
        except ValueError:
            pass

    def _detect_tws(self) -> None:
        found = find_tws_exe()
        self._set_ibkr_path(found or "", auto=found is not None)

    def _set_ibkr_path(self, path: str, *, auto: bool) -> None:
        self._ibkr_path_auto = auto
        self._ibkr_exe.blockSignals(True)
        self._ibkr_exe.setText(path)
        self._ibkr_exe.blockSignals(False)
        _update_status_label(self._ibkr_detect_lbl, path or None)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_close_toggled(self, checked: bool) -> None:
        self._close_time.setEnabled(checked)

    def _on_us_browse(self) -> None:
        start = str(Path(r"C:\Program Files (x86)\USSwing"))
        if not Path(start).exists():
            start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Select USSwing Executable", start, "Executables (*.exe)"
        )
        if path:
            self._us_exe.setText(path)

    def _on_ibkr_browse(self) -> None:
        start = str(Path("C:/Jts")) if Path("C:/Jts").exists() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Select IBKR Executable", start, "Executables (*.exe)"
        )
        if path:
            self._set_ibkr_path(path, auto=False)

    def _on_add_or_update(self) -> None:
        us_cfg   = self._collect_usswing()
        ibkr_cfg = self._collect_ibkr()

        # Close tasks act on the same apps regardless of whether the launch task
        # is (re)created this round, so capture targets before the not-found flow.
        us_close_target   = us_cfg
        ibkr_close_target = ibkr_cfg

        if us_cfg is None and ibkr_cfg is None:
            QMessageBox.warning(
                self, "Nothing to Schedule",
                "Provide at least one executable path to create a scheduled task."
            )
            return

        errors: list[str] = []
        created: list[str] = []

        # ── USSwing task ──
        if us_cfg is not None:
            if not Path(us_cfg.exe_path).exists():
                ret = QMessageBox.question(
                    self, "File Not Found",
                    f"USSwing executable not found:\n{us_cfg.exe_path}\n\nAdd the task anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ret != QMessageBox.StandardButton.Yes:
                    us_cfg = None

        if us_cfg is not None:
            ok, msg = create_usswing_task(us_cfg)
            if ok:
                save_usswing_config(us_cfg)
                created.append(f"• {us_cfg.task_name} (USSwing App)")
            else:
                errors.append(f"USSwing task failed:\n{msg}")

        # ── IBKR task ──
        if ibkr_cfg is not None:
            if not Path(ibkr_cfg.exe_path).exists():
                ret = QMessageBox.question(
                    self, "File Not Found",
                    f"IBKR executable not found:\n{ibkr_cfg.exe_path}\n\nAdd the task anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ret != QMessageBox.StandardButton.Yes:
                    ibkr_cfg = None

        if ibkr_cfg is not None:
            pwd = self._ibkr_pwd.text()
            if ibkr_cfg.auto_login and ibkr_cfg.ibkr_username:
                if not _save_ibkr_password(ibkr_cfg.ibkr_username, pwd):
                    QMessageBox.warning(
                        self, "Credential Storage",
                        "Could not save the password to Windows Credential Manager.\n"
                        "Ensure the keyring package is installed.\n\n"
                        "The task will be created without auto-login.",
                    )
                    ibkr_cfg.auto_login = False
                    pwd = ""
            ok, msg = create_ibkr_task(ibkr_cfg, pwd)
            if ok:
                save_scheduler_config(ibkr_cfg)
                created.append(f"• {ibkr_cfg.task_name} (Trader Workstation)")
            else:
                errors.append(f"IBKR task failed:\n{msg}")

        # ── Auto-close tasks ──
        close_cfg = self._collect_close()
        us_close_name   = (self._us_task_name.text().strip()   or "USSwing_App")  + "_Close"
        ibkr_close_name = (self._ibkr_task_name.text().strip() or "USSwing_IBKR") + "_Close"
        if close_cfg.enabled:
            if us_close_target is not None:
                ok, msg = create_usswing_close_task(us_close_target, close_cfg.close_time)
                if ok:
                    created.append(f"• {us_close_name} (auto-close)")
                else:
                    errors.append(f"USSwing close task failed:\n{msg}")
            if ibkr_close_target is not None:
                ok, msg = create_ibkr_close_task(ibkr_close_target, close_cfg.close_time)
                if ok:
                    created.append(f"• {ibkr_close_name} (auto-close)")
                else:
                    errors.append(f"IBKR close task failed:\n{msg}")
        elif self._existing_close.enabled:
            # Auto-close was turned off — remove any close tasks created earlier.
            delete_task(us_close_name)
            delete_task(ibkr_close_name)
        save_close_config(close_cfg)
        self._existing_close = close_cfg

        if created:
            QMessageBox.information(
                self, "Tasks Scheduled",
                "✔  The following tasks were created in Windows Task Scheduler:\n\n"
                + "\n".join(created),
            )
        if errors:
            QMessageBox.critical(
                self, "Task Creation Failed",
                "\n\n".join(errors)
                + "\n\nIf the error mentions permissions, try running as Administrator.",
            )

        if created:
            self.accept()

    def _on_remove(self) -> None:
        tasks_to_remove: list[str] = []
        if self._existing_usswing:
            tasks_to_remove.append(self._us_task_name.text().strip() or "USSwing_App")
        if self._existing_ibkr:
            tasks_to_remove.append(self._ibkr_task_name.text().strip() or "USSwing_IBKR")

        names = "\n".join(f"• {t}" for t in tasks_to_remove)
        ret = QMessageBox.question(
            self, "Remove Scheduled Tasks",
            f"Remove these tasks from Windows Task Scheduler?\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        errors: list[str] = []
        if self._existing_usswing:
            ok, msg = delete_task(tasks_to_remove[0])
            if ok:
                delete_usswing_config()
            else:
                errors.append(f"USSwing task: {msg}")

        if self._existing_ibkr:
            ok, msg = delete_task(tasks_to_remove[-1])
            if ok:
                _delete_ibkr_password(self._existing_ibkr.ibkr_username)
                delete_scheduler_config()
            else:
                errors.append(f"IBKR task: {msg}")

        if self._existing_close.enabled:
            us_close   = (self._us_task_name.text().strip()   or "USSwing_App")  + "_Close"
            ibkr_close = (self._ibkr_task_name.text().strip() or "USSwing_IBKR") + "_Close"
            delete_task(us_close)
            delete_task(ibkr_close)
        delete_close_config()

        if errors:
            QMessageBox.critical(self, "Removal Failed", "\n".join(errors))
        else:
            QMessageBox.information(self, "Tasks Removed", "✔  Scheduled tasks have been removed.")
            self.accept()

    # ── Collect helpers ───────────────────────────────────────────────────────

    def _collect_usswing(self) -> USSwingConfig | None:
        exe = self._us_exe.text().strip()
        if not exe:
            return None
        t = self._us_time.time()
        return USSwingConfig(
            task_name=self._us_task_name.text().strip() or "USSwing_App",
            exe_path=exe,
            launch_time=f"{t.hour():02d}:{t.minute():02d}",
            days="weekdays" if self._us_days.currentIndex() == 0 else "daily",
        )

    def _collect_ibkr(self) -> SchedulerConfig | None:
        exe = self._ibkr_exe.text().strip()
        if not exe:
            return None
        t = self._ibkr_time.time()
        return SchedulerConfig(
            task_name=self._ibkr_task_name.text().strip() or "USSwing_IBKR",
            exe_path=exe,
            launch_time=f"{t.hour():02d}:{t.minute():02d}",
            days="weekdays" if self._ibkr_days.currentIndex() == 0 else "daily",
            ibkr_username=self._ibkr_user.text().strip(),
            auto_login=self._ibkr_auto_login.isChecked(),
        )

    def _collect_close(self) -> CloseConfig:
        t = self._close_time.time()
        return CloseConfig(
            enabled=self._close_enabled.isChecked(),
            close_time=f"{t.hour():02d}:{t.minute():02d}",
        )

    # ── Credential helpers ────────────────────────────────────────────────────

    def _on_eye_toggled(self, checked: bool) -> None:
        self._ibkr_pwd.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _on_save_credentials(self) -> None:
        username = self._ibkr_user.text().strip()
        password = self._ibkr_pwd.text()
        if not username:
            QMessageBox.warning(self, "Save Credentials", "Enter a username first.")
            return
        if not password:
            QMessageBox.warning(self, "Save Credentials", "Enter a password first.")
            return
        if _save_ibkr_password(username, password):
            # Persist auto_login flag + current form state so checkbox survives dialog re-open
            cfg = self._collect_ibkr()
            if cfg is None:
                cfg = SchedulerConfig(
                    ibkr_username=username,
                    auto_login=self._ibkr_auto_login.isChecked(),
                )
            save_scheduler_config(cfg)
            self._existing_ibkr = cfg
            QMessageBox.information(
                self, "Save Credentials",
                "✔  Password saved to Windows Credential Manager.",
            )
        else:
            QMessageBox.warning(
                self, "Save Credentials",
                "Could not save password.\n"
                "Run:  pip install keyring  then try again.",
            )

    # ── TEMP: Fill TWS Login ──────────────────────────────────────────────────

    def _on_fill_tws(self) -> None:
        if self._fill_worker is not None and self._fill_worker.isRunning():
            return
        username = self._ibkr_user.text().strip()
        password = self._ibkr_pwd.text()
        if not username or not password:
            QMessageBox.warning(self, "Fill TWS", "Enter username and password first.")
            return
        self._fill_btn.setEnabled(False)
        self._fill_btn.setText("Filling…")
        self._fill_worker: _FillWorker = _FillWorker(username, password, self)
        self._fill_worker.done.connect(self._on_fill_done)
        self._fill_worker.start()

    def _on_fill_done(self, error: str) -> None:
        self._fill_btn.setEnabled(True)
        self._fill_btn.setText("⌨  Fill TWS Login")
        if error:
            QMessageBox.warning(self, "Fill TWS", error)
        else:
            QMessageBox.information(
                self, "Fill TWS",
                "✔  Credentials typed and Log In clicked.\n"
                "Approve the 2FA prompt on your phone to complete login.",
            )
