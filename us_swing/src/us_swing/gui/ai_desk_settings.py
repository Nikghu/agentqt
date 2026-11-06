"""
Module: MD-GUI-034.016.M15 — gui/ai_desk_settings.py
Parent SRD: SRD-GUI-034.016

Editable desk AI settings in AI Desk → Desk settings: which sources the desk may use,
their models, the monthly API budget, the daily Claude Code CLI token cap and the
OpenRouter key (kept in the OS keychain, never shown).
"""
from __future__ import annotations

import logging
import math
from dataclasses import replace
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import (
    load_settings,
    save_key,
    save_settings,
)
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)
_FIELD_W = 260
_KEY_SAVED = "Saved — type to replace"
_KEY_HINT = "Paste a key to save or replace it"


class DeskAiSettingsForm(QWidget):
    """Form for the desk AI settings with a Save button and a status line."""

    def __init__(self, home: Path | None = None, parent: QWidget | None = None) -> None:
        """Load the saved settings from ``home`` (the desk folder) into the form."""
        super().__init__(parent)
        self._home = home
        self._settings = load_settings(home)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.claude_on = QCheckBox("Use Claude Code CLI (subscription: tokens only, no cost)")
        self.claude_model = self._line(self._settings.claude_model)
        self.claude_tokens = self._line(str(self._settings.claude_tokens_per_day))
        self.openrouter_on = QCheckBox("Use OpenRouter (API: counts against the budget)")
        self.openrouter_model = self._line(self._settings.openrouter_model)
        self.key = self._line("")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(_KEY_HINT)
        self.budget = self._line(f"{self._settings.monthly_budget_usd:.2f}")
        self.claude_on.setChecked(self._settings.claude_on)
        self.openrouter_on.setChecked(self._settings.openrouter_on)
        form.addRow("", self.claude_on)
        form.addRow("Claude model", self.claude_model)
        form.addRow("Claude tokens per day", self.claude_tokens)
        form.addRow("", self.openrouter_on)
        form.addRow("OpenRouter model", self.openrouter_model)
        form.addRow("OpenRouter key", self.key)
        form.addRow("Monthly API budget (USD)", self.budget)
        outer.addLayout(form)
        row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(90)
        # save button → clicked → form → save
        self.save_btn.clicked.connect(self.save)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {C.MUTED};")
        row.addWidget(self.save_btn)
        row.addWidget(self.status, 1)
        outer.addLayout(row)

    @staticmethod
    def _line(text: str) -> QLineEdit:
        edit = QLineEdit(text)
        edit.setFixedWidth(_FIELD_W)
        return edit

    def save(self) -> bool:
        """Check and save the form; return False and show why when a value is not valid."""
        try:
            budget = float(self.budget.text().strip())
            tokens = int(self.claude_tokens.text().strip().replace(",", ""))
            settings = replace(
                self._settings, claude_on=self.claude_on.isChecked(),
                claude_model=self.claude_model.text().strip(),
                openrouter_on=self.openrouter_on.isChecked(),
                openrouter_model=self.openrouter_model.text().strip(),
                monthly_budget_usd=budget, claude_tokens_per_day=tokens)
            if not math.isfinite(budget):
                raise ValueError("budget")
        except ValueError:
            self.status.setText("Budget and tokens per day must be numbers above 0")
            return False
        if ((settings.claude_on and not settings.claude_model)
                or (settings.openrouter_on and not settings.openrouter_model)):
            self.status.setText("Set a model for each source that is on")
            return False
        try:
            save_settings(settings, self._home)
        except OSError as exc:
            self.status.setText(f"Could not save: {exc}")
            return False
        if self.key.text().strip():
            save_key(self.key.text())
            self.key.clear()
            self.key.setPlaceholderText(_KEY_SAVED)
        self._settings = settings
        self.status.setText("Saved; used from the next desk run")
        _log.info("[AI Desk] Desk AI settings saved")
        return True
