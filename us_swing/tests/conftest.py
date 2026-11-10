"""Root conftest — adds us_swing/src to sys.path for src-layout imports."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def _private_users_file(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the users store at a temp folder so no test rewrites ~/.usswing/users.json.

    Tests that patch ``load_users`` to ``[]`` make ``AppService`` save a default
    paper user, which reset the real user's mode to paper (ISS-GUI-0013).
    """
    import us_swing.data  # noqa: F401  — load data before db (db ↔ data import cycle)
    from us_swing.gui import user_store

    folder = tmp_path_factory.mktemp("usswing")
    monkeypatch.setattr(user_store, "_APP_DIR", folder)
    monkeypatch.setattr(user_store, "_STORE_FILE", folder / "users.json")
    from us_swing.core.notifications import _briefs
    monkeypatch.setattr(_briefs, "SEND_LOG_PATH", folder / "notify_state.json")
    from us_swing.core import desk_alerts
    monkeypatch.setattr(desk_alerts, "USERS_FILE", folder / "users.json")
