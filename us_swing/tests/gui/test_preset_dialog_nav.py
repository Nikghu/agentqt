"""Unit tests: MD-GUI-042.001.M01 — Edit Preset side navigation.
Refs: UT-GUI-042.001.M01.T01 – UT-GUI-042.006.M01.T01
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from tests.screener.conftest import make_composite_preset
from us_swing.gui.screener_panel import _PresetBuilderDialog


def _dialog(qtbot, preset=None) -> _PresetBuilderDialog:  # type: ignore[no-untyped-def]
    dlg = _PresetBuilderDialog(mgr=SimpleNamespace(), user_id="u1", preset=preset)
    qtbot.addWidget(dlg)
    return dlg


def _page_of(dlg: _PresetBuilderDialog, key: str):  # type: ignore[no-untyped-def]
    keys = [k for k, _ in dlg._NAV_SECTIONS]
    return dlg._pages.widget(keys.index(key))


def test_side_list_and_pages(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.001.M01.T01: Side list shows four sections and switches pages."""
    dlg = _dialog(qtbot)
    names = [dlg._nav_rows[k].name_lbl.text().split("&nbsp; ")[-1] for k in dlg._nav_rows]
    assert names == ["General", "Screeners", "AI Ranking", "AI Context"]
    assert dlg._nav.currentRow() == 0 and dlg._pages.currentIndex() == 0
    dlg._nav.setCurrentRow(3)
    assert dlg._pages.currentWidget() is _page_of(dlg, "context")


def test_general_holds_trade_settings(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.002.M01.T01: General holds name, timeframe, styles and Assign Users."""
    dlg = _dialog(qtbot)
    general = _page_of(dlg, "general")
    widgets = [dlg._name, dlg._desc, dlg._tf_preset, *dlg._style_checks.values()]
    assert dlg._assign_widget is not None
    assert all(general.isAncestorOf(w) for w in [*widgets, dlg._assign_widget])


def test_pages_hold_their_fields(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.003.M01.T01: Each page holds its own fields."""
    dlg = _dialog(qtbot)
    assert _page_of(dlg, "screeners").isAncestorOf(dlg._preview)
    assert _page_of(dlg, "ai").isAncestorOf(dlg._ai_model_combo)
    assert _page_of(dlg, "ai").isAncestorOf(dlg._ai_model_validate_btn)
    context = _page_of(dlg, "context")
    assert all(context.isAncestorOf(c) for c in dlg._ai_ctx_checks.values())


def test_ai_fields_greyed_when_off(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.003.M01.T02: AI fields are greyed out, not hidden, while AI is off."""
    dlg = _dialog(qtbot)
    fields = [dlg._ai_model_combo, dlg._ai_ctx_checks["earnings"], dlg._ai_model_validate_btn]
    assert not any(w.isEnabled() for w in fields)
    assert not any(w.isHidden() for w in fields)
    dlg._ai_ranking_chk.setChecked(True)
    assert all(w.isEnabled() for w in fields)


def test_summaries_follow_changes(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.004.M01.T01: Summary lines follow field changes."""
    dlg = _dialog(qtbot)
    dlg._style_checks["swing"].setChecked(True)
    assert dlg._nav_rows["general"].meta_lbl.text() == "Daily · Swing"
    dlg._ai_ranking_chk.setChecked(True)
    dlg._ai_top_n.setValue(7)
    dlg._ai_model_combo.setEditText("my-model")
    assert dlg._nav_rows["ai"].meta_lbl.text() == "Top 7 · my-model"
    dlg._ai_ctx_checks["sector"].setChecked(True)
    assert dlg._nav_rows["context"].meta_lbl.text() == "1 data · 0 top picks"


def test_amber_when_missing(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.005.M01.T01: Dots warn when name, screener or model is missing."""
    dlg = _dialog(qtbot)
    dlg._ai_ranking_chk.setChecked(True)
    dlg._ai_model_combo.setEditText("")
    assert dlg._nav_states["general"] == "warn"
    assert dlg._nav_states["screeners"] == "warn"
    assert dlg._nav_states["ai"] == "warn"
    dlg._name.setText("My preset")
    dlg._ai_model_combo.setEditText("my-model")
    assert dlg._nav_states["general"] == "ok" and dlg._nav_states["ai"] == "ok"


def test_save_error_shown_in_footer(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.005.M01.T03: A failed Save shows its reason in the footer on any page."""
    dlg = _dialog(qtbot)
    dlg._name.setText("My preset")
    dlg._nav.setCurrentRow(3)
    dlg._on_save()
    assert dlg._save_error_lbl.text() == "Add at least one group."
    assert dlg.result() == 0
    dlg._on_save_as()
    assert dlg._save_error_lbl.text() == "Add at least one group."


def test_grey_when_ai_off(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.005.M01.T02: AI sections read Off with a grey dot while AI is off."""
    dlg = _dialog(qtbot)
    for key in ("ai", "context"):
        assert dlg._nav_states[key] == "off"
        assert dlg._nav_rows[key].meta_lbl.text() == "Off"


def test_same_preset_saved(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-042.006.M01.T01: An edited preset with no changes builds the same preset."""
    saved = replace(
        make_composite_preset(),
        enable_llm_ranking=True, top_n=7, ai_provider="claude", ai_model="claude-opus-5-5",
        ai_query="near resistance", ai_context=["earnings", "review"],
        trading_styles=["swing"], timeframe="1w",
    )
    dlg = _dialog(qtbot, saved)
    assert dlg._nav_states["screeners"] == "ok"
    assert dlg._nav_rows["screeners"].meta_lbl.text() == "2 groups · OR"
    built = dlg._build_preset_from_ui(saved.id)
    for name in (
        "name", "description", "preset_type", "enable_llm_ranking", "top_n", "ai_provider",
        "ai_model", "ai_query", "ai_context", "trading_styles", "timeframe",
    ):
        assert getattr(built, name) == getattr(saved, name), name
    assert [(g.group_id, g.logic, [r.screener_id for r in g.screeners]) for g in built.groups] == [
        (g.group_id, g.logic, [r.screener_id for r in g.screeners]) for g in saved.groups
    ]
