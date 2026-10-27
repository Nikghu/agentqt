"""Tests for the Carbon theme and icon system (FO-GUI-017)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QPushButton

from us_swing.gui import icons, theme

_GUI_DIR = Path(theme.__file__).parent
# Status-message warning sign (U+26A0) is allowed; it is text, not an emoji icon.
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-⚟⚡-⛿➕✎⬇⟳⏸＋]")
_WIDGET_TEXT = re.compile(r"(QPushButton|addTab|QAction|setText)\(([^)]*)\)")


@pytest.fixture()
def theme_file(tmp_path, monkeypatch):
    path = tmp_path / "theme_id"
    monkeypatch.setattr(theme, "_THEME_PREF_FILE", path)
    monkeypatch.setattr(theme, "_theme_id", None)
    icons.clear_cache()
    yield path
    icons.clear_cache()


def test_carbon_is_default(theme_file):
    """UT-GUI-017.001.M02.T01: Carbon is the default theme."""
    assert theme.load_theme_id() == "carbon"
    assert theme.active_palette().BG == "#0c0f13"


def test_unknown_theme_falls_back_to_carbon(theme_file):
    """UT-GUI-017.001.M02.T02: Unknown saved theme falls back to Carbon."""
    theme_file.write_text("neon", encoding="utf-8")
    assert theme.load_theme_id() == "carbon"


def test_theme_file_read_once(theme_file):
    """UT-GUI-000.008.M01.T01: The theme file is read once; later colour lookups use memory."""
    theme_file.write_text("mocha", encoding="utf-8")
    assert theme.load_theme_id() == "mocha"

    theme_file.write_text("vscode", encoding="utf-8")

    assert theme.load_theme_id() == "mocha"
    assert theme.C.BG == theme._PALETTES["mocha"].BG


def test_saved_theme_used_at_once(theme_file):
    """UT-GUI-000.008.M01.T02: Saving a theme updates lookups and the file."""
    assert theme.load_theme_id() == "carbon"

    theme.save_theme_id("vscode")

    assert theme.load_theme_id() == "vscode"
    assert theme_file.read_text(encoding="utf-8") == "vscode"

    theme.save_theme_id("neon")

    assert theme.load_theme_id() == "carbon"


def test_carbon_qss_has_no_mocha_colours(theme_file):
    """UT-GUI-017.001.M02.T03: Carbon QSS has no Mocha colours left and same colour keys."""
    used = set(re.findall(r"#[0-9a-f]{6}", theme.CARBON_QSS))
    assert not used & set(theme._MOCHA_TO_CARBON)
    assert set(theme.THEME_COLORS["carbon"]) == set(theme.THEME_COLORS["mocha"])


def test_bad_font_file_is_skipped(qapp, tmp_path, caplog):
    """UT-GUI-017.002.M02.T01: Missing font file does not stop the app."""
    good = theme.asset_dir("fonts") / "IBMPlexMono-Regular.ttf"
    (tmp_path / "a_good.ttf").write_bytes(good.read_bytes())
    (tmp_path / "b_bad.ttf").write_bytes(b"not a font")
    with caplog.at_level(logging.WARNING):
        theme.load_fonts(tmp_path)
    assert any("[Theme]" in r.message and "b_bad.ttf" in r.message for r in caplog.records)
    assert not any("a_good.ttf" in r.message for r in caplog.records)


def test_icon_uses_role_colour(qapp, theme_file, monkeypatch):
    """UT-GUI-017.003.M01.T01: Icon is built in the role colour."""
    seen: list[str] = []
    real_render = icons._render

    def spy(svg: str, colour: str, size: int):
        seen.append(colour)
        return real_render(svg, colour, size)

    monkeypatch.setattr(icons, "_render", spy)
    result = icons.icon("plus", "add")
    assert not result.isNull()
    assert theme.C.GREEN in seen


def test_unknown_icon_is_empty(qapp, theme_file, caplog):
    """UT-GUI-017.003.M01.T02: Unknown icon name."""
    with caplog.at_level(logging.WARNING):
        result = icons.icon("nope")
    assert result.isNull()
    assert any(r.message.startswith("[Theme]") for r in caplog.records)


def test_icon_cache_reuse_and_clear(qapp, theme_file):
    """UT-GUI-017.003.M01.T03: Cache reuses and clears."""
    first = icons.icon("save")
    assert icons.icon("save") is first
    icons.clear_cache()
    assert not icons._cache


def test_icon_button_has_tooltip(qapp, theme_file):
    """UT-GUI-017.003.M01.T04: Icon-only button has tooltip and accessible name."""
    button = icons.icon_button("refresh-cw", "info", "Refresh")
    assert button.toolTip() == "Refresh"
    assert button.accessibleName() == "Refresh"
    assert button.text() == ""


def test_no_emoji_on_buttons_and_tabs():
    """UT-GUI-017.004.M01.T01: No emoji on buttons and tabs."""
    offenders = []
    for path in sorted(_GUI_DIR.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in _WIDGET_TEXT.finditer(line):
                if _EMOJI.search(match.group(2)):
                    offenders.append(f"{path.name}:{lineno}")
    assert offenders == []


def test_risky_buttons_marked_danger(qapp):
    """UT-GUI-017.005.M01.T01: Risky buttons are marked danger in every theme."""
    button = QPushButton("Square Off All")
    icons.mark_danger(button)
    assert button.property("role") == "danger"
    for qss in theme.THEMES.values():
        assert 'QPushButton[role="danger"]' in qss
    for name in ("dashboard_panel.py", "settings_panel.py"):
        assert "mark_danger(" in (_GUI_DIR / name).read_text(encoding="utf-8")
