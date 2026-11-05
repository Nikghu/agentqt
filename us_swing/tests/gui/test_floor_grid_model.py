"""Tests for the Market Floor grid rules (MD-GUI-034.005.M05)."""
from __future__ import annotations

from us_swing.gui.floor_grid_model import GridModel, PanelSpec, clamp_rect, snap_delta


def _spec(pid: str, x: int, y: int, w: int, h: int) -> PanelSpec:
    return PanelSpec(pid, "ideas.top", x=x, y=y, w=w, h=h)


def _no_overlap(model: GridModel) -> bool:
    panels = model.panels
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h:
                return False
    return True


def test_move_onto_another_pushes_it_down() -> None:
    """UT-GUI-034.005.M05.T01: a moved panel keeps its place; the other goes below."""
    model = GridModel([_spec("a", 0, 0, 4, 4), _spec("b", 6, 0, 4, 4)])
    model.move("b", 1, 1)
    b, a = model.get("b"), model.get("a")
    assert b is not None and a is not None
    assert (b.x, b.y) == (1, 1)
    assert a.y == b.y + b.h
    assert _no_overlap(model)


def test_resize_clamps_to_columns_and_minimum() -> None:
    """UT-GUI-034.005.M05.T02: w 20 at x 4 gives w 8; minimum 2 x 3 is kept."""
    model = GridModel([_spec("a", 4, 0, 4, 4)])
    model.resize("a", 20, 4)
    spec = model.get("a")
    assert spec is not None and spec.w == 12 - 4 and spec.x == 4
    model.resize("a", 0, 0)
    assert (spec.w, spec.h) == (2, 3)
    assert clamp_rect(11, -3, 20, 1) == (0, 0, 12, 3)


def test_new_panel_goes_below_when_full() -> None:
    """UT-GUI-034.005.M05.T03: with no free spot the new panel sits below the lowest one."""
    model = GridModel([_spec("a", 0, 0, 12, 4), _spec("b", 0, 4, 12, 5)])
    spec = model.add(PanelSpec("c", "news.latest", w=6, h=4))
    assert (spec.x, spec.y) == (0, 9)
    assert _no_overlap(model)


def test_new_panel_takes_first_free_spot() -> None:
    """UT-GUI-034.005.M05.T04: scanning top-down, left-right finds the first gap."""
    model = GridModel([_spec("a", 0, 0, 6, 4)])
    spec = model.add(PanelSpec("b", "news.latest", w=4, h=3))
    assert (spec.x, spec.y) == (6, 0)


def test_remove_and_round_trip() -> None:
    """UT-GUI-034.005.M05.T05: remove drops a panel; to_dict/from_dict keep every field."""
    spec = PanelSpec("p1", "ideas.top", "card", {"side": "long"}, "A", 2, 3, 5, 6)
    assert PanelSpec.from_dict(spec.to_dict()) == spec
    model = GridModel([spec, _spec("p2", 6, 0, 4, 4)])
    model.remove("p1")
    assert [p.id for p in model.panels] == ["p2"]
    assert PanelSpec.from_dict({**spec.to_dict(), "link": ""}).link is None


def test_chain_push_and_duplicate_ids() -> None:
    """UT-GUI-034.005.M05.T06: pushes cascade; empty or repeated ids get new ones."""
    model = GridModel([_spec("a", 0, 0, 4, 3), _spec("b", 0, 3, 4, 3), _spec("c", 0, 6, 4, 3)])
    model.move("c", 0, 0)
    assert _no_overlap(model)
    assert model.get("c") is not None and model.get("c").y == 0  # type: ignore[union-attr]
    twin = GridModel([_spec("a", 0, 0, 4, 3), _spec("a", 6, 0, 4, 3), _spec("", 0, 4, 4, 3)])
    assert len({p.id for p in twin.panels}) == 3


def test_snap_delta() -> None:
    """UT-GUI-034.005.M05.T07: pixel distance rounds to whole cells."""
    assert snap_delta(110, 31, 100, 32) == (1, 1)
    assert snap_delta(40, -20, 100, 32) == (0, -1)
    assert snap_delta(5, 5, 0, 0) == (0, 0)
