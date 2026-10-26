"""GUI test fixtures shared by every test in tests/gui."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests away from the real scheduler.json, TWS install, keyring and Windows tasks.

    The Settings Scheduler section (FO-GUI-029) loads all of these when it is built.
    """
    from us_swing.gui import scheduler_dialog as sd
    from us_swing.gui import scheduler_store as ss

    monkeypatch.setattr(ss, "_APP_DIR", tmp_path / ".usswing")
    monkeypatch.setattr(ss, "_STORE_FILE", tmp_path / ".usswing" / "scheduler.json")
    monkeypatch.setattr(sd, "find_tws_exe", lambda: None)
    monkeypatch.setattr(sd, "load_ibkr_password", lambda _user: "")
    monkeypatch.setattr(sd, "_save_ibkr_password", lambda _user, _pwd: True)
    monkeypatch.setattr(sd, "_delete_ibkr_password", lambda _user: None)
    monkeypatch.setattr(sd, "_run_schtasks", lambda *_args: (False, "blocked in tests"))
