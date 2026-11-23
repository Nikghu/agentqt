"""Tests for MD-EXE-022.008.M03 — core/indicator_plugins/_registry.py."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from tests.execution.plugin_helpers import SWING_PLUS, frames, swing_plus_source, write_plugin
from us_swing.core.indicator_plugins import IndicatorRegistry, plugin_dir

_BUILTINS = {"EMA", "SWING", "BOSS_ST"}


def _install(root: Path, user_id: int, name: str = "swing_plus.py",
             text: str | None = None) -> Path:
    folder = plugin_dir(user_id, root)
    folder.mkdir(parents=True, exist_ok=True)
    if text is None:
        return Path(shutil.copy(SWING_PLUS, folder / name))
    return write_plugin(folder, name, text)


def test_only_active_users_folder_loads(tmp_path: Path) -> None:
    """UT-EXE-022.008.M03.T01: Only the active user's folder is loaded."""
    _install(tmp_path, 1)
    _install(tmp_path, 2, "other.py", swing_plus_source(
        ('indicator_name = "SWING_PLUS"', 'indicator_name = "USER_TWO"')))
    registry = IndicatorRegistry(tmp_path)

    registry.load_for_user(1, builtins=_BUILTINS)

    assert registry.names() == {"SWING_PLUS"}
    assert registry.user_id == 1


def test_other_users_indicator_unknown(tmp_path: Path) -> None:
    """UT-EXE-022.008.M03.T02: A second user does not see the first user's indicator."""
    _install(tmp_path, 1)
    registry = IndicatorRegistry(tmp_path)

    registry.load_for_user(2, builtins=_BUILTINS)

    assert registry.get("SWING_PLUS") is None
    assert registry.statuses() == ()


def test_good_loaded_broken_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.009.M03.T01: A good file loads; a broken one is listed with its reason."""
    _install(tmp_path, 1)
    _install(tmp_path, 1, "broken.py", "def oops(:\n")
    registry = IndicatorRegistry(tmp_path)

    with caplog.at_level(logging.INFO):
        registry.load_for_user(1, builtins=_BUILTINS,
                               candle_probe=lambda: [("AAA", frames(60))])

    assert registry.names() == {"SWING_PLUS"}
    broken = next(s for s in registry.statuses() if s.file == "broken.py")
    assert not broken.ok and broken.reasons[0].startswith("syntax error on line 1")
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [f"[Indicators] broken.py was not loaded: {broken.reasons[0]}"]
    assert "[Indicators] Loaded 1 of 2 custom indicator(s)" in caplog.text


def test_reload_after_file_removed(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T02: Reloading after a file is removed drops it; listeners run."""
    path = _install(tmp_path, 1)
    registry = IndicatorRegistry(tmp_path)
    calls: list[int] = []
    registry.add_listener(lambda: calls.append(1))

    registry.load_for_user(1, builtins=_BUILTINS)
    path.unlink()
    registry.load_for_user(1, builtins=_BUILTINS)

    assert registry.names() == frozenset()
    assert calls == [1, 1]


def test_exit_while_loading_does_not_stop(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T03: A file calling sys.exit() is skipped; other files still load."""
    _install(tmp_path, 1, "a_exit.py", "import sys\nsys.exit()\n")
    _install(tmp_path, 1)
    registry = IndicatorRegistry(tmp_path)

    registry.load_for_user(1, builtins=_BUILTINS)

    assert registry.names() == {"SWING_PLUS"}
    exiting = next(s for s in registry.statuses() if s.file == "a_exit.py")
    assert exiting.reasons == ("stopped while loading (sys.exit was called)",)


def test_same_name_twice_keeps_first(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T01 (part): A second file with a taken name is refused."""
    _install(tmp_path, 1, "a.py")
    _install(tmp_path, 1, "b.py")
    registry = IndicatorRegistry(tmp_path)

    registry.load_for_user(1, builtins=_BUILTINS)

    second = next(s for s in registry.statuses() if s.file == "b.py")
    assert registry.names() == {"SWING_PLUS"}
    assert second.reasons == ('name "SWING_PLUS" is already used by another of your indicators',)
