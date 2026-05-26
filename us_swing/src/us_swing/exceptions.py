"""Module: exceptions.py — Project-wide custom exception hierarchy.

All us_swing exceptions inherit from ``USSwingError`` so callers can
catch the entire family with a single ``except USSwingError`` clause
while still being able to discriminate individual error types.
"""
from __future__ import annotations


class USSwingError(Exception):
    """Base class for all us_swing exceptions."""


# ── Infrastructure ────────────────────────────────────────────────────────────

class ConfigurationError(USSwingError):
    """Invalid or missing application configuration."""


class BrokerConnectionError(USSwingError):
    """IBKR gateway connection could not be established or validated."""


class PacingLimitError(USSwingError):
    """Request rate exceeds the IBKR pacing limit (> 50 req / 10 min)."""


class CandleConsistencyError(USSwingError):
    """Live-built candle differs from the stored historical bar for the same timestamp."""


# ── Database ──────────────────────────────────────────────────────────────────

class DatabaseError(USSwingError):
    """Generic database operation failure."""


# ── User management ───────────────────────────────────────────────────────────

class UserNotFoundError(USSwingError):
    """No user record exists for the given user_id."""


class DuplicateUserError(USSwingError):
    """A user with that username or ibkr_client_id already exists."""


class ConfirmationRequiredError(USSwingError):
    """Switching to live mode requires an explicit confirmation token."""


class OrderSubmissionError(USSwingError):
    """IBKR order submission failed or timed out."""


class InvalidStateTransitionError(USSwingError):
    """Attempted an illegal position state transition."""


class LiveModeDisabledError(USSwingError):
    """Live mode is administratively disabled in the current configuration.

    Raised when ``AppConfig.live_mode_enabled`` is ``False`` and a caller
    attempts to switch a user to live trading.
    """
