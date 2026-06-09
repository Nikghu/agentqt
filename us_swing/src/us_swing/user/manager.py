"""Module: MD-INF-006.001.M01 — user/manager.py
Parent SRD: SRD-INF-006.001 – SRD-INF-006.007

UserManager provides CRUD operations over user profiles and controls
mode transitions (paper ↔ live).  It is the only layer that may read or
write the ``users`` database table via DatabaseManager.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from us_swing.config.settings import AppConfig
from us_swing.data.models import RiskConfig as ModelRiskConfig
from us_swing.data.models import UserProfile, UserRecord
from us_swing.db.manager import DatabaseManager
from us_swing.exceptions import (
    ConfirmationRequiredError,
    DuplicateUserError,
    LiveModeDisabledError,
    UserNotFoundError,
)

log = logging.getLogger(__name__)

# Token required when switching to live mode (simple shared secret; can be
# replaced with a proper auth mechanism in a future phase).
_LIVE_CONFIRM_TOKEN = "CONFIRM_LIVE_TRADING"

_VALID_MODES = {"paper", "live"}


class UserManager:
    """CRUD and mode-transition service for user profiles.

    Args:
        db:  Initialised :class:`DatabaseManager` (schema already created).
        cfg: Application config (read for ``live_mode_enabled``).
    """

    def __init__(self, db: DatabaseManager, cfg: AppConfig) -> None:
        self._db  = db
        self._cfg = cfg

    # ── Create ────────────────────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        display_name: str,
        ibkr_client_id: int,
        mode: str = "paper",
    ) -> UserProfile:
        """Create a new user with default settings.

        Raises:
            DuplicateUserError: If ``username`` or ``ibkr_client_id`` already exists.
            ValueError: If ``mode`` is not 'paper' or 'live'.
        """
        self._validate_mode(mode)
        default_settings = _default_settings_json()
        record = UserRecord(
            user_id=0,          # auto-assigned by DB
            username=username,
            display_name=display_name,
            ibkr_client_id=ibkr_client_id,
            settings_json=json.dumps(default_settings),
            mode=mode,
        )
        try:
            user_id = self._db.insert_user(record)
        except Exception as exc:
            # SQLAlchemy raises IntegrityError on UNIQUE constraint violation.
            if "UNIQUE" in str(exc).upper() or "unique" in str(exc).lower():
                raise DuplicateUserError(
                    f"User with username='{username}' or ibkr_client_id={ibkr_client_id} already exists."
                ) from exc
            raise

        log.info("UserManager: created user '%s' (id=%d)", username, user_id)
        record.user_id = user_id
        return self._to_profile(record)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_user(self, user_id: int) -> UserProfile:
        """Retrieve a user profile by ID.

        Raises:
            UserNotFoundError: If no user with that ID exists.
        """
        record = self._db.fetch_user(user_id)
        if record is None:
            raise UserNotFoundError(f"No user found with user_id={user_id}.")
        return self._to_profile(record)

    def list_users(self) -> list[UserProfile]:
        """Return all user profiles; empty list when no users exist."""
        return [self._to_profile(r) for r in self._db.fetch_all_users()]

    # ── Update ────────────────────────────────────────────────────────────────

    def update_user(self, user_id: int, **kwargs: Any) -> UserProfile:
        """Update one or more user fields.

        Only these keys are accepted: ``display_name``, ``ibkr_client_id``,
        ``settings_json``, ``mode``.

        Raises:
            UserNotFoundError: If the user does not exist.
            ValueError: If an invalid ``mode`` value is supplied.
        """
        self._ensure_exists(user_id)
        if "mode" in kwargs:
            self._validate_mode(kwargs["mode"])
        self._db.update_user(user_id, **kwargs)
        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> None:
        """Delete a user record.  Orphan trades/positions are retained.

        Raises:
            UserNotFoundError: If the user does not exist.
        """
        self._ensure_exists(user_id)
        self._db.delete_user(user_id)
        log.info("UserManager: deleted user_id=%d (orphan records retained)", user_id)

    # ── Mode switching ────────────────────────────────────────────────────────

    def switch_mode(
        self,
        user_id: int,
        new_mode: str,
        confirm_token: str | None = None,
    ) -> UserProfile:
        """Switch a user between paper and live mode.

        Switching to ``'live'`` requires:
        1. ``AppConfig.live_mode_enabled == True`` (Phase 0: disabled).
        2. ``confirm_token == 'CONFIRM_LIVE_TRADING'``.

        Raises:
            LiveModeDisabledError: If live mode is disabled in config.
            ConfirmationRequiredError: If no / wrong confirmation token supplied.
            UserNotFoundError: If the user does not exist.
            ValueError: If ``new_mode`` is not 'paper' or 'live'.
        """
        self._validate_mode(new_mode)
        self._ensure_exists(user_id)

        if new_mode == "live":
            if not self._cfg.live_mode_enabled:
                raise LiveModeDisabledError(
                    "Live mode is disabled for this phase. "
                    "Set 'live_mode_enabled = true' in us_swing.toml to enable."
                )
            if confirm_token != _LIVE_CONFIRM_TOKEN:
                raise ConfirmationRequiredError(
                    "Switching to live mode requires confirm_token='CONFIRM_LIVE_TRADING'."
                )

        self._db.update_user(user_id, mode=new_mode)
        log.info("UserManager: user_id=%d switched to '%s' mode", user_id, new_mode)
        return self.get_user(user_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ensure_exists(self, user_id: int) -> None:
        if self._db.fetch_user(user_id) is None:
            raise UserNotFoundError(f"No user found with user_id={user_id}.")

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {_VALID_MODES}.")

    @staticmethod
    def _to_profile(record: UserRecord) -> UserProfile:
        """Parse raw UserRecord into an enriched UserProfile."""
        try:
            settings: dict = json.loads(record.settings_json or "{}")
        except json.JSONDecodeError:
            log.warning("UserManager: could not parse settings_json for user_id=%d; using defaults", record.user_id)
            settings = {}

        risk_raw = settings.get("risk_config", {})
        risk = ModelRiskConfig(
            risk_per_trade_pct = float(risk_raw.get("risk_per_trade_pct", 1.0)),
            max_position_value = float(risk_raw.get("max_position_value", 10_000.0)),
            max_capital_value  = float(risk_raw.get("max_capital_value", 2_000.0)),
            max_daily_loss_pct = float(risk_raw.get("max_daily_loss_pct", 2.0)),
            default_order_type = str(risk_raw.get("default_order_type", "MKT")),
            confirm_orders     = bool(risk_raw.get("confirm_orders", True)),
        )

        return UserProfile(
            user_id         = record.user_id,
            username        = record.username,
            display_name    = record.display_name,
            ibkr_client_id  = record.ibkr_client_id,
            mode            = record.mode,
            risk_config     = risk,
            strategy_config = dict(settings.get("strategy_config", {})),
            screener_config = dict(settings.get("screener_config", {})),
        )


def _default_settings_json() -> dict:
    return {
        "risk_config": {
            "risk_per_trade_pct": 1.0,
            "max_position_value": 10_000.0,
            "max_capital_value":  2_000.0,
            "max_daily_loss_pct": 2.0,
            "default_order_type": "MKT",
            "confirm_orders":     True,
        },
        "strategy_config": {
            "breakout_enabled": True,
            "pullback_enabled": True,
        },
        "screener_config": {
            "volatility_enabled": True,
            "rsi_enabled": True,
            "rsi_min": 30,
            "rsi_max": 70,
        },
    }
