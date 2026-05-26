"""
Module: MD-EXE-002.001.M01 — PositionTracker
Parent SRD: SRD-EXE-002.001, SRD-EXE-002.004, SRD-EXE-005.001, SRD-EXE-005.006
"""
from __future__ import annotations

import logging
import threading

from us_swing.data.models import IBKRPosition, OpenPosition, PositionState
from us_swing.db.manager import DatabaseManager
from us_swing.exceptions import InvalidStateTransitionError

log = logging.getLogger(__name__)

_VALID_TRANSITIONS: dict[PositionState, set[PositionState]] = {
    PositionState.NEW:           {PositionState.PARTIAL_ENTRY, PositionState.OPEN},
    PositionState.PARTIAL_ENTRY: {PositionState.PARTIAL_ENTRY, PositionState.OPEN},
    PositionState.OPEN:          {PositionState.PARTIAL_EXIT, PositionState.CLOSED},
    PositionState.PARTIAL_EXIT:  {PositionState.PARTIAL_EXIT, PositionState.CLOSED},
    PositionState.CLOSED:        set(),
}


class PositionTracker:
    """Thread-safe in-memory position store mirrored to the DB."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._positions: dict[tuple[int, str], OpenPosition] = {}
        self._lock = threading.RLock()

    # ── Mutating operations ───────────────────────────────────────────────────

    def open(self, pos: OpenPosition) -> None:
        """Register a new position (state=NEW) and upsert to DB."""
        with self._lock:
            self._positions[(pos.user_id, pos.symbol)] = pos
            self._db.upsert_position(pos)

    def close(self, user_id: int, symbol: str) -> OpenPosition:
        """Remove position from memory and DB; return the removed position."""
        with self._lock:
            pos = self._positions.pop((user_id, symbol))
            self._db.delete_position(user_id, symbol)
            return pos

    def update_stop(self, user_id: int, symbol: str, new_stop: float) -> None:
        """Update stop_loss in memory and DB."""
        with self._lock:
            pos = self._positions[(user_id, symbol)]
            pos.stop_loss = new_stop
            self._db.upsert_position(pos)

    def update_state(
        self,
        user_id: int,
        symbol: str,
        new_state: PositionState,
        filled_qty: int | None = None,
    ) -> None:
        """Validate and apply a state transition; update DB."""
        with self._lock:
            pos = self._positions[(user_id, symbol)]
            current = PositionState(pos.state)
            allowed = _VALID_TRANSITIONS[current]
            if new_state not in allowed:
                raise InvalidStateTransitionError(
                    f"Invalid transition {current.value} → {new_state.value} for {symbol}"
                )
            pos.state = new_state.value
            if filled_qty is not None:
                pos.filled_quantity = filled_qty
            self._db.upsert_position(pos)

    # ── Query operations ──────────────────────────────────────────────────────

    def has_open(self, user_id: int, symbol: str) -> bool:
        with self._lock:
            return (user_id, symbol) in self._positions

    def get_all(self, user_id: int | None = None) -> list[OpenPosition]:
        """Return all positions; pass user_id to filter to a single user."""
        with self._lock:
            if user_id is None:
                return list(self._positions.values())
            return [p for (uid, _), p in self._positions.items() if uid == user_id]

    def load_from_db(self, user_id: int) -> None:
        """Restore non-CLOSED positions from DB on application startup."""
        records = self._db.fetch_open_positions(user_id)
        with self._lock:
            for r in records:
                pos = OpenPosition(
                    symbol=r.symbol,
                    user_id=r.user_id,
                    quantity=r.quantity,
                    average_price=r.average_price,
                    stop_loss=r.stop_loss,
                    target_price=r.target_price,
                    mode=r.mode,
                    state=r.state,
                    trailing_stop=r.trailing_stop,
                )
                self._positions[(user_id, r.symbol)] = pos

    def reconcile(
        self,
        ibkr_positions: list[IBKRPosition],
        user_id: int = 0,
    ) -> list[str]:
        """Adopt IBKR positions absent from local DB; log WARNING per adopted symbol."""
        adopted: list[str] = []
        with self._lock:
            for ibkr_pos in ibkr_positions:
                if (user_id, ibkr_pos.symbol) not in self._positions:
                    pos = OpenPosition(
                        symbol=ibkr_pos.symbol,
                        user_id=user_id,
                        quantity=ibkr_pos.quantity,
                        average_price=ibkr_pos.average_price,
                        stop_loss=0.0,
                        target_price=0.0,
                        mode="live",
                        state=PositionState.OPEN.value,
                    )
                    self._positions[(user_id, ibkr_pos.symbol)] = pos
                    self._db.upsert_position(pos)
                    log.warning("[Execution] Adopted unrecognised IBKR position: %s", ibkr_pos.symbol)
                    adopted.append(ibkr_pos.symbol)
        return adopted
