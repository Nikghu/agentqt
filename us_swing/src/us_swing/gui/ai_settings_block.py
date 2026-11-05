"""
Module: MD-GUI-033.001.M01 — AI Notes Settings Block
Parent SRD: SRD-GUI-033.001

Top block of Settings → Telegram: an Enable AI notes tick and two provider cards,
Claude Code CLI and OpenRouter, with Default, model and AI Fallback.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.notifications import AiConfig
from us_swing.gui.theme import C
from us_swing.screener.screeners._cloud_ai_models import ALL_MODEL_PRESETS, ENV_API_KEY

CLAUDE_MODELS: tuple[tuple[str, str], ...] = (
    ("Sonnet 5.5", "claude-sonnet-5-5"),
    ("Haiku 5.5", "claude-haiku-5-5"),
    ("Opus 5.5", "claude-opus-5-5"),
)
FALLBACK_HINT = "Tick both providers to use fallback"
_CARD_W = 270


@dataclass(frozen=True, slots=True)
class AiSettings:
    """AI notes settings of one user (SRD-GUI-033.005)."""

    enabled: bool = False
    claude_on: bool = True
    claude_model: str = "claude-sonnet-5-5"
    openrouter_on: bool = False
    openrouter_model: str = ""
    default: str = "claude"
    fallback: bool = False


def user_ai_settings(user: Any) -> AiSettings:
    """Read the ``ai_*`` fields of a user profile."""
    return AiSettings(
        enabled=user.ai_enabled,
        claude_on=user.ai_claude_on,
        claude_model=user.ai_claude_model,
        openrouter_on=user.ai_openrouter_on,
        openrouter_model=user.ai_openrouter_model,
        default=user.ai_default,
        fallback=user.ai_fallback,
    )


def store_ai_settings(settings: AiSettings, user: Any) -> None:
    """Write ``settings`` into the ``ai_*`` fields of a user profile."""
    user.ai_enabled = settings.enabled
    user.ai_claude_on = settings.claude_on
    user.ai_claude_model = settings.claude_model
    user.ai_openrouter_on = settings.openrouter_on
    user.ai_openrouter_model = settings.openrouter_model
    user.ai_default = settings.default
    user.ai_fallback = settings.fallback


def ai_problem(settings: AiSettings, key: str) -> str:
    """What blocks Apply, or an empty string when the settings are complete (SRD-GUI-033.004)."""
    if not settings.enabled:
        return ""
    if not (settings.claude_on or settings.openrouter_on):
        return "Tick at least one AI provider"
    if settings.openrouter_on:
        missing = [name for name, value in (("API key", key), ("model", settings.openrouter_model))
                   if not value.strip()]
        if missing:
            return "Enter the OpenRouter " + " and ".join(missing)
    return ""


def ai_ready(settings: AiSettings, key: str, claude_ok: bool) -> bool:
    """True when the default AI can be used (SRD-GUI-033.006)."""
    if settings.default == "openrouter":
        return (settings.openrouter_on and bool(key.strip())
                and bool(settings.openrouter_model.strip()))
    return settings.claude_on and claude_ok


def claude_found() -> bool:
    """True when the ``claude`` program is on this PC's PATH."""
    return shutil.which("claude") is not None


def ai_config(settings: AiSettings, key: str) -> AiConfig:
    """The client config for ``settings`` and the OpenRouter ``key``."""
    return AiConfig(
        claude_on=settings.claude_on, claude_model=settings.claude_model,
        openrouter_on=settings.openrouter_on, openrouter_model=settings.openrouter_model,
        openrouter_key=key, default=settings.default, fallback=settings.fallback,
    )


def _card(*items: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("settings_card")
    card.setFixedWidth(_CARD_W)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)
    for item in items:
        layout.addWidget(item)
    return card


class AiSettingsBlock(QWidget):
    """Enable AI notes tick, two provider cards, fallback and Test AI (SRD-GUI-033.001–.003)."""

    valid_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._claude_ok = claude_found()
        self._valid = True
        self._syncing = False

        self._enabled = QCheckBox("Enable AI notes")

        self._claude_on = QCheckBox("Claude Code CLI")
        self._claude_default = QRadioButton("Default")
        self._claude_model = QComboBox()
        for label, model_id in CLAUDE_MODELS:
            self._claude_model.addItem(label, model_id)
        self._claude_status = QLabel()

        self._or_on = QCheckBox("OpenRouter")
        self._or_default = QRadioButton("Default")
        self._or_key = QLineEdit()
        self._or_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_key.setPlaceholderText("API key")
        self.key_locked = bool(os.environ.get(ENV_API_KEY))
        if self.key_locked:
            self._or_key.setToolTip(f"Set by {ENV_API_KEY} on this PC")
        self._or_model = QComboBox()
        self._or_model.setEditable(True)
        for _tier, label, model_id, _tools in ALL_MODEL_PRESETS:
            self._or_model.addItem(model_id)
            self._or_model.setItemData(self._or_model.count() - 1, label.strip(),
                                       Qt.ItemDataRole.ToolTipRole)
        line_edit = self._or_model.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("Pick or type a model")
        self._or_status = QLabel()

        default_group = QButtonGroup(self)
        default_group.setExclusive(True)
        default_group.addButton(self._claude_default)
        default_group.addButton(self._or_default)
        self._claude_default.setChecked(True)

        self._fallback = QCheckBox("AI Fallback")
        self._fallback.setToolTip("Use the other provider when the default AI fails")
        self._hint = QLabel(FALLBACK_HINT)
        self._hint.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")
        self._problem = QLabel("")
        self._problem.setStyleSheet(f"color: {C.RED}; font-size: 9pt;")

        cards = QHBoxLayout()
        cards.setSpacing(10)
        cards.addWidget(_card(self._claude_on, self._claude_default, self._claude_model,
                              self._claude_status))
        cards.addWidget(_card(self._or_on, self._or_default, self._or_key, self._or_model,
                              self._or_status))
        cards.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._enabled)
        layout.addLayout(cards)
        layout.addWidget(self._fallback)
        layout.addWidget(self._hint)
        layout.addWidget(self._problem)

        for box in (self._enabled, self._claude_on, self._or_on, self._claude_default,
                    self._or_default, self._fallback):
            box.toggled.connect(self._sync)
        self._or_key.textChanged.connect(self._sync)
        self._or_model.currentTextChanged.connect(self._sync)
        self.load(AiSettings(), "")

    @property
    def inputs(self) -> list[QWidget]:
        """Fields whose changes mark the Telegram section as edited."""
        return [self._enabled, self._claude_on, self._claude_default, self._claude_model,
                self._or_on, self._or_default, self._or_key, self._or_model, self._fallback]

    @property
    def key(self) -> str:
        return self._or_key.text().strip()

    @property
    def is_valid(self) -> bool:
        return self._valid

    def settings(self) -> AiSettings:
        """The settings as shown."""
        model = self._claude_model.currentData()
        return AiSettings(
            enabled=self._enabled.isChecked(),
            claude_on=self._claude_on.isChecked(),
            claude_model=str(model) if model else CLAUDE_MODELS[0][1],
            openrouter_on=self._or_on.isChecked(),
            openrouter_model=self._or_model.currentText().strip(),
            default="openrouter" if self._or_default.isChecked() else "claude",
            fallback=self._fallback.isChecked(),
        )

    def load(self, settings: AiSettings, key: str) -> None:
        """Show ``settings`` and the stored OpenRouter ``key``."""
        self._syncing = True
        self._enabled.setChecked(settings.enabled)
        self._claude_on.setChecked(settings.claude_on)
        index = self._claude_model.findData(settings.claude_model)
        self._claude_model.setCurrentIndex(max(index, 0))
        self._or_on.setChecked(settings.openrouter_on)
        self._or_key.setText(key)
        self._or_model.setCurrentText(settings.openrouter_model)
        default = self._or_default if settings.default == "openrouter" else self._claude_default
        default.setChecked(True)
        self._fallback.setChecked(settings.fallback)
        self._syncing = False
        self._sync()

    def _sync(self) -> None:
        """Apply the enable, default and fallback rules, then refresh status lines."""
        if self._syncing:
            return
        self._syncing = True
        claude, router = self._claude_on.isChecked(), self._or_on.isChecked()
        if self._claude_default.isChecked() and not claude and router:
            self._or_default.setChecked(True)
        elif self._or_default.isChecked() and not router and claude:
            self._claude_default.setChecked(True)
        both = claude and router
        if not both:
            self._fallback.setChecked(False)
        self._syncing = False

        on = self._enabled.isChecked()
        for widget, state in (
            (self._claude_on, on), (self._or_on, on),
            (self._claude_default, on and claude), (self._claude_model, on and claude),
            (self._or_default, on and router), (self._or_key, on and router and not self.key_locked),
            (self._or_model, on and router), (self._fallback, on and both),
        ):
            widget.setEnabled(state)
        self._hint.setVisible(on and not both)
        self._show_status(on and claude, on and router)

        problem = ai_problem(self.settings(), self.key)
        self._problem.setText(problem)
        self._problem.setVisible(bool(problem))
        if self._valid == (not problem):
            return
        self._valid = not problem
        self.valid_changed.emit(self._valid)

    def _show_status(self, claude: bool, router: bool) -> None:
        if not claude:
            self._set_status(self._claude_status, "Not used", C.SUBTEXT)
        elif self._claude_ok:
            self._set_status(self._claude_status, "Found on this PC", C.GREEN)
        else:
            self._set_status(self._claude_status, "Not installed on this PC", C.RED)
        if not router:
            self._set_status(self._or_status, "Not used", C.SUBTEXT)
        elif self.key:
            self._set_status(self._or_status, "API key set", C.GREEN)
        else:
            self._set_status(self._or_status, "API key needed", C.YELLOW)

    @staticmethod
    def _set_status(label: QLabel, text: str, colour: str) -> None:
        label.setText(text)
        label.setStyleSheet(f"color: {colour}; font-size: 9pt;")
