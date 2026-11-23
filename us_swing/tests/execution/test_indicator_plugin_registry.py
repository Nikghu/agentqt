"""Tests for MD-EXE-022.008.M03 — core/indicator_plugins/_registry.py."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from tests.execution.plugin_helpers import SWING_PLUS, frames, swing_plus_source, write_plugin
from us_swing.core.indicator_plugins import IndicatorRegistry, plugin_dir

_BUILTINS = {"EMA", "SWING", "BOSS_ST"}


def _install(root: Path, name: str = "swing_plus.py", text: str | None = None) -> Path:
    folder = plugin_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    if text is None:
        return Path(shutil.copy(SWING_PLUS, folder / name))
    return write_plugin(folder, name, text)


def test_shared_folder_loads(tmp_path: Path) -> None:
    """UT-EXE-022.008.M03.T01: Every file in the shared indicator folder is loaded."""
    _install(tmp_path)
    _install(tmp_path, "other.py", swing_plus_source(
        ('indicator_name = "SWING_PLUS"', 'indicator_name = "OTHER_ONE"')))
    registry = IndicatorRegistry(tmp_path)

    registry.load(builtins=_BUILTINS)

    assert plugin_dir(tmp_path) == tmp_path / "indicators"
    assert registry.names() == {"SWING_PLUS", "OTHER_ONE"}


def test_old_user_folders_moved_once(tmp_path: Path) -> None:
    """UT-EXE-022.008.M03.T02: Old per-user folders move to the shared ones; clashes stay."""
    old = tmp_path / "1"
    (old / "indicators").mkdir(parents=True)
    (old / "projects" / "my_st").mkdir(parents=True)
    shutil.copy(SWING_PLUS, old / "indicators" / "swing_plus.py")
    (old / "projects" / "my_st" / "my_st.py").write_text("# mine\n", encoding="utf-8")
    (tmp_path / "2" / "indicators").mkdir(parents=True)
    (tmp_path / "2" / "indicators" / "swing_plus.py").write_text("# clash\n", encoding="utf-8")
    registry = IndicatorRegistry(tmp_path)

    registry.load(builtins=_BUILTINS)

    assert registry.names() == {"SWING_PLUS"}
    assert (tmp_path / "projects" / "my_st" / "my_st.py").read_text(encoding="utf-8") == "# mine\n"
    assert not old.exists()
    assert (tmp_path / "2" / "indicators" / "swing_plus.py").exists()


def test_locked_old_folder_does_not_stop_load(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.008.M03.T03: An item that cannot be moved stays; the rest still loads."""
    (tmp_path / "1" / "projects" / "busy").mkdir(parents=True)
    _install(tmp_path)

    def locked(_source: str, _target: str) -> None:
        raise PermissionError("in use")

    monkeypatch.setattr(shutil, "move", locked)
    registry = IndicatorRegistry(tmp_path)

    with caplog.at_level(logging.WARNING):
        registry.load(builtins=_BUILTINS)

    assert registry.names() == {"SWING_PLUS"}
    assert (tmp_path / "1" / "projects" / "busy").is_dir()
    assert "trying again on the next start" in caplog.text


def test_good_loaded_broken_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.009.M03.T01: A good file loads; a broken one is listed with its reason."""
    _install(tmp_path)
    _install(tmp_path, "broken.py", "def oops(:\n")
    registry = IndicatorRegistry(tmp_path)

    with caplog.at_level(logging.INFO):
        registry.load(builtins=_BUILTINS,
                      candle_probe=lambda: [("AAA", frames(60))])

    assert registry.names() == {"SWING_PLUS"}
    broken = next(s for s in registry.statuses() if s.file == "broken.py")
    assert not broken.ok and broken.reasons[0].startswith("syntax error on line 1")
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [f"[Indicators] broken.py was not loaded: {broken.reasons[0]}"]
    assert "[Indicators] Loaded 1 of 2 custom indicator(s)" in caplog.text


def test_reload_after_file_removed(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T02: Reloading after a file is removed drops it; listeners run."""
    path = _install(tmp_path)
    registry = IndicatorRegistry(tmp_path)
    calls: list[int] = []
    registry.add_listener(lambda: calls.append(1))

    registry.load(builtins=_BUILTINS)
    path.unlink()
    registry.load(builtins=_BUILTINS)

    assert registry.names() == frozenset()
    assert calls == [1, 1]


def test_exit_while_loading_does_not_stop(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T03: A file calling sys.exit() is skipped; other files still load."""
    _install(tmp_path, "a_exit.py", "import sys\nsys.exit()\n")
    _install(tmp_path)
    registry = IndicatorRegistry(tmp_path)

    registry.load(builtins=_BUILTINS)

    assert registry.names() == {"SWING_PLUS"}
    exiting = next(s for s in registry.statuses() if s.file == "a_exit.py")
    assert exiting.reasons == ("stopped while loading (sys.exit was called)",)


def test_candle_read_error_still_loads(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.009.M03.T03 (review fix): A candle read error skips the dry run, not the load."""
    _install(tmp_path)
    registry = IndicatorRegistry(tmp_path)

    def broken_probe() -> list:  # type: ignore[type-arg]
        raise OSError("database is locked")

    with caplog.at_level(logging.WARNING):
        registry.load(builtins=_BUILTINS, candle_probe=broken_probe)

    assert registry.names() == {"SWING_PLUS"}
    assert registry.statuses()[0].notes == ("not checked on candles (no candle data yet)",)
    assert "[Indicators] Could not read candles for the indicator check" in caplog.text


def test_same_name_twice_keeps_first(tmp_path: Path) -> None:
    """UT-EXE-022.009.M03.T01 (part): A second file with a taken name is refused."""
    _install(tmp_path, "a.py")
    _install(tmp_path, "b.py")
    registry = IndicatorRegistry(tmp_path)

    registry.load(builtins=_BUILTINS)

    second = next(s for s in registry.statuses() if s.file == "b.py")
    assert registry.names() == {"SWING_PLUS"}
    assert second.reasons == ('name "SWING_PLUS" is already used by another of your indicators',)
