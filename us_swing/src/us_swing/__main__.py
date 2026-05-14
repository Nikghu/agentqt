"""Entry point — ``python -m us_swing [command]``

Commands:
    (none)   Launch the GUI in paper mode (default).
    health   Print a JSON health report and exit.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path


# ── Log directory: ~/.usswing/logs/<date>.log ─────────────────────────────────
_LOG_DIR = Path.home() / ".usswing" / "logs"


def _setup_logging() -> None:
    """Initialise file + stderr logging before anything else starts."""
    import os
    from us_swing.monitoring.logging_setup import configure_logging
    level = os.environ.get("LOG_LEVEL", "INFO")
    configure_logging(_LOG_DIR, level=level)


def _run_updater() -> None:
    try:
        from updater_stub import check_for_updates  # type: ignore[import]
        check_for_updates(interactive=True)
    except Exception:
        pass


def _patch_ib_del() -> None:
    # IB.__del__ calls disconnect() during GC, which fails if the asyncio event loop
    # is already closed (harmless but noisy on Windows ProactorEventLoop).
    try:
        import ib_insync
        _orig = ib_insync.IB.__del__

        def _safe_del(self: ib_insync.IB) -> None:
            try:
                _orig(self)
            except Exception:
                pass

        ib_insync.IB.__del__ = _safe_del  # type: ignore[method-assign]
    except Exception:
        pass


def _cmd_gui() -> None:
    import os

    _patch_ib_del()

    # Suppress Chromium DirectComposition warning on GPUs that don't support
    # IDCompositionDevice4 (harmless, but floods the console on some Windows setups).
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-direct-composition")

    from PyQt6.QtWidgets import QApplication

    from us_swing.gui.app_service import AppService
    from us_swing.gui.main_window import MainWindow
    from us_swing.gui.theme import QSS

    threading.Thread(target=_run_updater, daemon=True).start()

    app = QApplication(sys.argv)
    app.setApplicationName("US Swing Trader")
    app.setOrganizationName("USSwing")
    app.setStyleSheet(QSS)

    svc    = AppService()
    window = MainWindow(svc)
    window.showMaximized()
    sys.exit(app.exec())


def _cmd_health() -> None:
    from us_swing.monitoring.health import HealthCheck

    check = HealthCheck()  # no broker / DB connected in standalone health check
    report = check.report()
    print(json.dumps(report, indent=2, default=str))


def main() -> None:
    _setup_logging()
    command = sys.argv[1] if len(sys.argv) > 1 else "gui"
    if command == "health":
        _cmd_health()
    else:
        _cmd_gui()


if __name__ == "__main__":
    main()
