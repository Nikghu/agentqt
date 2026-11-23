"""
Module: MD-EXE-022.017.M07 — tests
Parent SRD: SRD-EXE-022.017

``usswing.dev.preview`` writes one HTML chart and opens it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.execution.plugin_helpers import SWING_PLUS, frames
from usswing import dev

from us_swing.core.indicator_plugins import builtin_names, check_file


def test_preview_writes_html_chart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-022.017.M07.T01: Preview writes an HTML chart."""
    opened: list[str] = []
    monkeypatch.setattr(dev.webbrowser, "open", opened.append)
    spec = check_file(SWING_PLUS, builtin_names=builtin_names()).spec
    assert spec is not None
    target = tmp_path / "swing.html"

    saved = dev.preview(spec.indicator_class, frames(120), {"Candles": 10}, path=target)

    page = saved.read_text(encoding="utf-8")
    data = json.loads(re.search(r"const data = (\{.*\});", page).group(1))  # type: ignore[union-attr]
    assert saved == target and opened == [target.resolve().as_uri()]
    assert "SWING_PLUS 1.0" in page
    assert [line["name"] for line in data["lines"]] == ["SWING_PLUS", "Swing high", "Swing low"]
    assert len(data["candles"]) == 120 and len(data["lines"][0]["points"]) == 110
    assert "unpkg.com" not in page and "createChart" in page
